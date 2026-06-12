from __future__ import annotations

import hashlib
import json
import math
import mimetypes
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from backend.app.core.config import get_settings
from backend.app.db.session import dumps, get_db, loads, utc_now
from backend.app.services import document_extractors, graph_store, llm

VECTOR_DIMENSIONS = 256
TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
TEXT_SUFFIXES = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".csv", ".xml", ".toml"}
TEXT_MEDIA_PREFIXES = ("text/",)
TEXT_MEDIA_TYPES = {
    "application/json",
    "application/javascript",
    "application/xml",
    "application/x-yaml",
    "application/toml",
}


def list_files(db: sqlite3.Connection, query: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    if query:
        pattern = f"%{query.strip()}%"
        rows = db.execute(
            """
            SELECT *
            FROM library_files
            WHERE name LIKE ? OR description LIKE ? OR summary LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, max(1, min(limit, 100))),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM library_files ORDER BY updated_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    return [row_to_library_file(row) for row in rows]


def get_file(db: sqlite3.Connection, file_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM library_files WHERE id = ?", (file_id,)).fetchone()
    return row_to_library_file(row) if row else None


def list_entries(
    db: sqlite3.Connection,
    query: str | None = None,
    kind: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if query:
        vector_results = search_entries_by_vector(db, query=query, kind=kind, limit=limit)
        if vector_results:
            return vector_results
    where: list[str] = []
    params: list[Any] = []
    if query:
        pattern = f"%{query.strip()}%"
        where.append("(title LIKE ? OR description LIKE ? OR summary LIKE ? OR content LIKE ?)")
        params.extend([pattern, pattern, pattern, pattern])
    if kind:
        where.append("kind = ?")
        params.append(kind)
    sql = "SELECT * FROM library_entries"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(max(1, min(limit, 100)))
    rows = db.execute(sql, tuple(params)).fetchall()
    return [row_to_library_entry(row) for row in rows]


def get_entry(db: sqlite3.Connection, entry_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM library_entries WHERE id = ?", (entry_id,)).fetchone()
    return row_to_library_entry(row) if row else None


def create_or_update_entry(
    db: sqlite3.Connection,
    *,
    title: str,
    description: str | None = None,
    content: str = "",
    kind: str = "text",
    source_file_id: str | None = None,
    actor: str = "user",
) -> dict[str, Any]:
    normalized_title = title.strip() or "未命名条目"
    normalized_description = (description or "").strip() or None
    normalized_content = content or ""
    summary = summarize_for_library(normalized_title, normalized_description, normalized_content)
    normalized_description = summary or normalized_description
    content_hash = hashlib.sha256(
        json.dumps(
            {
                "title": normalized_title,
                "description": normalized_description,
                "content": normalized_content,
                "kind": kind,
                "source_file_id": source_file_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    existing = db.execute("SELECT * FROM library_entries WHERE content_hash = ?", (content_hash,)).fetchone()
    now = utc_now()
    if existing:
        db.execute(
            """
            UPDATE library_entries
            SET title = ?, description = ?, content = ?, summary = ?, kind = ?, source_file_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (normalized_title, normalized_description, normalized_content, summary, kind, source_file_id, now, existing["id"]),
        )
        item = get_entry(db, existing["id"])
    else:
        entry_id = graph_store.new_id("entry")
        db.execute(
            """
            INSERT INTO library_entries
            (id,title,kind,description,content,summary,source_file_id,content_hash,metadata,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                entry_id,
                normalized_title,
                kind,
                normalized_description,
                normalized_content,
                summary,
                source_file_id,
                content_hash,
                dumps({}),
                now,
                now,
            ),
        )
        item = get_entry(db, entry_id)
    upsert_entry_vector(db, item)
    schedule_library_summary("entry", item["id"], normalized_title, normalized_description, normalized_content)
    graph_store.append_event(db, "LibraryEntryUpserted", actor, {"entry_id": item["id"], "title": item["title"], "kind": kind})
    return item


def create_or_reuse_file(
    db: sqlite3.Connection,
    *,
    name: str,
    description: str | None = None,
    media_type: str | None = None,
    source_path: str | None = None,
    content: str | None = None,
    raw_bytes: bytes | None = None,
    actor: str = "user",
) -> dict[str, Any]:
    normalized_name = name.strip() or "未命名文件"
    normalized_description = (description or "").strip() or None
    normalized_path = (source_path or "").strip() or None
    file_bytes = raw_bytes
    if file_bytes is None and content is not None:
        file_bytes = content.encode("utf-8")
    if file_bytes is None and normalized_path:
        path = Path(normalized_path).expanduser()
        if path.exists() and path.is_file():
            file_bytes = path.read_bytes()
    if file_bytes is None:
        file_bytes = b""
    normalized_media_type = (media_type or "").strip() or infer_media_type(normalized_name, normalized_path, content, file_bytes)
    stored_content, text_extracted = extract_file_content(
        normalized_name,
        normalized_media_type,
        file_bytes,
        content,
    )
    size_bytes = len(file_bytes)
    summary = summarize_for_file(normalized_name, normalized_description, stored_content, normalized_media_type, size_bytes)
    normalized_description = summary or normalized_description
    content_hash = hashlib.sha256(file_bytes or normalized_name.encode("utf-8")).hexdigest()
    existing = db.execute("SELECT * FROM library_files WHERE content_hash = ?", (content_hash,)).fetchone()
    now = utc_now()
    storage_path = ensure_stored_file(content_hash, normalized_name, file_bytes) if file_bytes else None
    if existing:
        db.execute(
            """
            UPDATE library_files
            SET name = ?, description = ?, summary = ?,
                media_type = COALESCE(?, media_type), source_path = COALESCE(?, source_path),
                storage_path = COALESCE(?, storage_path), size_bytes = MAX(size_bytes, ?),
                text_extracted = ?, content = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                normalized_name,
                normalized_description,
                summary,
                normalized_media_type,
                normalized_path,
                storage_path,
                size_bytes,
                int(text_extracted),
                stored_content,
                now,
                existing["id"],
            ),
        )
        item = get_file(db, existing["id"])
    else:
        file_id = graph_store.new_id("file")
        db.execute(
            """
            INSERT INTO library_files
            (id,name,description,summary,media_type,source_path,storage_path,size_bytes,text_extracted,content,content_hash,linked_node_ids,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                file_id,
                normalized_name,
                normalized_description,
                summary,
                normalized_media_type,
                normalized_path,
                storage_path,
                size_bytes,
                int(text_extracted),
                stored_content,
                content_hash,
                dumps([]),
                now,
                now,
            ),
        )
        item = get_file(db, file_id)
    upsert_file_vector(db, item)
    schedule_library_summary("file", item["id"], normalized_name, normalized_description, stored_content)
    entry = create_or_update_entry(
        db,
        title=item["name"],
        description=item.get("description"),
        content=item.get("content") or "",
        kind="file",
        source_file_id=item["id"],
        actor=actor,
    )
    db.execute(
        "UPDATE library_entries SET metadata = ? WHERE id = ?",
        (
            dumps(
                {
                    "media_type": item.get("media_type"),
                    "source_path": item.get("source_path"),
                    "file_id": item.get("id"),
                    "download_url": f"/files/{item['id']}/download",
                    "size_bytes": item.get("size_bytes") or 0,
                    "text_extracted": bool(item.get("text_extracted")),
                }
            ),
            entry["id"],
        ),
    )
    graph_store.append_event(db, "LibraryFileUpserted", actor, {"file_id": item["id"], "name": item["name"]})
    return get_file(db, item["id"]) or item


def get_file_storage_path(item: dict[str, Any]) -> Path | None:
    storage_path = str(item.get("storage_path") or "").strip()
    if not storage_path:
        return None
    path = Path(storage_path)
    if not path.is_absolute():
        path = get_settings().file_storage_path / path
    try:
        path.relative_to(get_settings().file_storage_path.resolve())
    except ValueError:
        return None
    return path if path.exists() and path.is_file() else None


def ensure_stored_file(content_hash: str, name: str, data: bytes) -> str:
    storage_root = get_settings().file_storage_path
    storage_root.mkdir(parents=True, exist_ok=True)
    suffix = safe_suffix(name)
    filename = f"{content_hash[:16]}{suffix}"
    path = storage_root / filename
    if not path.exists():
        path.write_bytes(data)
    return filename


def safe_suffix(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if not suffix or len(suffix) > 16 or not re.fullmatch(r"\.[a-z0-9][a-z0-9._-]*", suffix):
        return ".bin"
    return suffix


def sync_node_file_attachments(db: sqlite3.Connection, attachments: list[dict[str, Any]], node_id: str | None = None) -> list[dict[str, Any]]:
    synced: list[dict[str, Any]] = []
    linked_ids: list[str] = []
    for attachment in attachments:
        file_id = str(attachment.get("file_id") or "").strip()
        linked = get_file(db, file_id) if file_id else None
        if not linked:
            linked = create_or_reuse_file(
                db,
                name=str(attachment.get("name") or "文件"),
                description=attachment_summary(attachment) or None,
                media_type=str(attachment.get("media_type") or "") or None,
                source_path=str(attachment.get("path") or "") or None,
                content=str(attachment.get("content") or "") or None,
                actor="system",
            )
        linked_ids.append(linked["id"])
        synced.append(
            {
                "id": str(attachment.get("id") or linked["id"]),
                "file_id": linked["id"],
                "name": str(attachment.get("name") or linked["name"]),
                "path": linked.get("source_path") or "",
                "description": str(attachment_summary(attachment) or linked.get("summary") or linked.get("description") or ""),
                "content": str(linked.get("content") or ""),
                "summary": str(attachment_summary(attachment) or linked.get("summary") or ""),
                "media_type": str(attachment.get("media_type") or linked.get("media_type") or ""),
                "download_url": f"/files/{linked['id']}/download",
                "size_bytes": int(linked.get("size_bytes") or 0),
                "text_extracted": bool(linked.get("text_extracted")),
            }
        )
    update_linked_nodes_for_files(db, linked_ids, node_id)
    return synced


def sync_node_database_attachments(db: sqlite3.Connection, attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    synced: list[dict[str, Any]] = []
    for attachment in attachments:
        entry_id = str(attachment.get("entry_id") or "").strip()
        linked = get_entry(db, entry_id) if entry_id else None
        if not linked:
            kind = str(attachment.get("kind") or "").strip()
            file_id = str(attachment.get("file_id") or "").strip()
            linked_file = get_file(db, file_id) if file_id else None
            if kind == "file" or linked_file:
                if not linked_file:
                    linked_file = create_or_reuse_file(
                        db,
                        name=str(attachment.get("name") or "文件"),
                        description=attachment_summary(attachment) or None,
                        media_type=str(attachment.get("media_type") or "") or None,
                        source_path=str(attachment.get("path") or "") or None,
                        content=str(attachment.get("content") or "") or None,
                        actor="system",
                    )
                linked = create_or_update_entry(
                    db,
                    title=str(attachment.get("name") or linked_file["name"]),
                    description=attachment_summary(attachment) or linked_file.get("summary") or linked_file.get("description") or None,
                    content=str(linked_file.get("content") or ""),
                    kind="file",
                    source_file_id=linked_file["id"],
                    actor="system",
                )
            else:
                linked = create_or_update_entry(
                    db,
                    title=str(attachment.get("name") or "知识条目"),
                    description=attachment_summary(attachment) or None,
                    content=str(attachment.get("content") or ""),
                    kind="text",
                    actor="system",
                )
        synced.append(
            {
                "id": str(attachment.get("id") or linked["id"]),
                "entry_id": linked["id"],
                "kind": str(linked.get("kind") or "text"),
                "file_id": str(linked.get("source_file_id") or attachment.get("file_id") or ""),
                "name": str(attachment.get("name") or linked["title"]),
                "description": str(attachment_summary(attachment) or linked.get("summary") or linked.get("description") or ""),
                "content": str(linked.get("content") or ""),
                "summary": str(attachment_summary(attachment) or linked.get("summary") or ""),
                "media_type": str(attachment.get("media_type") or linked.get("metadata", {}).get("media_type") or ""),
                "path": str(attachment.get("path") or linked.get("metadata", {}).get("source_path") or ""),
                "download_url": f"/files/{linked.get('source_file_id')}/download" if linked.get("source_file_id") else "",
                "size_bytes": int(linked.get("metadata", {}).get("size_bytes") or 0),
                "text_extracted": bool(linked.get("metadata", {}).get("text_extracted", True)),
            }
        )
    return synced


def update_linked_nodes_for_files(db: sqlite3.Connection, file_ids: list[str], node_id: str | None) -> None:
    if not file_ids:
        return
    for file_id in file_ids:
        item = get_file(db, file_id)
        if not item:
            continue
        linked = set(item.get("linked_node_ids") or [])
        if node_id:
            linked.add(node_id)
        db.execute("UPDATE library_files SET linked_node_ids = ? WHERE id = ?", (dumps(sorted(linked)), file_id))


def summarize_for_library(title: str, description: str | None, content: str) -> str:
    if description:
        return compact_text(description, 240)
    return compact_text(" ".join(part for part in [title, content] if part), 240)


def summarize_for_file(title: str, description: str | None, content: str, media_type: str, size_bytes: int) -> str:
    if description:
        return compact_text(description, 240)
    if content.strip():
        return summarize_for_library(title, None, content)
    size = format_size(size_bytes)
    return compact_text(f"{title}（{media_type or 'unknown'}，{size}）。非文本文件仅保存文件元数据和摘要，可下载原文件访问。", 240)


def schedule_library_summary(item_type: str, item_id: str, title: str, description: str | None, content: str) -> None:
    if not content.strip() and description:
        return

    def worker() -> None:
        time.sleep(0.2)
        summary = llm.summarize_library_item(title, description or "", content)
        if not summary:
            return
        with get_db() as db:
            table = "library_entries" if item_type == "entry" else "library_files"
            id_column = "id"
            db.execute(f"UPDATE {table} SET summary = ?, description = ?, updated_at = ? WHERE {id_column} = ?", (summary, summary, utc_now(), item_id))
            if item_type == "entry":
                item = get_entry(db, item_id)
                upsert_entry_vector(db, item)
            else:
                item = get_file(db, item_id)
                upsert_file_vector(db, item)

    threading.Thread(target=worker, name=f"library-summary-{item_type}-{item_id}", daemon=True).start()


def compact_text(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def attachment_summary(attachment: dict[str, Any]) -> str:
    return str(attachment.get("summary") or attachment.get("description") or "").strip()


def infer_media_type(name: str, source_path: str | None, content: str | None, raw_bytes: bytes | None = None) -> str:
    guessed, _ = mimetypes.guess_type(source_path or name)
    if guessed:
        return guessed
    suffix = Path(source_path or name).suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return "text/plain"
    if content:
        return "text/plain"
    if raw_bytes and is_probably_utf8(raw_bytes):
        return "text/plain"
    return "application/octet-stream"


def is_text_file(name: str, media_type: str | None, data: bytes) -> bool:
    normalized_media_type = (media_type or "").split(";", 1)[0].strip().lower()
    if normalized_media_type.startswith(TEXT_MEDIA_PREFIXES) or normalized_media_type in TEXT_MEDIA_TYPES:
        return True
    if Path(name).suffix.lower() in TEXT_SUFFIXES:
        return True
    return is_probably_utf8(data)


def is_probably_utf8(data: bytes) -> bool:
    if not data:
        return True
    sample = data[:8192]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def decode_text_content(data: bytes) -> str:
    if not data:
        return ""
    return data.decode("utf-8", errors="replace")


def extract_file_content(
    name: str,
    media_type: str | None,
    data: bytes,
    explicit_content: str | None = None,
) -> tuple[str, bool]:
    if explicit_content is not None:
        return explicit_content, True
    extraction = document_extractors.extract_text(name, media_type, data)
    if extraction is not None:
        return extraction.text, bool(extraction.text.strip())
    text_extracted = is_text_file(name, media_type, data)
    if text_extracted:
        return decode_text_content(data), True
    return "", False


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def row_to_library_file(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["linked_node_ids"] = loads(item.get("linked_node_ids"), [])
    item["text_extracted"] = bool(item.get("text_extracted"))
    item["download_url"] = f"/files/{item['id']}/download"
    return item


def row_to_library_entry(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["metadata"] = loads(item.get("metadata"), {})
    return item


def upsert_entry_vector(db: sqlite3.Connection, item: dict[str, Any] | None) -> None:
    if not item:
        return
    text = library_entry_vector_text(item)
    upsert_vector(db, item_id=item["id"], item_type="entry", text=text, content_hash=item.get("content_hash") or "")


def upsert_file_vector(db: sqlite3.Connection, item: dict[str, Any] | None) -> None:
    if not item:
        return
    text = "\n".join(
        part
        for part in [
            str(item.get("name") or ""),
            str(item.get("description") or ""),
            str(item.get("summary") or ""),
            str(item.get("content") or ""),
        ]
        if part
    )
    upsert_vector(db, item_id=item["id"], item_type="file", text=text, content_hash=item.get("content_hash") or "")


def upsert_vector(db: sqlite3.Connection, *, item_id: str, item_type: str, text: str, content_hash: str) -> None:
    embedding = text_embedding(text)
    db.execute(
        """
        INSERT INTO library_vectors (item_id,item_type,embedding,content_hash,updated_at)
        VALUES (?,?,?,?,?)
        ON CONFLICT(item_id) DO UPDATE SET
          item_type = excluded.item_type,
          embedding = excluded.embedding,
          content_hash = excluded.content_hash,
          updated_at = excluded.updated_at
        """,
        (item_id, item_type, dumps(embedding), content_hash, utc_now()),
    )


def search_entries_by_vector(
    db: sqlite3.Connection,
    *,
    query: str,
    kind: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    query_embedding = text_embedding(query)
    rows = db.execute(
        """
        SELECT e.*, v.embedding
        FROM library_entries e
        JOIN library_vectors v ON v.item_id = e.id AND v.item_type = 'entry'
        WHERE (? IS NULL OR e.kind = ?)
        """,
        (kind, kind),
    ).fetchall()
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        item = row_to_library_entry(row)
        score = cosine_similarity(query_embedding, loads(row["embedding"], []))
        if score > 0:
            item["search_score"] = score
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[: max(1, min(limit, 100))]]


def library_entry_vector_text(item: dict[str, Any]) -> str:
    return "\n".join(
        part
        for part in [
            str(item.get("title") or ""),
            str(item.get("description") or ""),
            str(item.get("summary") or ""),
            str(item.get("content") or ""),
        ]
        if part
    )


def text_embedding(text: str) -> list[float]:
    vector = [0.0] * VECTOR_DIMENSIONS
    for token in TOKEN_PATTERN.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % VECTOR_DIMENSIONS
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))
