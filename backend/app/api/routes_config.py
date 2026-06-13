from __future__ import annotations

from fastapi import APIRouter

from backend.app.core.config import get_settings
from backend.app.services.model_context import model_context_window

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/runtime")
def runtime_config():
    settings = get_settings()
    return {
        "model": settings.openai_base_model,
        "context_budget": model_context_window(settings.openai_base_model),
    }
