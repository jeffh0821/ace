"""Escalation model — low-confidence questions sent to engineers."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, Text, DateTime, Enum, ForeignKey
from app.db.database import Base


class EscalationStatus(str, enum.Enum):
    pending = "pending"
    resolved = "resolved"


class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, unique=True)
    retrieved_context = Column(Text, nullable=True)
    engineer_response = Column(Text, nullable=True)
    responded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(Enum(EscalationStatus), default=EscalationStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
