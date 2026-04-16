"""MariaDB remote database - persistent storage for chat logs."""

import json
import logging
import time
from typing import Optional, Dict, Any, List, Tuple

import config

logger = logging.getLogger("hermes-zalo.db_mariadb")

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        try:
            import mariadb
        except ImportError:
            raise ImportError(
                "mariadb package not installed. Run: pip install mariadb\n"
                "Also needs libmariadb-dev: apt install libmariadb-dev"
            )
        _pool = mariadb.connect(
            host=config.MARIADB_HOST,
            port=config.MARIADB_PORT,
            user=config.MARIADB_USER,
            password=config.MARIADB_PASSWORD,
            database=config.MARIADB_DATABASE,
            autocommit=False,
            pool_name="hermes_zalo_pool",
            pool_size=5,
        )
        logger.info(f"[MARIADB] Kết nối thành công tới {config.MARIADB_DATABASE}")
    return _pool


def get_conn():
    return _get_pool()


def init_tables():
    """Create tables if they don't exist."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            thread_id VARCHAR(64) NOT NULL,
            msg_id VARCHAR(64),
            sender_id VARCHAR(64) NOT NULL,
            sender_name VARCHAR(255),
            content TEXT NOT NULL,
            msg_type VARCHAR(32) DEFAULT 'text',
            chat_type VARCHAR(16) DEFAULT 'user',
            timestamp BIGINT,
            timestamp_ms BIGINT,
            is_from_self TINYINT(1) DEFAULT 0,
            raw_json LONGTEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_thread (thread_id),
            INDEX idx_sender (sender_id),
            INDEX idx_ts (timestamp_ms),
            INDEX idx_chat_type (chat_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            `key` VARCHAR(128) PRIMARY KEY,
            `value` TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conn.commit()
    logger.info("[MARIADB] Tables initialized")


def insert_messages(rows: List[Tuple]) -> int:
    """Batch insert messages. Returns number of rows inserted.

    Each row tuple: (thread_id, msg_id, sender_id, sender_name,
                     content, msg_type, chat_type, timestamp, timestamp_ms,
                     is_from_self, raw_json)
    """
    if not rows:
        return 0

    conn = get_conn()
    cursor = conn.cursor()

    cursor.executemany("""
        INSERT INTO chat_logs
            (thread_id, msg_id, sender_id, sender_name, content,
             msg_type, chat_type, timestamp, timestamp_ms,
             is_from_self, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    count = cursor.rowcount
    logger.debug(f"[MARIADB] Inserted {count} rows")
    return count


def insert_single(data: Dict[str, Any]) -> int:
    """Insert a single message directly (for real-time writes)."""
    import db_local
    is_from_self = 1 if str(data.get("senderId", "")) == config.OWN_ID else 0

    return insert_messages([(
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
    )])


def get_total_count() -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chat_logs")
    return cursor.fetchone()[0]


def get_stats() -> Dict[str, Any]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chat_logs")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE chat_type = 'user'")
    dm = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE chat_type = 'group'")
    group = cursor.fetchone()[0]
    return {"total": total, "dm": dm, "group": group}
