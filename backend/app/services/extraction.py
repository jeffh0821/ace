"""PDF text extraction with OCR fallback.

Strategy:
1. Try native text extraction via PyMuPDF (fast, preserves structure)
2. If a page has little/no text, fall back to Tesseract OCR on rendered image
3. Extract tables as structured text where possible
4. Strip per-page headers and footers before returning text
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io


# Minimum characters on a page before triggering OCR fallback
OCR_TEXT_THRESHOLD = 50

# Fraction of page height to exclude from top/bottom as header/footer
HEADER_FOOTER_EXCLUDE_FRACTION = 0.06


@dataclass
class ExtractedPage:
    page_number: int  # 1-indexed
    text: str
    is_ocr: bool = False
    tables: List[str] = field(default_factory=list)
    # Lines at the top/bottom of the page that are candidate headers/footers.
    # Maps line_text -> y0_position (normalized 0..1 as fraction of page height).
    hf_candidates: List[Tuple[str, float]] = field(default_factory=list)


@dataclass
class ExtractionResult:
    filename: str
    pdf_title: Optional[str] = None  # Extracted from PDF metadata, may be empty
    page_count: int
    pages: List[ExtractedPage]
    errors: List[str] = field(default_factory=list)


def _build_header_footer_lines(pages: List[ExtractedPage]) -> set:
    """Build a set of lines confirmed as per-page headers or footers.

    Uses two complementary signals:
    1. hf_candidates: lines collected from blocks in the top/bottom 6% of the page
    2. Text frequency: lines extracted directly from page text if they appear as
       complete lines across 80%+ of sample pages (catches phone/URL footers that
       span multiple lines in a single block).
    Page numbers (pure digits) are excluded.
    """
    if len(pages) < 3:
        return set()

    sample = pages[: min(20, len(pages))]
    total_sample = len(sample)
    line_counts: dict = defaultdict(int)

    for epage in sample:
        seen_in_page: set = set()

        # Signal 1: block-position candidates
        for line_text, y_pos in epage.hf_candidates:
            if line_text not in seen_in_page:
                line_counts[line_text] += 1
                seen_in_page.add(line_text)

        # Signal 2: any complete line (after stripping) that appears in 80%+ of pages
        # This catches footer patterns that span multiple lines within a single block
        # (e.g., phone number on one line, URL on next)
        for line in epage.text.split("\n"):
            stripped = line.strip()
            # Only consider short to medium lines that could be footer boilerplate
            if 3 < len(stripped) <= 200 and stripped not in seen_in_page:
                line_counts[stripped] += 1
                seen_in_page.add(stripped)

    # Confirm if appears in 80%+ of sample pages AND is not a page number
    confirmed = set()
    for line_text, count in line_counts.items():
        if count >= total_sample * 0.8 and not line_text.isdigit() and len(line_text) > 2:
            confirmed.add(line_text)

    return confirmed


def _strip_header_footer(raw_text: str, confirmed_lines: set) -> str:
    """Remove confirmed header/footer lines AND pattern-matched boilerplate."""
    import re

    # Phone number + URL patterns that always indicate footer boilerplate.
    # Conservative: only match lines that ARE primarily phone/URL content,
    # not paragraphs that happen to contain CEO-related keywords.
    FOOTER_PATTERNS = re.compile(
        r"^.*800-642-8750.*$|"
        r"^.*800-523-0727.*$|"
        r"^.*www\.peigenesis\.com?.*$|"
        r"^.*techsupport@peigenesis.*$|"
        r"^.*Specifications subject to change.*$|"
        r"^For Assistance in Europe.*back cover.*$",
        re.IGNORECASE | re.MULTILINE,
    )

    result_lines = []
    for line in raw_text.split("\n"):
        stripped = line.strip()
        # Skip confirmed frequency-based headers/footers
        if stripped in confirmed_lines:
            continue
        # Skip lines matching footer patterns (phone numbers, URLs, repeated boilerplate)
        if FOOTER_PATTERNS.search(stripped):
            continue
        result_lines.append(line)

    return "\n".join(result_lines)


def extract_pdf(file_path: str) -> ExtractionResult:
    """Extract all text from a PDF file with OCR fallback."""
    path = Path(file_path)
    doc = fitz.open(str(path))
    pages = []
    errors = []
    total_pages = len(doc)

    for page_num in range(total_pages):
        page = doc[page_num]
        try:
            page_height = page.rect.height
            hf_candidates: List[Tuple[str, float]] = []

            # Collect header/footer candidates while we have the fitz.Page
            try:
                blocks = page.get_text("blocks")
                for block in blocks:
                    if not isinstance(block, tuple) or len(block) < 7:
                        continue
                    x0, y0, x1, y1, block_text, _bno, btype = block
                    if btype != 0:
                        continue
                    # Only consider top/bottom 6% of page
                    y_frac = y0 / page_height
                    if y_frac < HEADER_FOOTER_EXCLUDE_FRACTION or y_frac > (1 - HEADER_FOOTER_EXCLUDE_FRACTION):
                        for line in block_text.split("\n"):
                            stripped = line.strip()
                            if stripped:
                                hf_candidates.append((stripped, y_frac))
            except Exception:
                pass

            # Try native text extraction first
            text = page.get_text("text")

            # Extract tables as text blocks (pure PyMuPDF, no pandas needed)
            tables = []
            try:
                table_finder = page.find_tables()
                if table_finder and table_finder.tables:
                    for table in table_finder.tables:
                        try:
                            rows = table.extract()
                            if rows:
                                tables.append("\n".join(" | ".join(str(c) for c in row) for row in rows))
                        except Exception:
                            pass
            except Exception:
                pass

            # OCR fallback if native text is too sparse
            is_ocr = False
            if len(text.strip()) < OCR_TEXT_THRESHOLD:
                try:
                    pix = page.get_pixmap(dpi=300)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = pytesseract.image_to_string(img)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text
                        is_ocr = True
                except Exception as e:
                    errors.append(f"OCR failed on page {page_num + 1}: {str(e)}")

            pages.append(ExtractedPage(
                page_number=page_num + 1,
                text=text.strip(),
                is_ocr=is_ocr,
                tables=tables,
                hf_candidates=hf_candidates,
            ))

        except Exception as e:
            errors.append(f"Extraction failed on page {page_num + 1}: {str(e)}")
            pages.append(ExtractedPage(page_number=page_num + 1, text=""))

    doc.close()

    # Extract PDF metadata title (may be empty or useless — ingestion layer decides)
    pdf_title = None
    try:
        pdf_doc = fitz.open(str(path))
        metadata = pdf_doc.metadata
        raw_title = metadata.get("title", "").strip()
        # Only use it if it's non-empty and looks like a real title
        # (not the filename, not a single generic word)
        if raw_title and len(raw_title) > 3 and raw_title.lower() != path.stem.lower():
            pdf_title = raw_title
        pdf_doc.close()
    except Exception:
        pass

    # Post-process: strip repeated per-page headers/footers (no re-opening needed)
    confirmed_hf: set = set()
    if len(pages) >= 3:
        confirmed_hf = _build_header_footer_lines(pages)
    for epage in pages:
        epage.text = _strip_header_footer(epage.text, confirmed_hf)

    return ExtractionResult(
        filename=path.name,
        pdf_title=pdf_title,
        page_count=total_pages,
        pages=pages,
        errors=errors,
    )
