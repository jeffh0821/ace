"""Confidence scoring — combine retrieval and LLM confidence."""

from typing import List

from app.core.config import settings
from app.services.retrieval import RetrievedChunk


def compute_confidence(
    retrieval_chunks: List[RetrievedChunk],
    llm_confidence: float,
) -> tuple:
    """
    Compute combined confidence score.
    Returns: (combined_score, retrieval_score, llm_score)
    """
    if retrieval_chunks:
        retrieval_score = sum(c.similarity_score for c in retrieval_chunks) / len(retrieval_chunks)
    else:
        retrieval_score = 0.0

    combined = (
        settings.retrieval_weight * retrieval_score
        + settings.llm_weight * llm_confidence
    )

    combined = max(0.0, min(1.0, combined))
    retrieval_score = max(0.0, min(1.0, retrieval_score))
    llm_confidence = max(0.0, min(1.0, llm_confidence))

    return combined, retrieval_score, llm_confidence


def is_above_threshold(combined_score: float) -> bool:
    return combined_score >= settings.confidence_threshold
