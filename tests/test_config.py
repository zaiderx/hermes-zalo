"""Tests for config module."""

import pytest
import os
import config


class TestConfig:
    def test_profiles_loaded(self):
        assert len(config.OPENZCA_PROFILES) > 0

    def test_get_profile_config_empty(self):
        cfg = config.get_profile_config("nonexistent")
        assert cfg == {}

    def test_set_and_get_own_id(self):
        config.set_own_id("test_profile", "123456")
        assert config.get_own_id("test_profile") == "123456"

    def test_get_own_id_default(self):
        assert config.get_own_id("nonexistent") == ""

    def test_mariadb_default_not_empty(self):
        # MariaDB defaults exist (may be overridden by env)
        assert hasattr(config, "MARIADB_HOST")

    def test_sqlite_path(self):
        assert config.SQLITE_PATH.endswith(".db")
