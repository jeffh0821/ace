"""Document management API — upload, list, delete."""

import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.core.config import settings
from app.db.database import get_db
from app.db.chroma_client import get_collection
from app.models.document import Document, ProcessingStatus
from app.models.user import User, UserRole
from app.services.ingestion import ingest_document
from app.services.bm25 import build_bm25_from_chroma

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    id: int
    title: str
    filename: str
    file_size_bytes: int
    page_count: Optional[int]
    chunk_count: int
    status: str
    error_message: Optional[str]
    uploaded_at: str
    processed_at: Optional[str]

    class Config:
        from_attributes = True


class DocumentUpdateRequest(BaseModel):
    title: str


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.engineer, UserRole.admin])),
):
    """Upload a PDF document for ingestion."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Save file
    safe_filename = f"{int(datetime.utcnow().timestamp())}_{file.filename}"
    file_path = os.path.join(settings.upload_dir, safe_filename)

    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_upload_size_mb}MB limit")

    with open(file_path, "wb") as f:
        f.write(content)

    # Create document record
    title = os.path.splitext(file.filename)[0]
    doc = Document(
        title=title,
        filename=file.filename,
        file_path=file_path,
        file_size_bytes=len(content),
        uploaded_by=current_user.id,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # Trigger background ingestion
    background_tasks.add_task(ingest_document, doc.id)

    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        filename=doc.filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        status=doc.status.value,
        error_message=doc.error_message,
        uploaded_at=doc.uploaded_at.isoformat(),
        processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
    )


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all documents (any authenticated user)."""
    result = await db.execute(select(Document).order_by(Document.uploaded_at.desc()))
    docs = result.scalars().all()
    return [
        DocumentResponse(
            id=d.id,
            title=d.title,
            filename=d.filename,
            file_size_bytes=d.file_size_bytes,
            page_count=d.page_count,
            chunk_count=d.chunk_count,
            status=d.status.value,
            error_message=d.error_message,
            uploaded_at=d.uploaded_at.isoformat(),
            processed_at=d.processed_at.isoformat() if d.processed_at else None,
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        filename=doc.filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        status=doc.status.value,
        error_message=doc.error_message,
        uploaded_at=doc.uploaded_at.isoformat(),
        processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    body: DocumentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles([UserRole.admin])),
):
    """Update a document's title (admin only).

    If the title changes, all Chroma chunks for this document are updated
    so that citations reflect the new title.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    old_title = doc.title
    doc.title = body.title.strip()
    await db.commit()
    await db.refresh(doc)

    # If title changed, update Chroma metadata for all chunks of this document
    if old_title != doc.title:
        try:
            collection = get_collection()
            chunks = collection.get(where={"document_id": doc.id})
            if chunks and chunks.get("ids"):
                # Update metadata for each chunk
                updated_metadatas = []
                for meta in chunks.get("metadatas", []):
                    updated = dict(meta)
                    updated["document_title"] = doc.title
                    updated_metadatas.append(updated)
                collection.update(
                    ids=chunks["ids"],
                    metadatas=updated_metadatas,
                )
        except Exception:
            pass  # Non-fatal — document record is updated

    return DocumentResponse(
        id=doc.id,
        title=doc.title,
        filename=doc.filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        status=doc.status.value,
        error_message=doc.error_message,
        uploaded_at=doc.uploaded_at.isoformat(),
        processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    """Delete a document and its chunks from Chroma."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from Chroma
    try:
        collection = get_collection()
        collection.delete(where={"document_id": doc.id})
        # Rebuild BM25 index so deleted chunks are no longer indexed
        build_bm25_from_chroma(collection)
    except Exception:
        pass

    # Remove file from disk
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    # Remove from DB
    await db.delete(doc)
    return None
