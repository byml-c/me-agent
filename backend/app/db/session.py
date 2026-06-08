from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.core.config import get_settings


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def dict_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or get_settings().database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              body TEXT NOT NULL DEFAULT '',
              summary TEXT,
              memory TEXT NOT NULL DEFAULT '{}',
              is_workspace INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'active',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              last_accessed_at TEXT,
              access_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS edges (
              id TEXT PRIMARY KEY,
              node_a_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
              node_b_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
              weight REAL NOT NULL DEFAULT 1.0,
              access_count INTEGER NOT NULL DEFAULT 0,
              coactivation_count INTEGER NOT NULL DEFAULT 0,
              is_candidate INTEGER NOT NULL DEFAULT 0,
              created_by TEXT NOT NULL DEFAULT 'user',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              last_accessed_at TEXT,
              UNIQUE(node_a_id, node_b_id),
              CHECK(node_a_id < node_b_id)
            );

            CREATE TABLE IF NOT EXISTS events (
              id TEXT PRIMARY KEY,
              type TEXT NOT NULL,
              actor TEXT NOT NULL,
              payload TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS proposals (
              id TEXT PRIMARY KEY,
              operation TEXT NOT NULL,
              target_ids TEXT NOT NULL,
              payload TEXT NOT NULL,
              reason TEXT NOT NULL,
              confidence REAL NOT NULL,
              risk_level TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              created_at TEXT NOT NULL,
              resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              current_anchor_node_ids TEXT NOT NULL DEFAULT '[]',
              current_workspace_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              context_node_ids TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL
            );
            """
        )
