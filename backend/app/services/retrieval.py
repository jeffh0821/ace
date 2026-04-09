"""Retrieval service — query Chroma for relevant document chunks."""

import re
from dataclasses import dataclass
from typing import List, Optional

from app.core.config import settings
from app.db.chroma_client import get_collection
from app.services.embedding import embed_query

# Keywords that indicate the user is asking about leadership/organization.
# Chunks matching these get a keyword-boost to counter embedding blind spots.
LEADERSHIP_KEYWORDS = re.compile(
    r"\b(ceo|chief executive|chairman|president|chief (?!technology|officer))"
    r"\b|head chef", re.IGNORECASE
)


@dataclass
class RetrievedChunk:
    text: str
    document_id: int
    document_title: str
    page_number: int
    chunk_index: int
    similarity_score: float


def retrieve_chunks(query: str, top_k: Optional[int] = None) -> List[RetrievedChunk]:
    """Embed query and retrieve top-K similar chunks from Chroma.

    Uses vector similarity with a keyword-boost layer: if the query contains
    leadership/organizational keywords (CEO, Chairman, etc.), chunks that
    contain those exact terms are pulled directly and receive a boosted score.
    This counters the embedding model's tendency to miss named entities that
    are buried in otherwise-unrelated content.
    """
    k = top_k or settings.top_k
    collection = get_collection()

    if collection.count() == 0:
        return []

    query_embedding = embed_query(query)

    # Fetch 3x k from vector search to give room for keyword-boosted results
    vector_k = min(k * 3, collection.count())
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=vector_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks: dict[str, RetrievedChunk] = {}
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i]
            similarity = 1.0 - distance
            metadata = results["metadatas"][0][i]
            chunk_key = doc_id
            chunks[chunk_key] = RetrievedChunk(
                text=results["documents"][0][i],
                document_id=int(metadata.get("document_id", 0)),
                document_title=metadata.get("document_title", "Unknown"),
                page_number=int(metadata.get("page_number", 0)),
                chunk_index=int(metadata.get("chunk_index", 0)),
                similarity_score=max(0.0, min(1.0, similarity)),
            )

    # Keyword-boost: if query has leadership terms, pull matching chunks directly
    leadership_match = LEADERSHIP_KEYWORDS.search(query)
    if leadership_match:
        # Fetch all chunks and filter for keyword matches
        all_results = collection.get(include=["documents", "metadatas"])
        keyword = leadership_match.group(0).lower()
        for i in range(len(all_results["ids"])):
            doc_id = all_results["ids"][i]
            if doc_id in chunks:
                continue  # already have it
            text = all_results["documents"][i]
            if keyword in text.lower():
                metadata = all_results["metadatas"][i]
                chunks[doc_id] = RetrievedChunk(
                    text=text,
                    document_id=int(metadata.get("document_id", 0)),
                    document_title=metadata.get("document_title", "Unknown"),
                    page_number=int(metadata.get("page_number", 0)),
                    chunk_index=int(metadata.get("chunk_index", 0)),
                    similarity_score=0.95,  # high guaranteed score for keyword match
                )

    sorted_chunks = sorted(chunks.values(), key=lambda c: c.similarity_score, reverse=True)
    return sorted_chunks[:k]
