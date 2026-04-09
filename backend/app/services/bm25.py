"""BM25 index service — builds and queries a BM25 index over document chunks.

Used as the keyword-similarity layer in hybrid search alongside vector retrieval.
The index is built from all chunks in Chroma and persisted to disk so it can be
loaded on startup without rebuilding.
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

from rank_bm25 import BM25Okapi

# NLTK components — downloaded on first use
try:
    from nltk.corpus import stopwords
    from nltk.stem import PorterStemmer
    from nltk.tokenize import word_tokenize

    ENGLISH_STOPWORDS = set(stopwords.words("english"))
except LookupError:
    import nltk

    nltk.download("stopwords", quiet=True)
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)
    from nltk.corpus import stopwords
    from nltk.stem import Porterstemmer
    from nltk.tokenize import word_tokenize

    ENGLISH_STOPWORDS = set(stopwords.words("english"))

STEMMER = PorterStemmer()

# Path for persisted BM25 index (container path; bind-mounted to host at data/db/)
BM25_INDEX_PATH = "/app/bm25_index.json"


def _tokenize(text: str) -> list[str]:
    """Tokenize, lowercase, stem, and stop-word remove a string."""
    tokens = word_tokenize(text.lower())
    return [
        STEMMER.stem(t)
        for t in tokens
        if t.isalpha() and t not in ENGLISH_STOPWORDS and len(t) > 2
    ]


@dataclass
class Bm25Result:
    doc_id: str
    score: float


class Bm25Index:
    """Persistent BM25 index over all Chroma chunks."""

    def __init__(self, index_path: str | None = None):
        self.index_path = index_path or BM25_INDEX_PATH
        self._bm25: Optional[BM25Okapi] = None
        self._corpus: list[str] = []
        self._doc_ids: list[str] = []
        self._tokenized_corpus: list[list[str]] = []

    # -------------------------------------------------------------------------
    # Build / load
    # -------------------------------------------------------------------------

    def build(self, chunks: list[dict]) -> None:
        """Build BM25 index from a list of chunk dicts with 'id' and 'text' keys.

        chunks: list of {"id": str, "text": str, "metadata": dict, ...}
        """
        self._corpus = [c["text"] for c in chunks]
        self._doc_ids = [c["id"] for c in chunks]
        self._tokenized_corpus = [_tokenize(text) for text in self._corpus]
        self._bm25 = BM25Okapi(self._tokenized_corpus)
        self._persist()

    def load(self) -> bool:
        """Load a previously persisted index. Returns True on success."""
        if not os.path.exists(self.index_path):
            return False
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._corpus = data["corpus"]
            self._doc_ids = data["doc_ids"]
            self._tokenized_corpus = [_tokenize(text) for text in self._corpus]
            self._bm25 = BM25Okapi(self._tokenized_corpus)
            return True
        except (json.JSONDecodeError, KeyError, OSError):
            return False

    def _persist(self) -> None:
        """Write index to disk."""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump({"corpus": self._corpus, "doc_ids": self._doc_ids}, f)

    # -------------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------------

    def search(self, query: str, top_k: int = 20) -> list[Bm25Result]:
        """Return top-K BM25 results for a query string."""
        if self._bm25 is None:
            return []
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)
        # Return top-k as (doc_id, score) pairs
        ranked = sorted(zip(self._doc_ids, scores), key=lambda x: x[1], reverse=True)
        return [Bm25Result(doc_id=doc_id, score=score) for doc_id, score in ranked[:top_k]]


# Module-level singleton (loaded lazily on first query)
_bm25_index: Optional[Bm25Index] = None


def get_bm25_index() -> Bm25Index:
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = Bm25Index()
        _bm25_index.load()
    return _bm25_index


def build_bm25_from_chroma(collection) -> None:
    """Fetch all chunks from a Chroma collection and build/replace the BM25 index."""
    all_chunks = collection.get(include=["documents", "metadatas", "ids"])
    chunks = [
        {"id": all_chunks["ids"][i], "text": all_chunks["documents"][i]}
        for i in range(len(all_chunks["ids"]))
    ]
    idx = Bm25Index()
    idx.build(chunks)
    global _bm25_index
    _bm25_index = idx
