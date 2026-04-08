"""Chroma vector database client (persistent, self-hosted)."""

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

_client = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Return singleton persistent Chroma client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection(name: str = "documents"):
    """Get or create the documents collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
