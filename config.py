"""Hermes-Zalo configuration - loaded from environment."""

import os
import json

# ─── Zalo / OpenZCA ───────────────────────────────────────────────────────────
OPENZCA_BIN = os.getenv("OPENZCA_BIN", "openzca")

# Multi-profile support: comma-separated list of profile names
# Example: OPENZCA_PROFILES="personal,work,shop"
_profiles_env = os.getenv("OPENZCA_PROFILES", os.getenv("OPENZCA_PROFILE", "default"))
OPENZCA_PROFILES = [p.strip() for p in _profiles_env.split(",") if p.strip()]

# Per-profile config: {"profile_name": {"own_id": "...", "label": "..."}}
# Can be set via PROFILES_CONFIG env var (JSON) or auto-detected
_profiles_config_raw = os.getenv("PROFILES_CONFIG", "{}")
try:
    PROFILES_CONFIG = json.loads(_profiles_config_raw)
except json.JSONDecodeError:
    PROFILES_CONFIG = {}

# Legacy single profile support
OPENZCA_PROFILE = os.getenv("OPENZCA_PROFILE", OPENZCA_PROFILES[0] if OPENZCA_PROFILES else "default")
OWN_ID = os.getenv("OWN_ID", "")  # Legacy single own_id

def get_profile_config(profile: str) -> dict:
    """Get config for a specific profile."""
    return PROFILES_CONFIG.get(profile, {})

def get_own_id(profile: str = None) -> str:
    """Get own ID for a profile, falling back to global."""
    if profile:
        pc = get_profile_config(profile)
        return pc.get("own_id", "")
    return OWN_ID

def set_own_id(profile: str, own_id: str):
    """Set own ID for a profile (runtime)."""
    if profile not in PROFILES_CONFIG:
        PROFILES_CONFIG[profile] = {}
    PROFILES_CONFIG[profile]["own_id"] = own_id

# ─── Hermes Bridge ────────────────────────────────────────────────────────────
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://localhost:5000/chat")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
HERMES_TIMEOUT = int(os.getenv("HERMES_TIMEOUT", "60"))

# ─── SQLite (local cache) ─────────────────────────────────────────────────────
SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.expanduser("~/.hermes-zalo/hermes_zalo.db"))

# ─── MariaDB ──────────────────────────────────────────────────────────────────
MARIADB_HOST = os.getenv("MARIADB_HOST", "localhost")
MARIADB_PORT = int(os.getenv("MARIADB_PORT", "3306"))
MARIADB_USER = os.getenv("MARIADB_USER", "hermes_zalo")
MARIADB_PASSWORD = os.getenv("MARIADB_PASSWORD", "")
MARIADB_DATABASE = os.getenv("MARIADB_DATABASE", "hermes_zalo")

# ─── Auto-Sync ────────────────────────────────────────────────────────────────
SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "15"))

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
