"""Question API — submit questions, get answers, view history."""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.database import get_db
from app.models.question import Question, QuestionStatus
from app.models.escalation import Escalation, EscalationStatus
from app.models.user import User, UserRole
from app.services.retrieval import retrieve_chunks
from app.services.llm import generate_answer
from app.services.confidence import compute_confidence, is_above_threshold

router = APIRouter(prefix="/questions", tags=["questions"])


class AskRequest(BaseModel):
    question: str


class CitationOut(BaseModel):
    document_title: str
    page_number: int
    excerpt: str


class QuestionResponse(BaseModel):
    id: int
    question_text: str
    answer_text: Optional[str] = None
    citations: Optional[List[CitationOut]] = None
    confidence_score: Optional[float] = None
    status: str
    asked_at: str
    feedback_positive: Optional[bool] = None
    engineer_response: Optional[str] = None


@router.post("/", response_model=QuestionResponse)
async def ask_question(
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Step 1: Retrieve relevant chunks
    chunks = retrieve_chunks(body.question)

    # Step 2: Generate answer via LLM
    llm_response = await generate_answer(body.question, chunks)

    # Step 3: Compute confidence
    combined_score, retrieval_score, llm_conf = compute_confidence(
        chunks, llm_response.confidence
    )

    # Step 4: Determine status
    if is_above_threshold(combined_score):
        q_status = QuestionStatus.answered
        answer_text = llm_response.answer
        citations_json = json.dumps(llm_response.citations)
    else:
        q_status = QuestionStatus.escalated
        answer_text = None
        citations_json = None

    # Step 5: Save question
    question = Question(
        question_text=body.question,
        answer_text=answer_text,
        citations=citations_json,
        confidence_score=combined_score,
        retrieval_score=retrieval_score,
        llm_confidence=llm_conf,
        status=q_status,
        asked_by=current_user.id,
    )
    db.add(question)
    await db.flush()
    await db.refresh(question)

    # Step 6: Create escalation if needed
    if q_status == QuestionStatus.escalated:
        context_data = [
            {
                "text": c.text,
                "document_title": c.document_title,
                "page_number": c.page_number,
                "similarity": c.similarity_score,
            }
            for c in chunks
        ]
        escalation = Escalation(
            question_id=question.id,
            retrieved_context=json.dumps(context_data),
        )
        db.add(escalation)

    await db.commit()

    citations_out = None
    if citations_json:
        try:
            citations_out = [CitationOut(**c) for c in json.loads(citations_json)]
        except Exception:
            citations_out = []

    return QuestionResponse(
        id=question.id,
        question_text=question.question_text,
        answer_text=question.answer_text,
        citations=citations_out,
        confidence_score=question.confidence_score,
        status=question.status.value,
        asked_at=question.asked_at.isoformat(),
        feedback_positive=question.feedback_positive,
    )


@router.get("/", response_model=List[QuestionResponse])
async def list_questions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Question).order_by(Question.asked_at.desc())
    if current_user.role == UserRole.sales:
        query = query.where(Question.asked_by == current_user.id)

    result = await db.execute(query)
    questions = result.scalars().all()

    responses = []
    for q in questions:
        engineer_response = None
        if q.status == QuestionStatus.resolved:
            esc_result = await db.execute(
                select(Escalation).where(Escalation.question_id == q.id)
            )
            esc = esc_result.scalar_one_or_none()
            if esc:
                engineer_response = esc.engineer_response

        citations_out = None
        if q.citations:
            try:
                citations_out = [CitationOut(**c) for c in json.loads(q.citations)]
            except Exception:
                citations_out = []

        responses.append(QuestionResponse(
            id=q.id,
            question_text=q.question_text,
            answer_text=q.answer_text,
            citations=citations_out,
            confidence_score=q.confidence_score,
            status=q.status.value,
            asked_at=q.asked_at.isoformat(),
            feedback_positive=q.feedback_positive,
            engineer_response=engineer_response,
        ))

    return responses
