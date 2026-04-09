"""Confidence scoring — combine retrieval and LLM confidence with BM25 awareness."""

from typing import List

from app.core.config import settings
from app.services.retrieval import RetrievedChunk

# Minimum BM25 score for a "strong" keyword match on a named entity / rare term.
# Exact match on "CEO" scores ~6.0; connector-generic terms score 0.
BM25_STRONG_SCORE = 2.0


def is_strong_bm25_match(chunks: List[RetrievedChunk]) -> bool:
    """
    Return True if the top chunk has a strong BM25 keyword match — rank=1 and
    score above BM25_STRONG_SCORE.  This means the query keyword was found
    verbatim in the chunk text, which is a high-confidence retrieval signal
    even when the embedding similarity is low.
    """
    if not chunks:
        return False
    top = chunks[0]
    return top.bm25_rank == 1 and top.bm25_score >= BM25_STRONG_SCORE


def compute_confidence(
    retrieval_chunks: List[RetrievedChunk],
    llm_confidence: float,
) -> tuple:
    """
    Compute combined confidence score.
    Returns: (combined_score, retrieval_score, llm_score)
    """
    if retrieval_chunks:
        retrieval_score = sum(c.vector_similarity for c in retrieval_chunks) / len(retrieval_chunks)
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


def should_escalate(chunks: List[RetrievedChunk], combined_score: float) -> bool:
    """
    BM25-aware escalation decision.

    Normally escalation is triggered when combined_score < confidence_threshold.
    However, if BM25 found a strong verbatim keyword match (rank=1, score >= 2.0)
    at the top of the results, that keyword hit is itself a strong answer signal
    and escalation should be skipped — the LLM can generate the answer from the
    strongly-retrieved chunk.
    """
    if not is_strong_bm25_match(chunks):
        return combined_score < settings.confidence_threshold
    return False
