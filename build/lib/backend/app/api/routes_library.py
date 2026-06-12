from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.api.schemas import LibraryEntryCreate
from backend.app.db.session import get_db
from backend.app.services import file_library

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/entries")
def list_entries(query: str | None = None, kind: str | None = None, limit: int = Query(default=50, ge=1, le=100)):
    with get_db() as db:
        return file_library.list_entries(db, query=query, kind=kind, limit=limit)


@router.post("/entries")
def create_entry(payload: LibraryEntryCreate):
    with get_db() as db:
        return file_library.create_or_update_entry(
            db,
            title=payload.title,
            description=payload.description,
            content=payload.content,
        )


@router.get("/entries/{entry_id}")
def get_entry(entry_id: str):
    with get_db() as db:
        item = file_library.get_entry(db, entry_id)
        if not item:
            raise HTTPException(status_code=404, detail="entry not found")
        return item
