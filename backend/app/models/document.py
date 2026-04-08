"""Document model — tracks uploaded PDFs and processing status."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Enum, Text
from app.db.database import Base


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=True)
    chunk_count = Column(Integer, default=0)
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.pending)
    error_message = Column(Text, nullable=True)
    uploaded_by = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
