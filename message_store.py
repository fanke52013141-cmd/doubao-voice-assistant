"""Persistent PC-to-phone messages and downloadable attachments."""
from __future__ import annotations

import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


MESSAGE_RETENTION_SECONDS = 30 * 24 * 60 * 60
MAX_SHARED_FILE_BYTES = 2 * 1024 * 1024 * 1024


def data_root() -> Path:
    root = Path(os.environ.get("APPDATA", os.path.dirname(os.path.abspath(__file__)))) / "VoiceInputAssistant"
    root.mkdir(parents=True, exist_ok=True)
    return root


def shared_file_dir() -> Path:
    path = data_root() / "shared-files"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return data_root() / "phone-messages.sqlite3"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path(), timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY,
            message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            size INTEGER NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
        CREATE INDEX IF NOT EXISTS idx_attachments_message_id ON attachments(message_id);
        """
    )
    return connection


@contextmanager
def database():
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _attachment_dict(row: sqlite3.Row) -> dict:
    attachment_id = row["id"]
    return {
        "id": attachment_id,
        "name": row["original_name"],
        "type": row["mime_type"],
        "size": row["size"],
        "view_url": f"/api/files/{attachment_id}",
        "download_url": f"/api/files/{attachment_id}?download=1",
    }


def _message_dict(connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
    attachment_rows = connection.execute(
        "SELECT * FROM attachments WHERE message_id = ? ORDER BY rowid",
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "direction": "pc_to_phone",
        "text": row["text"],
        "created_at": int(row["created_at"] * 1000),
        "attachments": [_attachment_dict(item) for item in attachment_rows],
    }


def create_message(text: str, saved_attachments: list[dict]) -> dict:
    now = time.time()
    with database() as connection:
        cursor = connection.execute(
            "INSERT INTO messages(text, created_at) VALUES (?, ?)",
            (text or "", now),
        )
        message_id = cursor.lastrowid
        for attachment in saved_attachments:
            connection.execute(
                """
                INSERT INTO attachments(
                    id, message_id, original_name, stored_name, mime_type, size, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attachment["id"], message_id, attachment["name"], attachment["stored_name"],
                    attachment["type"], attachment["size"], now,
                ),
            )
        row = connection.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        return _message_dict(connection, row)


def list_messages(after_id: int = 0, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    after_id = max(0, int(after_id))
    with database() as connection:
        if after_id:
            rows = connection.execute(
                "SELECT * FROM messages WHERE id > ? ORDER BY id ASC LIMIT ?",
                (after_id, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()[::-1]
        return [_message_dict(connection, row) for row in rows]


def attachment_file(attachment_id: str) -> dict | None:
    with database() as connection:
        row = connection.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
        if not row:
            return None
        path = (shared_file_dir() / row["stored_name"]).resolve()
        try:
            path.relative_to(shared_file_dir().resolve())
        except ValueError:
            return None
        if not path.is_file():
            return None
        return {
            "path": path,
            "name": row["original_name"],
            "type": row["mime_type"],
            "size": row["size"],
        }


def allocate_file_name(original_name: str) -> tuple[str, Path]:
    suffix = Path(original_name or "").suffix.lower()[:12]
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    return stored_name, shared_file_dir() / stored_name


def cleanup_messages() -> None:
    cutoff = time.time() - MESSAGE_RETENTION_SECONDS
    with database() as connection:
        expired = connection.execute(
            "SELECT stored_name FROM attachments WHERE message_id IN "
            "(SELECT id FROM messages WHERE created_at < ?)",
            (cutoff,),
        ).fetchall()
        connection.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))
    for row in expired:
        try:
            (shared_file_dir() / row["stored_name"]).unlink(missing_ok=True)
        except OSError:
            pass

    with database() as connection:
        rows = connection.execute(
            "SELECT id, stored_name, size FROM attachments ORDER BY created_at DESC"
        ).fetchall()
        total = 0
        remove_ids = []
        remove_names = []
        for row in rows:
            total += row["size"]
            if total > MAX_SHARED_FILE_BYTES:
                remove_ids.append(row["id"])
                remove_names.append(row["stored_name"])
        if remove_ids:
            connection.executemany("DELETE FROM attachments WHERE id = ?", [(item,) for item in remove_ids])
    for name in remove_names:
        try:
            (shared_file_dir() / name).unlink(missing_ok=True)
        except OSError:
            pass
