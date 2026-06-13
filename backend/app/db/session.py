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
              UNIQUE(node_a_id, node_b_id)
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

            CREATE TABLE IF NOT EXISTS library_files (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              description TEXT,
              summary TEXT,
              media_type TEXT,
              source_path TEXT,
              storage_path TEXT,
              size_bytes INTEGER NOT NULL DEFAULT 0,
              text_extracted INTEGER NOT NULL DEFAULT 1,
              content TEXT NOT NULL DEFAULT '',
              content_hash TEXT NOT NULL UNIQUE,
              linked_node_ids TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS library_entries (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              kind TEXT NOT NULL DEFAULT 'text',
              description TEXT,
              content TEXT NOT NULL DEFAULT '',
              summary TEXT,
              source_file_id TEXT REFERENCES library_files(id) ON DELETE SET NULL,
              content_hash TEXT NOT NULL UNIQUE,
              metadata TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS library_vectors (
              item_id TEXT PRIMARY KEY,
              item_type TEXT NOT NULL,
              embedding TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        ensure_chat_message_columns(db)
        ensure_directed_edges_schema(db)
        ensure_library_file_columns(db)
        ensure_library_entry_columns(db)
        ensure_library_vector_table(db)


def ensure_directed_edges_schema(db: sqlite3.Connection) -> None:
    table = db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'edges'").fetchone()
    if not table or "CHECK(node_a_id < node_b_id)" not in (table["sql"] or ""):
        return
    db.executescript(
        """
        PRAGMA foreign_keys = OFF;
        CREATE TABLE edges_directed_migration (
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
          UNIQUE(node_a_id, node_b_id)
        );
        INSERT INTO edges_directed_migration
          (id,node_a_id,node_b_id,weight,access_count,coactivation_count,is_candidate,created_by,created_at,updated_at,last_accessed_at)
        SELECT
          id,node_a_id,node_b_id,weight,access_count,coactivation_count,is_candidate,created_by,created_at,updated_at,last_accessed_at
        FROM edges;
        DROP TABLE edges;
        ALTER TABLE edges_directed_migration RENAME TO edges;
        PRAGMA foreign_keys = ON;
        """
    )


def ensure_chat_message_columns(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(chat_messages)").fetchall()}
    migrations = {
        "parent_message_id": "ALTER TABLE chat_messages ADD COLUMN parent_message_id TEXT",
        "source_message_id": "ALTER TABLE chat_messages ADD COLUMN source_message_id TEXT",
        "variant_index": "ALTER TABLE chat_messages ADD COLUMN variant_index INTEGER NOT NULL DEFAULT 0",
        "status": "ALTER TABLE chat_messages ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
        "updated_at": "ALTER TABLE chat_messages ADD COLUMN updated_at TEXT",
        "provider_response_id": "ALTER TABLE chat_messages ADD COLUMN provider_response_id TEXT",
        "token_usage": "ALTER TABLE chat_messages ADD COLUMN token_usage TEXT",
    }
    for column, sql in migrations.items():
        if column not in columns:
            db.execute(sql)
    db.execute("UPDATE chat_messages SET updated_at = created_at WHERE updated_at IS NULL")


def ensure_library_file_columns(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(library_files)").fetchall()}
    migrations = {
        "description": "ALTER TABLE library_files ADD COLUMN description TEXT",
        "summary": "ALTER TABLE library_files ADD COLUMN summary TEXT",
        "media_type": "ALTER TABLE library_files ADD COLUMN media_type TEXT",
        "source_path": "ALTER TABLE library_files ADD COLUMN source_path TEXT",
        "storage_path": "ALTER TABLE library_files ADD COLUMN storage_path TEXT",
        "size_bytes": "ALTER TABLE library_files ADD COLUMN size_bytes INTEGER NOT NULL DEFAULT 0",
        "text_extracted": "ALTER TABLE library_files ADD COLUMN text_extracted INTEGER NOT NULL DEFAULT 1",
        "content": "ALTER TABLE library_files ADD COLUMN content TEXT NOT NULL DEFAULT ''",
        "content_hash": "ALTER TABLE library_files ADD COLUMN content_hash TEXT",
        "linked_node_ids": "ALTER TABLE library_files ADD COLUMN linked_node_ids TEXT NOT NULL DEFAULT '[]'",
        "created_at": "ALTER TABLE library_files ADD COLUMN created_at TEXT",
        "updated_at": "ALTER TABLE library_files ADD COLUMN updated_at TEXT",
    }
    for column, sql in migrations.items():
        if column not in columns:
            db.execute(sql)
    now = utc_now()
    db.execute("UPDATE library_files SET linked_node_ids = '[]' WHERE linked_node_ids IS NULL")
    db.execute("UPDATE library_files SET created_at = ? WHERE created_at IS NULL", (now,))
    db.execute("UPDATE library_files SET updated_at = created_at WHERE updated_at IS NULL")


def ensure_library_entry_columns(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(library_entries)").fetchall()}
    migrations = {
        "title": "ALTER TABLE library_entries ADD COLUMN title TEXT",
        "kind": "ALTER TABLE library_entries ADD COLUMN kind TEXT NOT NULL DEFAULT 'text'",
        "description": "ALTER TABLE library_entries ADD COLUMN description TEXT",
        "content": "ALTER TABLE library_entries ADD COLUMN content TEXT NOT NULL DEFAULT ''",
        "summary": "ALTER TABLE library_entries ADD COLUMN summary TEXT",
        "source_file_id": "ALTER TABLE library_entries ADD COLUMN source_file_id TEXT",
        "content_hash": "ALTER TABLE library_entries ADD COLUMN content_hash TEXT",
        "metadata": "ALTER TABLE library_entries ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'",
        "created_at": "ALTER TABLE library_entries ADD COLUMN created_at TEXT",
        "updated_at": "ALTER TABLE library_entries ADD COLUMN updated_at TEXT",
    }
    for column, sql in migrations.items():
        if column not in columns:
            db.execute(sql)
    now = utc_now()
    db.execute("UPDATE library_entries SET metadata = '{}' WHERE metadata IS NULL")
    db.execute("UPDATE library_entries SET created_at = ? WHERE created_at IS NULL", (now,))
    db.execute("UPDATE library_entries SET updated_at = created_at WHERE updated_at IS NULL")


def ensure_library_vector_table(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS library_vectors (
          item_id TEXT PRIMARY KEY,
          item_type TEXT NOT NULL,
          embedding TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
