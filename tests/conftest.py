"""Shared test fixtures."""

import os
import sys
import tempfile
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def isolate_env(tmp_path, monkeypatch):
    """Isolate all file paths to temp directory."""
    home = tmp_path / "hermes-zalo"
    home.mkdir()

    monkeypatch.setenv("HERMES_ZALO_HOME", str(home))
    monkeypatch.setenv("SQLITE_PATH", str(home / "test.db"))
    monkeypatch.setenv("MARIADB_HOST", "")
    monkeypatch.setenv("MARIADB_USER", "")
    monkeypatch.setenv("MARIADB_PASSWORD", "")
    monkeypatch.setenv("OPENZCA_PROFILES", "test_profile")
    monkeypatch.setenv("OPENZCA_BIN", "echo")  # Mock openzca with echo

    # Redirect file paths
    import accounts
    import scheduler
    import config
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", str(home / "accounts.json"))
    monkeypatch.setattr(scheduler, "SCHEDULES_FILE", str(home / "schedules.json"))
    monkeypatch.setattr(config, "SQLITE_PATH", str(home / "test.db"))

    return home
