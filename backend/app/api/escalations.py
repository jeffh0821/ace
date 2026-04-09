"""Escalation API — view and respond to escalated questions."""

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.db.database import get_db
from app.db.chroma_client import get_collection
from app.models.escalation import Escalation, EscalationStatus
from app.models.question import Question, QuestionStatus
from app.models.user import User, UserRole
from app.services.embedding import embed_texts

router = APIRouter(prefix="/escalations", tags=["escalations"])


class EscalationResponse(BaseModel):
    id: int
    question_id: int
    question_text: str
    retrieved_context: Optional[List[dict]] = None
    asked_by_name: str
    status: str
    engineer_response: Optional[str] = None
    created_at: str
    resolved_at: Optional[str] = None


class RespondRequest(BaseModel):
    response: str


@router.get("/", response_model=List[EscalationResponse])
async def list_escalations(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles([UserRole.engineer, UserRole.admin])),
):
    query = select(Escalation).order_by(Escalation.created_at.desc())
    if status_filter:
        query = query.where(Escalation.status == status_filter)

    result = await db.execute(query)
    escalations = result.scalars().all()

    responses = []
    for esc in escalations:
        q_result = await db.execute(select(Question).where(Question.id == esc.question_id))
        question = q_result.scalar_one_or_none()
        if not question:
            continue

        u_result = await db.execute(select(User).where(User.id == question.asked_by))
        asking_user = u_result.scalar_one_or_none()

        context = None
        if esc.retrieved_context:
            try:
                context = json.loads(esc.retrieved_context)
            except json.JSONDecodeError:
                context = []

        responses.append(EscalationResponse(
            id=esc.id,
            question_id=esc.question_id,
            question_text=question.question_text,
            retrieved_context=context,
            asked_by_name=asking_user.display_name if asking_user else "Unknown",
            status=esc.status.value,
            engineer_response=esc.engineer_response,
            created_at=esc.created_at.isoformat(),
            resolved_at=esc.resolved_at.isoformat() if esc.resolved_at else None,
        ))

    return responses


@router.post("/{escalation_id}/respond")
async def respond_to_escalation(
    escalation_id: int,
    body: RespondRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.engineer, UserRole.admin])),
):
    result = await db.execute(select(Escalation).where(Escalation.id == escalation_id))
    esc = result.scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if esc.status == EscalationStatus.resolved:
        raise HTTPException(status_code=400, detail="Escalation already resolved")

    q_result = await db.execute(select(Question).where(Question.id == esc.question_id))
    question = q_result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Associated question not found")

    esc.engineer_response = body.response
    esc.responded_by = current_user.id
    esc.status = EscalationStatus.resolved
    esc.resolved_at = datetime.utcnow()

    question.status = QuestionStatus.resolved
    question.answer_text = body.response

    # Feed back into knowledgebase
    qa_text = f"Q: {question.question_text}\nA: {body.response}"
    embedding = embed_texts([qa_text])

    collection = get_collection()
    collection.add(
        ids=[f"qa_escalation_{esc.id}"],
        embeddings=embedding,
        documents=[qa_text],
        metadatas=[{
            "document_id": -1,
            "document_title": "Engineer Q&A",
            "page_number": 0,
            "chunk_index": 0,
            "is_ocr": "False",
            "source": "escalation_response",
            "escalation_id": esc.id,
        }],
    )

    await db.commit()

    return {"message": "Response submitted and added to knowledgebase", "escalation_id": esc.id}


@router.delete("/{escalation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_escalation(
    escalation_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    """Delete an escalation and its associated question (admin only).

    Chroma entry for the escalation Q&A (qa_escalation_*) is also removed.
    The question row is deleted first, which cascades to the escalation row via FK.
    """
    result = await db.execute(select(Escalation).where(Escalation.id == escalation_id))
    escalation = result.scalar_one_or_none()
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")

    # Remove Chroma entry for resolved escalation Q&A
    try:
        collection = get_collection()
        collection.delete(where={"source": "escalation_response", "escalation_id": escalation.id})
    except Exception:
        pass

    # Delete the question first — FK cascade removes the escalation row
    q_result = await db.execute(select(Question).where(Question.id == escalation.question_id))
    question = q_result.scalar_one_or_none()
    if question:
        await db.delete(question)

    return None
