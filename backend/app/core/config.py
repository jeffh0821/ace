"""Application configuration loaded from config.yaml and environment variables."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic_settings import BaseSettings


def load_yaml_config() -> dict:
    """Load config.yaml from project root, return empty dict if not found."""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


_yaml = load_yaml_config()


class Settings(BaseSettings):
    # App
    app_host: str = _yaml.get("app", {}).get("host", "0.0.0.0")
    app_port: int = _yaml.get("app", {}).get("port", 8000)
    secret_key: str = _yaml.get("app", {}).get("secret_key", "CHANGE-ME-IN-PRODUCTION")

    # Database
    database_url: str = "sqlite+aiosqlite:///./ace.db"

    # Chroma
    chroma_persist_dir: str = _yaml.get("database", {}).get("chroma_persist_dir", "./chroma_data")

    # LLM
    llm_provider: str = _yaml.get("llm", {}).get("provider", "openrouter")
    llm_model: str = _yaml.get("llm", {}).get("model", "gpt-4o-mini")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", _yaml.get("llm", {}).get("api_key", ""))

    # Embeddings
    embedding_model: str = _yaml.get("llm", {}).get("embedding_model", "all-MiniLM-L6-v2")

    # Confidence
    confidence_threshold: float = _yaml.get("confidence", {}).get("threshold", 0.80)
    retrieval_weight: float = _yaml.get("confidence", {}).get("retrieval_weight", 0.5)
    llm_weight: float = _yaml.get("confidence", {}).get("llm_weight", 0.5)

    # Retrieval
    top_k: int = _yaml.get("retrieval", {}).get("top_k", 5)

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 hours

    # Upload
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 100

    class Config:
        env_prefix = "ACE_"


settings = Settings()
