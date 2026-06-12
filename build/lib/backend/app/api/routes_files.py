from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

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


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    node_id: str | None = Form(default=None),
):
    data = await file.read()
    with get_db() as db:
        item = file_library.create_or_reuse_file(
            db,
            name=file.filename or "uploaded-file",
            description=description,
            media_type=file.content_type,
            raw_bytes=data,
        )
        if node_id:
            file_library.update_linked_nodes_for_files(db, [item["id"]], node_id)
            item = file_library.get_file(db, item["id"]) or item
        return item


@router.get("/{file_id}")
def get_file(file_id: str):
    with get_db() as db:
        item = file_library.get_file(db, file_id)
        if not item:
            raise HTTPException(status_code=404, detail="file not found")
        return item


@router.get("/{file_id}/download")
def download_file(file_id: str):
    with get_db() as db:
        item = file_library.get_file(db, file_id)
        if not item:
            raise HTTPException(status_code=404, detail="file not found")
        path = file_library.get_file_storage_path(item)
        if not path:
            raise HTTPException(status_code=404, detail="stored file not found")
        return FileResponse(
            path,
            media_type=item.get("media_type") or "application/octet-stream",
            filename=item.get("name") or path.name,
        )
