"""Config API — admin can view/update runtime settings."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_roles
from app.core.config import settings
from app.models.user import User, UserRole

router = APIRouter(prefix="/config", tags=["config"])


class ConfigResponse(BaseModel):
    llm_model: str
    confidence_threshold: float
    retrieval_top_k: int
    embedding_model: str


class ConfigUpdateRequest(BaseModel):
    llm_model: Optional[str] = None
    confidence_threshold: Optional[float] = None
    retrieval_top_k: Optional[int] = None


@router.get("/", response_model=ConfigResponse)
async def get_config(
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    return ConfigResponse(
        llm_model=settings.llm_model,
        confidence_threshold=settings.confidence_threshold,
        retrieval_top_k=settings.top_k,
        embedding_model=settings.embedding_model,
    )


@router.patch("/")
async def update_config(
    body: ConfigUpdateRequest,
    _admin: User = Depends(require_roles([UserRole.admin])),
):
    updated = {}
    if body.llm_model is not None:
        settings.llm_model = body.llm_model
        updated["llm_model"] = body.llm_model
    if body.confidence_threshold is not None:
        settings.confidence_threshold = body.confidence_threshold
        updated["confidence_threshold"] = body.confidence_threshold
    if body.retrieval_top_k is not None:
        settings.top_k = body.retrieval_top_k
        updated["retrieval_top_k"] = body.retrieval_top_k

    return {"message": "Config updated", "changes": updated}
