"""Hybrid chunking: structure-aware splitting with token-size fallback.

Strategy:
1. Split on structural boundaries (headings, page breaks, double newlines)
2. If a structural chunk exceeds max_tokens, split by token count with overlap
3. Each chunk carries metadata: document_id, page_number, chunk_index
"""

import re
from dataclasses import dataclass
from typing import List

# Defaults
DEFAULT_MAX_CHUNK_CHARS = 1500
DEFAULT_OVERLAP_CHARS = 200


@dataclass
class Chunk:
    text: str
    document_id: int
    page_number: int
    chunk_index: int
    metadata: dict


def _split_by_size(text: str, max_chars: int, overlap: int) -> List[str]:
    """Split text into fixed-size chunks with overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        # Try to break at a sentence or paragraph boundary
        if end < len(text):
            for sep in ['. ', '.\n', '\n\n', '\n', ' ']:
                last_sep = text.rfind(sep, start + max_chars // 2, end)
                if last_sep > start:
                    end = last_sep + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else len(text)
    return chunks


def chunk_document(
    pages: list,
    document_id: int,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> List[Chunk]:
    """
    Chunk extracted pages using hybrid strategy.

    Args:
        pages: list of ExtractedPage objects
        document_id: ID of the parent document
        max_chunk_chars: max characters per chunk
        overlap_chars: overlap between consecutive token-split chunks

    Returns:
        List of Chunk objects ready for embedding
    """
    chunks = []
    chunk_idx = 0

    for page in pages:
        # Combine page text with any table text
        full_text = page.text
        if page.tables:
            full_text += "\n\n[TABLE]\n" + "\n[TABLE]\n".join(page.tables)

        if not full_text.strip():
            continue

        # Step 1: split on paragraph/section boundaries
        segments = re.split(r'\n\n+', full_text)

        # Step 2: merge small segments, split large ones
        current_segment = ""
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            if len(current_segment) + len(segment) + 2 <= max_chunk_chars:
                current_segment = (current_segment + "\n\n" + segment).strip()
            else:
                # Flush current
                if current_segment:
                    if len(current_segment) > max_chunk_chars:
                        sub_chunks = _split_by_size(current_segment, max_chunk_chars, overlap_chars)
                    else:
                        sub_chunks = [current_segment]
                    for text in sub_chunks:
                        if len(text.strip()) < 20:
                            continue
                        chunks.append(Chunk(
                            text=text.strip(),
                            document_id=document_id,
                            page_number=page.page_number,
                            chunk_index=chunk_idx,
                            metadata={
                                "document_id": document_id,
                                "page_number": page.page_number,
                                "chunk_index": chunk_idx,
                                "is_ocr": page.is_ocr,
                            },
                        ))
                        chunk_idx += 1
                current_segment = segment

        # Flush remaining
        if current_segment.strip():
            if len(current_segment) > max_chunk_chars:
                sub_chunks = _split_by_size(current_segment, max_chunk_chars, overlap_chars)
            else:
                sub_chunks = [current_segment]
            for text in sub_chunks:
                if len(text.strip()) < 20:
                    continue
                chunks.append(Chunk(
                    text=text.strip(),
                    document_id=document_id,
                    page_number=page.page_number,
                    chunk_index=chunk_idx,
                    metadata={
                        "document_id": document_id,
                        "page_number": page.page_number,
                        "chunk_index": chunk_idx,
                        "is_ocr": page.is_ocr,
                    },
                ))
                chunk_idx += 1

    return chunks
