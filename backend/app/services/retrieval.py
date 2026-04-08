"""Retrieval service — query Chroma for relevant document chunks."""

from dataclasses import dataclass
from typing import List, Optional

from app.core.config import settings
from app.db.chroma_client import get_collection
from app.services.embedding import embed_query


@dataclass
class RetrievedChunk:
    text: str
    document_id: int
    document_title: str
    page_number: int
    chunk_index: int
    similarity_score: float


def retrieve_chunks(query: str, top_k: Optional[int] = None) -> List[RetrievedChunk]:
    """Embed query and retrieve top-K similar chunks from Chroma."""
    k = top_k or settings.top_k
    collection = get_collection()

    if collection.count() == 0:
        return []

    query_embedding = embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i]
            similarity = 1.0 - distance

            metadata = results["metadatas"][0][i]
            chunks.append(RetrievedChunk(
                text=results["documents"][0][i],
                document_id=int(metadata.get("document_id", 0)),
                document_title=metadata.get("document_title", "Unknown"),
                page_number=int(metadata.get("page_number", 0)),
                chunk_index=int(metadata.get("chunk_index", 0)),
                similarity_score=max(0.0, min(1.0, similarity)),
            ))

    return sorted(chunks, key=lambda c: c.similarity_score, reverse=True)
