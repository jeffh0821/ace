"""Document ingestion pipeline: extract -> chunk -> embed -> store."""

import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.db.chroma_client import get_collection
from app.models.document import Document, ProcessingStatus
from app.services.extraction import extract_pdf
from app.services.chunking import chunk_document
from app.services.embedding import embed_texts


async def ingest_document(document_id: int):
    """
    Full ingestion pipeline for a document. Runs as a background task.

    1. Update status to 'processing'
    2. Extract text from PDF (with OCR fallback)
    3. Chunk extracted text (hybrid strategy)
    4. Embed chunks via sentence-transformers
    5. Store embeddings in Chroma
    6. Update status to 'completed'
    """
    async with async_session() as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None:
            return

        try:
            # Mark as processing
            doc.status = ProcessingStatus.processing
            await db.commit()

            # Step 1: Extract text
            extraction = await asyncio.to_thread(extract_pdf, doc.file_path)
            doc.page_count = extraction.page_count

            # Step 2: Chunk
            chunks = chunk_document(extraction.pages, document_id=doc.id)

            if not chunks:
                doc.status = ProcessingStatus.failed
                doc.error_message = "No text could be extracted from document"
                await db.commit()
                return

            # Step 3: Embed
            texts = [c.text for c in chunks]
            embeddings = await asyncio.to_thread(embed_texts, texts)

            # Step 4: Store in Chroma
            collection = get_collection()
            ids = [f"doc{doc.id}_chunk{c.chunk_index}" for c in chunks]
            metadatas = [
                {
                    "document_id": doc.id,
                    "document_title": doc.title,
                    "page_number": c.page_number,
                    "chunk_index": c.chunk_index,
                    "is_ocr": str(c.metadata.get("is_ocr", False)),
                }
                for c in chunks
            ]

            # Chroma has batch limits; add in batches of 100
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                batch_end = i + batch_size
                collection.add(
                    ids=ids[i:batch_end],
                    embeddings=embeddings[i:batch_end],
                    documents=texts[i:batch_end],
                    metadatas=metadatas[i:batch_end],
                )

            # Step 5: Update document record
            doc.chunk_count = len(chunks)
            doc.status = ProcessingStatus.completed
            doc.processed_at = datetime.utcnow()
            if extraction.errors:
                doc.error_message = "; ".join(extraction.errors)
            await db.commit()

        except Exception as e:
            doc.status = ProcessingStatus.failed
            doc.error_message = str(e)[:2000]
            await db.commit()
            raise
