from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.core.config import ROOT_DIR


CONTEXT_LIMITS_PATH = ROOT_DIR / "backend" / "app" / "db" / "context.json"
DEFAULT_CONTEXT_WINDOW = 12000


def model_context_window(model: str | None, fallback: int = DEFAULT_CONTEXT_WINDOW) -> int:
    limits = load_context_limits()
    if not limits:
        return max(1, int(fallback or DEFAULT_CONTEXT_WINDOW))

    normalized_model = (model or "").strip().lower()
    if normalized_model and normalized_model in limits:
        return limits[normalized_model]
    return max(limits.values())


def load_context_limits(path: Path = CONTEXT_LIMITS_PATH) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}

    limits: dict[str, int] = {}
    for key, value in raw.items():
        parsed = parse_context_value(value)
        if parsed is not None:
            limits[str(key).strip().lower()] = parsed
    return limits


def parse_context_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = int(value)
        return parsed if parsed > 0 else None
    if not isinstance(value, str):
        return None

    text = value.strip().lower().replace("_", "").replace(",", "")
    if not text:
        return None
    multiplier = 1
    if text.endswith("k"):
        multiplier = 1000
        text = text[:-1]
    elif text.endswith("m"):
        multiplier = 1000 * 1000
        text = text[:-1]
    try:
        parsed = int(float(text) * multiplier)
    except ValueError:
        return None
    return parsed if parsed > 0 else None
