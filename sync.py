"""Auto-sync: SQLite -> MariaDB every N minutes."""

import logging
import time
import threading

import config
import db_local
import db_mariadb

logger = logging.getLogger("hermes-zalo.sync")

_sync_thread: threading.Thread | None = None
_stop_event = threading.Event()
_mariadb_available = False


def check_mariadb() -> bool:
    """Check if MariaDB is configured and reachable. Returns True if available."""
    global _mariadb_available

    # Skip if no config
    if not config.MARIADB_HOST or not config.MARIADB_USER or not config.MARIADB_PASSWORD:
        logger.info("[SYNC] MariaDB chưa cấu hình - bỏ qua sync")
        _mariadb_available = False
        return False

    try:
        db_mariadb.init_tables()
        stats = db_mariadb.get_stats()
        logger.info(f"[SYNC] MariaDB sẵn sàng - {stats['total']} records")
        _mariadb_available = True
        return True
    except Exception as e:
        logger.warning(f"[SYNC] MariaDB không khả dụng: {e}")
        _mariadb_available = False
        return False


def is_available() -> bool:
    """Check if MariaDB sync is available."""
    return _mariadb_available


def do_sync() -> dict:
    """Run one sync cycle. Returns stats dict."""
    global _mariadb_available

    if not _mariadb_available:
        return {"total": 0, "inserted": 0, "errors": 0, "skipped": True}

    logger.info("[SYNC] Bắt đầu đồng bộ dữ liệu...")

    unsynced = db_local.get_unsynced_messages(limit=1000)
    if not unsynced:
        logger.info("[SYNC] Không có dữ liệu mới")
        return {"total": 0, "inserted": 0, "errors": 0}

    rows = []
    ids = []
    for row in unsynced:
        ids.append(row["id"])
        rows.append((
            row["thread_id"],
            row["msg_id"],
            row["sender_id"],
            row["sender_name"],
            row["content"],
            row["msg_type"],
            row["chat_type"],
            row["timestamp"],
            row["timestamp_ms"],
            row["is_from_self"],
            row["raw_json"],
        ))

    errors = 0
    try:
        inserted = db_mariadb.insert_messages(rows)
    except Exception as e:
        logger.error(f"[SYNC] MariaDB insert error: {e}")
        inserted = 0
        errors = len(rows)
        # MariaDB went down - mark as unavailable
        _mariadb_available = False

    if inserted > 0:
        db_local.mark_synced(ids)

    stats = {
        "total": len(unsynced),
        "inserted": inserted,
        "errors": errors,
    }
    logger.info(
        f"[SYNC] Hoàn tất - total={stats['total']} "
        f"inserted={stats['inserted']} errors={stats['errors']}"
    )
    return stats


def _sync_loop():
    """Background sync loop."""
    interval = config.SYNC_INTERVAL_MINUTES * 60
    logger.info(f"[AUTO-SYNC] Thread khởi động - interval={config.SYNC_INTERVAL_MINUTES} phút")

    # Initial sync after 10 seconds
    time.sleep(10)

    while not _stop_event.is_set():
        try:
            do_sync()
        except Exception as e:
            logger.error(f"[AUTO-SYNC] Lỗi: {e}")

        _stop_event.wait(interval)


def start():
    """Start the background sync thread."""
    global _sync_thread
    if _sync_thread is None or not _sync_thread.is_alive():
        _stop_event.clear()
        _sync_thread = threading.Thread(target=_sync_loop, daemon=True, name="auto-sync")
        _sync_thread.start()


def stop():
    """Stop the background sync thread."""
    _stop_event.set()
    logger.info("[AUTO-SYNC] Dừng")
