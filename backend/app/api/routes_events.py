from __future__ import annotations

from fastapi import APIRouter

from backend.app.db.session import get_db
from backend.app.services import graph_store

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def list_events(limit: int = 100, node_id: str | None = None):
    with get_db() as db:
        return graph_store.list_events(db, limit=limit, node_id=node_id)
