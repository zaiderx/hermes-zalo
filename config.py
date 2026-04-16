"""BearGate configuration - loaded from environment."""

import os

# ─── Zalo / OpenZCA ───────────────────────────────────────────────────────────
OPENZCA_PROFILE = os.getenv("OPENZCA_PROFILE", "default")
OPENZCA_BIN = os.getenv("OPENZCA_BIN", "openzca")
OWN_ID = os.getenv("OWN_ID", "")  # Self-ID to filter own messages

# ─── Hermes Bridge ────────────────────────────────────────────────────────────
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://localhost:5000/chat")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
HERMES_TIMEOUT = int(os.getenv("HERMES_TIMEOUT", "60"))

# ─── SQLite (local cache) ─────────────────────────────────────────────────────
SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.expanduser("~/.beargate/beargate.db"))

# ─── MariaDB ──────────────────────────────────────────────────────────────────
MARIADB_HOST = os.getenv("MARIADB_HOST", "localhost")
MARIADB_PORT = int(os.getenv("MARIADB_PORT", "3306"))
MARIADB_USER = os.getenv("MARIADB_USER", "beargate")
MARIADB_PASSWORD = os.getenv("MARIADB_PASSWORD", "")
MARIADB_DATABASE = os.getenv("MARIADB_DATABASE", "beargate")

# ─── Auto-Sync ────────────────────────────────────────────────────────────────
SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "15"))

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
