"""Question and Answer models."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Enum, ForeignKey, Boolean
from app.db.database import Base


class QuestionStatus(str, enum.Enum):
    answered = "answered"
    escalated = "escalated"
    resolved = "resolved"


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=True)
    citations = Column(Text, nullable=True)  # JSON string
    confidence_score = Column(Float, nullable=True)
    retrieval_score = Column(Float, nullable=True)
    llm_confidence = Column(Float, nullable=True)
    status = Column(Enum(QuestionStatus), nullable=False)
    asked_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    asked_at = Column(DateTime, default=datetime.utcnow)
    feedback_positive = Column(Boolean, nullable=True)
    feedback_at = Column(DateTime, nullable=True)
