"""Feedback API — thumbs up/down on answers."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.database import get_db
from app.models.question import Question
from app.models.user import User

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    question_id: int
    positive: bool


@router.post("/")
async def submit_feedback(
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Question).where(Question.id == body.question_id))
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if question.asked_by != current_user.id:
        raise HTTPException(status_code=403, detail="Can only provide feedback on your own questions")

    question.feedback_positive = body.positive
    question.feedback_at = datetime.utcnow()
    await db.commit()

    return {"message": "Feedback recorded", "question_id": question.id, "positive": body.positive}
