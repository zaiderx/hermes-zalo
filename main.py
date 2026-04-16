#!/usr/bin/env python3
"""BearGate - Zalo <-> Hermes Gateway with MariaDB storage."""

import logging
import signal
import sys
import time

import config
import db_local
import db_mariadb
import listener
import sync

# ─── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hermes-zalo")

# ─── Own ID detection ─────────────────────────────────────────────────────────
def _detect_own_id():
    """Detect own Zalo ID if not configured."""
    if config.OWN_ID:
        return

    import subprocess
    try:
        result = subprocess.run(
            [config.OPENZCA_BIN, "--profile", config.OPENZCA_PROFILE, "me", "id"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            own_id = result.stdout.strip()
            if own_id:
                config.OWN_ID = own_id
                logger.info(f"Own ID: {own_id} (sẽ lọc tin nhắn từ chính mình)")
    except Exception as e:
        logger.warning(f"Không thể detect own ID: {e}")


# ─── Shutdown handler ─────────────────────────────────────────────────────────
def _shutdown(signum=None, frame=None):
    logger.info("Đang dừng BearGate...")
    sync.stop()
    listener.stop()
    logger.info("BearGate đã dừng. Tạm biệt!")
    sys.exit(0)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("=== BearGate khởi động ===")

    # Init databases
    logger.info("[INIT] Khởi tạo SQLite...")
    db_local.get_conn()

    logger.info("[INIT] Kết nối MariaDB...")
    try:
        db_mariadb.init_tables()
        stats = db_mariadb.get_stats()
        logger.info(f"[INIT] MariaDB ready - {stats['total']} records")
    except Exception as e:
        logger.error(f"[INIT] MariaDB connection failed: {e}")
        logger.error("[INIT] Tiếp tục với SQLite - sync sẽ retry sau")

    # Detect own ID
    _detect_own_id()

    # Start auto-sync
    sync.start()

    # Start listener (blocking)
    logger.info("[INIT] Khởi động Zalo listener...")
    listener.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()
