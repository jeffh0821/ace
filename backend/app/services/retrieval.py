"""Retrieval service — hybrid vector + BM25 search.

Uses Reciprocal Rank Fusion (RRF) to combine Chroma's vector similarity
with BM25 keyword scoring. RRF is parameter-light and handles heterogeneous
score distributions well — no normalization needed.
"""

from dataclasses import dataclass
from typing import List, Optional

from app.core.config import settings
from app.db.chroma_client import get_collection
from app.services.bm25 import get_bm25_index, Bm25Result
from app.services.embedding import embed_query

# RRF damping factor — higher = more weight to high ranks, less to lower ranks
RRF_K = 60


@dataclass
class RetrievedChunk:
    text: str
    document_id: int
    document_title: str
    page_number: int
    chunk_index: int
    similarity_score: float  # RRF fusion score — used for ranking only
    vector_rank: int
    bm25_rank: int
    bm25_score: float = 0.0  # Raw BM25 score — used for BM25-aware confidence boost
    vector_similarity: float = 0.0  # Raw vector similarity [0-1] — used for confidence scoring


def retrieve_chunks(query: str, top_k: Optional[int] = None) -> List[RetrievedChunk]:
    """Hybrid retrieval: Chroma vector search + BM25, fused via RRF.

    RRF score for each chunk = 1/(RRF_K + vector_rank) + 1/(RRF_K + bm25_rank)
    """
    k = top_k or settings.top_k
    collection = get_collection()

    if collection.count() == 0:
        return []

    # --- Vector search ---
    query_embedding = embed_query(query)
    vector_k = min(k * 3, collection.count())
    vector_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=vector_k,
        include=["documents", "metadatas", "distances"],
    )

    # Build vector rank map: doc_id -> (rank, similarity)
    vector_ranks: dict[str, tuple[int, float]] = {}
    if vector_results and vector_results["ids"] and vector_results["ids"][0]:
        for rank, doc_id in enumerate(vector_results["ids"][0], start=1):
            distance = vector_results["distances"][0][rank - 1]
            similarity = 1.0 - distance
            # Use best (highest) rank for duplicates
            if doc_id not in vector_ranks:
                vector_ranks[doc_id] = (rank, similarity)

    # --- BM25 search ---
    bm25_index = get_bm25_index()
    bm25_results: list[Bm25Result] = bm25_index.search(query, top_k=k * 3)

    # Build BM25 rank map: doc_id -> (rank, score)
    bm25_ranks: dict[str, tuple[int, float]] = {}
    for rank, result in enumerate(bm25_results, start=1):
        if result.doc_id not in bm25_ranks:
            bm25_ranks[result.doc_id] = (rank, result.score)

    # --- Collect all candidate doc IDs ---
    all_doc_ids = list(set(vector_ranks.keys()) | set(bm25_ranks.keys()))

    # --- Build full chunk records with RRF scores ---
    candidates: dict[str, RetrievedChunk] = {}
    for doc_id in all_doc_ids:
        v_rank, v_sim = vector_ranks.get(doc_id, (0, 0.0))
        b_rank, b_score = bm25_ranks.get(doc_id, (0, 0.0))

        # RRF fusion
        rrf_score = (1 / (RRF_K + v_rank) if v_rank else 0) + (
            1 / (RRF_K + b_rank) if b_rank else 0
        )

        # Get document text from vector results (or fetch from BM25 corpus)
        if vector_results and vector_results["ids"]:
            try:
                idx = vector_results["ids"][0].index(doc_id)
                text = vector_results["documents"][0][idx]
                metadata = vector_results["metadatas"][0][idx]
            except ValueError:
                # Chunk not in vector results — get from BM25 corpus
                bm25_corpus = bm25_index._corpus
                bm25_doc_ids = bm25_index._doc_ids
                if doc_id in bm25_doc_ids:
                    ci = bm25_doc_ids.index(doc_id)
                    text = bm25_corpus[ci]
                    metadata = {}
                else:
                    continue
        else:
            continue

        candidates[doc_id] = RetrievedChunk(
                text=text,
                document_id=int(metadata.get("document_id", 0)),
                document_title=metadata.get("document_title", "Unknown"),
                page_number=int(metadata.get("page_number", 0)),
                chunk_index=int(metadata.get("chunk_index", 0)),
                similarity_score=rrf_score,
                vector_rank=v_rank,
                bm25_rank=b_rank,
                bm25_score=b_score,
                vector_similarity=v_sim,
            )

    # Sort by RRF score descending
    sorted_chunks = sorted(candidates.values(), key=lambda c: c.similarity_score, reverse=True)
    return sorted_chunks[:k]
