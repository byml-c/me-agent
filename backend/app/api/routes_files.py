from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.api.schemas import LibraryFileCreate
from backend.app.db.session import get_db
from backend.app.services import file_library

router = APIRouter(prefix="/files", tags=["files"])


@router.get("")
def list_files(query: str | None = None, limit: int = Query(default=50, ge=1, le=100)):
    with get_db() as db:
        return file_library.list_files(db, query=query, limit=limit)


@router.post("")
def create_file(payload: LibraryFileCreate):
    with get_db() as db:
        return file_library.create_or_reuse_file(
            db,
            name=payload.name,
            description=payload.description,
            media_type=payload.media_type,
            source_path=payload.source_path,
            content=payload.content,
        )


@router.get("/{file_id}")
def get_file(file_id: str):
    with get_db() as db:
        item = file_library.get_file(db, file_id)
        if not item:
            raise HTTPException(status_code=404, detail="file not found")
        return item
