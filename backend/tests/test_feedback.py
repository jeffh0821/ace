"""Tests for feedback API."""

import pytest
import pytest_asyncio

from app.models.question import Question, QuestionStatus
from tests.conftest import login_as, TEST_PASSWORD


@pytest_asyncio.fixture
async def question_for_sales(db_session, seed_users):
    """Create a question owned by the sales user."""
    users = seed_users
    q = Question(
        question_text="What is a MIL-DTL-38999 connector?",
        answer_text="It is a military-grade circular connector.",
        confidence_score=0.9,
        retrieval_score=0.85,
        llm_confidence=0.95,
        status=QuestionStatus.answered,
        asked_by=users["sales"].id,
    )
    db_session.add(q)
    await db_session.commit()
    await db_session.refresh(q)
    return q


@pytest_asyncio.fixture
async def question_for_engineer(db_session, seed_users):
    """Create a question owned by the engineer user."""
    users = seed_users
    q = Question(
        question_text="What voltage rating does D38999/26WA98SN have?",
        answer_text="500V RMS.",
        confidence_score=0.88,
        retrieval_score=0.82,
        llm_confidence=0.94,
        status=QuestionStatus.answered,
        asked_by=users["engineer"].id,
    )
    db_session.add(q)
    await db_session.commit()
    await db_session.refresh(q)
    return q


@pytest.mark.asyncio
async def test_submit_positive_feedback_own_question(client, seed_users, question_for_sales):
    """User can submit positive feedback on their own question."""
    cookies = await login_as(client, "testsales")
    resp = await client.post(
        "/api/feedback/",
        json={"question_id": question_for_sales.id, "positive": True},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Feedback recorded"
    assert data["positive"] is True
    assert data["question_id"] == question_for_sales.id


@pytest.mark.asyncio
async def test_submit_negative_feedback_own_question(client, seed_users, question_for_sales):
    """User can submit negative feedback on their own question."""
    cookies = await login_as(client, "testsales")
    resp = await client.post(
        "/api/feedback/",
        json={"question_id": question_for_sales.id, "positive": False},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["positive"] is False


@pytest.mark.asyncio
async def test_cannot_submit_feedback_on_others_question(client, seed_users, question_for_engineer):
    """User cannot submit feedback on another user's question (403)."""
    cookies = await login_as(client, "testsales")
    resp = await client.post(
        "/api/feedback/",
        json={"question_id": question_for_engineer.id, "positive": True},
        cookies=cookies,
    )
    assert resp.status_code == 403
    assert "own questions" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_feedback_on_nonexistent_question(client, seed_users):
    """Feedback on a non-existent question returns 404."""
    cookies = await login_as(client, "testsales")
    resp = await client.post(
        "/api/feedback/",
        json={"question_id": 99999, "positive": True},
        cookies=cookies,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_feedback_requires_authentication(client, seed_users, question_for_sales):
    """Unauthenticated feedback request returns 401."""
    resp = await client.post(
        "/api/feedback/",
        json={"question_id": question_for_sales.id, "positive": True},
    )
    assert resp.status_code == 401
