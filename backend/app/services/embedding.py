"""Self-hosted embedding service using sentence-transformers."""

from typing import List

from sentence_transformers import SentenceTransformer

from app.core.config import settings

_model = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load and cache the embedding model."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts, return list of vectors."""
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return embeddings.tolist()


def embed_query(query: str) -> List[float]:
    """Embed a single query string."""
    return embed_texts([query])[0]
