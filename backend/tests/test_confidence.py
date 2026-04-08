"""Tests for confidence scoring service."""

import pytest
from unittest.mock import patch

from app.services.confidence import compute_confidence, is_above_threshold
from app.services.retrieval import RetrievedChunk


def _make_chunk(similarity: float) -> RetrievedChunk:
    """Helper to create a RetrievedChunk with a given similarity score."""
    return RetrievedChunk(
        text="Test chunk text",
        document_id=1,
        document_title="Test Doc",
        page_number=1,
        chunk_index=0,
        similarity_score=similarity,
    )


class TestComputeConfidence:
    """Tests for compute_confidence function."""

    def test_high_scores_return_above_threshold(self):
        """High retrieval and LLM scores produce high combined confidence."""
        chunks = [_make_chunk(0.95), _make_chunk(0.90), _make_chunk(0.85)]
        combined, retrieval, llm = compute_confidence(chunks, 0.95)
        assert combined > 0.8
        assert retrieval > 0.8
        assert llm == 0.95

    def test_low_scores_return_below_threshold(self):
        """Low retrieval and LLM scores produce low combined confidence."""
        chunks = [_make_chunk(0.2), _make_chunk(0.1)]
        combined, retrieval, llm = compute_confidence(chunks, 0.1)
        assert combined < 0.5
        assert retrieval < 0.3

    def test_mixed_scores(self):
        """Mixed scores produce intermediate confidence."""
        chunks = [_make_chunk(0.9), _make_chunk(0.3)]
        combined, retrieval, llm = compute_confidence(chunks, 0.5)
        # Retrieval avg = 0.6, weights 0.5 each => 0.5*0.6 + 0.5*0.5 = 0.55
        assert 0.4 < combined < 0.7

    def test_empty_chunks(self):
        """Empty chunk list yields zero retrieval score."""
        combined, retrieval, llm = compute_confidence([], 0.5)
        assert retrieval == 0.0
        # Combined = 0.5 * 0.0 + 0.5 * 0.5 = 0.25
        assert combined == pytest.approx(0.25, abs=0.01)

    def test_zero_llm_confidence(self):
        """Zero LLM confidence with good retrieval still produces some score."""
        chunks = [_make_chunk(0.9)]
        combined, retrieval, llm = compute_confidence(chunks, 0.0)
        assert llm == 0.0
        assert retrieval > 0.0
        # Combined = 0.5 * 0.9 + 0.5 * 0.0 = 0.45
        assert combined == pytest.approx(0.45, abs=0.01)

    def test_scores_clamped_to_0_1(self):
        """Scores are clamped between 0.0 and 1.0."""
        chunks = [_make_chunk(1.5)]  # artificially high
        combined, retrieval, llm = compute_confidence(chunks, 1.5)
        assert combined <= 1.0
        assert retrieval <= 1.0
        assert llm <= 1.0

    def test_single_chunk(self):
        """Single chunk retrieval score equals that chunk's similarity."""
        chunks = [_make_chunk(0.75)]
        combined, retrieval, llm = compute_confidence(chunks, 0.80)
        assert retrieval == pytest.approx(0.75, abs=0.001)


class TestIsAboveThreshold:
    """Tests for is_above_threshold function."""

    def test_above_threshold(self):
        """Score above threshold returns True."""
        # Default threshold is 0.80
        assert is_above_threshold(0.85) is True

    def test_below_threshold(self):
        """Score below threshold returns False."""
        assert is_above_threshold(0.5) is False

    def test_at_threshold(self):
        """Score exactly at threshold returns True (>=)."""
        from app.core.config import settings
        threshold = settings.confidence_threshold
        assert is_above_threshold(threshold) is True

    def test_zero_confidence(self):
        """Zero confidence is below threshold."""
        assert is_above_threshold(0.0) is False

    def test_perfect_confidence(self):
        """Perfect confidence is above threshold."""
        assert is_above_threshold(1.0) is True
