"""Analytics API — admin-only metrics."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.db.database import get_db
from app.models.document import Document
from app.models.question import Question, QuestionStatus
from app.models.escalation import Escalation, EscalationStatus
from app.models.user import User, UserRole

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/")
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    total_q = await db.execute(select(func.count(Question.id)))
    total_questions = total_q.scalar() or 0

    answered = await db.execute(
        select(func.count(Question.id)).where(Question.status == QuestionStatus.answered)
    )
    answered_count = answered.scalar() or 0

    escalated = await db.execute(
        select(func.count(Question.id)).where(
            Question.status.in_([QuestionStatus.escalated, QuestionStatus.resolved])
        )
    )
    escalated_count = escalated.scalar() or 0

    pending_esc = await db.execute(
        select(func.count(Escalation.id)).where(Escalation.status == EscalationStatus.pending)
    )
    pending_escalations = pending_esc.scalar() or 0

    positive_fb = await db.execute(
        select(func.count(Question.id)).where(Question.feedback_positive == True)
    )
    positive_feedback = positive_fb.scalar() or 0

    negative_fb = await db.execute(
        select(func.count(Question.id)).where(Question.feedback_positive == False)
    )
    negative_feedback = negative_fb.scalar() or 0

    total_docs = await db.execute(select(func.count(Document.id)))
    document_count = total_docs.scalar() or 0

    total_users = await db.execute(select(func.count(User.id)))
    user_count = total_users.scalar() or 0

    avg_conf = await db.execute(select(func.avg(Question.confidence_score)))
    avg_confidence = round(avg_conf.scalar() or 0, 3)

    return {
        "total_questions": total_questions,
        "answered_directly": answered_count,
        "escalated": escalated_count,
        "pending_escalations": pending_escalations,
        "escalation_rate": round(escalated_count / max(total_questions, 1), 3),
        "positive_feedback": positive_feedback,
        "negative_feedback": negative_feedback,
        "feedback_satisfaction_rate": round(
            positive_feedback / max(positive_feedback + negative_feedback, 1), 3
        ),
        "average_confidence": avg_confidence,
        "document_count": document_count,
        "user_count": user_count,
    }
