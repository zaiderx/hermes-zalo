"""SQLite local database - fast local storage for chat logs."""

import os
import sqlite3
import json
import time
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

import config

logger = logging.getLogger("beargate.db_local")

_conn: Optional[sqlite3.Connection] = None


def _ensure_dir():
    os.makedirs(os.path.dirname(config.SQLITE_PATH), exist_ok=True)


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _ensure_dir()
        _conn = sqlite3.connect(config.SQLITE_PATH)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _create_tables()
    return _conn


def _create_tables():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            msg_id TEXT,
            sender_id TEXT NOT NULL,
            sender_name TEXT,
            content TEXT NOT NULL,
            msg_type TEXT DEFAULT 'text',
            chat_type TEXT DEFAULT 'user',
            timestamp INTEGER,
            timestamp_ms INTEGER,
            is_from_self INTEGER DEFAULT 0,
            raw_json TEXT,
            synced INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_chat_logs_thread ON chat_logs(thread_id);
        CREATE INDEX IF NOT EXISTS idx_chat_logs_synced ON chat_logs(synced);
        CREATE INDEX IF NOT EXISTS idx_chat_logs_ts ON chat_logs(timestamp_ms);

        CREATE TABLE IF NOT EXISTS sync_state (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()


@contextmanager
def transaction():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def insert_message(data: Dict[str, Any]) -> int:
    """Insert a message into local SQLite. Returns row id."""
    conn = get_conn()
    now = time.time()
    is_from_self = 1 if str(data.get("senderId", "")) == config.OWN_ID else 0

    cursor = conn.execute("""
        INSERT INTO chat_logs
            (thread_id, msg_id, sender_id, sender_name, content,
             msg_type, chat_type, timestamp, timestamp_ms,
             is_from_self, raw_json, synced, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (
        str(data.get("threadId", "")),
        str(data.get("msgId", "")),
        str(data.get("senderId", "")),
        data.get("senderName") or data.get("senderDisplayName"),
        data.get("content", ""),
        data.get("msgType", "text"),
        data.get("chatType", "user"),
        data.get("timestamp"),
        data.get("ts") or data.get("timestampMs"),
        is_from_self,
        json.dumps(data, ensure_ascii=False),
        now,
    ))
    conn.commit()
    return cursor.lastrowid


def get_unsynced_messages(limit: int = 500) -> List[sqlite3.Row]:
    """Get messages not yet synced to MariaDB."""
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM chat_logs WHERE synced = 0 ORDER BY id ASC LIMIT ?",
        (limit,)
    ).fetchall()


def mark_synced(ids: List[int]):
    """Mark messages as synced."""
    if not ids:
        return
    conn = get_conn()
    placeholders = ",".join("?" * len(ids))
    conn.execute(
        f"UPDATE chat_logs SET synced = 1 WHERE id IN ({placeholders})",
        ids
    )
    conn.commit()


def get_stats() -> Dict[str, int]:
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM chat_logs").fetchone()[0]
    unsynced = conn.execute("SELECT COUNT(*) FROM chat_logs WHERE synced = 0").fetchone()[0]
    return {"total": total, "unsynced": unsynced}
