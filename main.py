#!/usr/bin/env python3
"""BearGate - Zalo <-> Hermes Gateway with MariaDB storage (multi-account)."""

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

    profiles = config.OPENZCA_PROFILES
    logger.info(f"=== BearGate khởi động ({len(profiles)} Zalo accounts) ===")
    for p in profiles:
        label = config.get_profile_config(p).get("label", "")
        logger.info(f"  📱 Profile: {p}" + (f" ({label})" if label else ""))

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

    # Start auto-sync
    sync.start()

    # Start all listeners (multi-account)
    logger.info(f"[INIT] Khởi động {len(profiles)} Zalo listeners...")
    listener.start_all()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()
