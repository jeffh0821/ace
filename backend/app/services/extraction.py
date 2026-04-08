"""PDF text extraction with OCR fallback.

Strategy:
1. Try native text extraction via PyMuPDF (fast, preserves structure)
2. If a page has little/no text, fall back to Tesseract OCR on rendered image
3. Extract tables as structured text where possible
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io


# Minimum characters on a page before triggering OCR fallback
OCR_TEXT_THRESHOLD = 50


@dataclass
class ExtractedPage:
    page_number: int  # 1-indexed
    text: str
    is_ocr: bool = False
    tables: List[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    filename: str
    page_count: int
    pages: List[ExtractedPage]
    errors: List[str] = field(default_factory=list)


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
            # Try native text extraction first
            text = page.get_text("text")

            # Extract tables as text blocks
            tables = []
            try:
                table_finder = page.find_tables()
                if table_finder and table_finder.tables:
                    for table in table_finder.tables:
                        try:
                            df = table.to_pandas()
                            tables.append(df.to_string(index=False))
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
            ))

        except Exception as e:
            errors.append(f"Extraction failed on page {page_num + 1}: {str(e)}")
            pages.append(ExtractedPage(page_number=page_num + 1, text=""))

    doc.close()

    return ExtractionResult(
        filename=path.name,
        page_count=total_pages,
        pages=pages,
        errors=errors,
    )
