"""Tests for accounts module."""

import pytest
import accounts


class TestAccounts:
    def test_register_account(self):
        acc = accounts.register_account("Duy Phong", "123456", "Nguyen Van A")
        assert acc["name"] == "Duy Phong"
        assert acc["zalo_id"] == "123456"
        assert acc["display_name"] == "Nguyen Van A"
        assert acc["key"] == "duy phong"

    def test_find_account_exact(self):
        accounts.register_account("Duy Phong", "123456", "Nguyen Van A")
        found = accounts.find_account("Duy Phong")
        assert found is not None
        assert found["zalo_id"] == "123456"

    def test_find_account_case_insensitive(self):
        accounts.register_account("Duy Phong", "123456", "Nguyen Van A")
        found = accounts.find_account("duy phong")
        assert found is not None
        assert found["zalo_id"] == "123456"

    def test_find_account_partial(self):
        accounts.register_account("Duy Phong", "123456", "Nguyen Van A")
        found = accounts.find_account("duy")
        assert found is not None

    def test_find_account_not_found(self):
        found = accounts.find_account("nonexistent")
        assert found is None

    def test_list_accounts_empty(self):
        accs = accounts.list_accounts()
        assert accs == []

    def test_list_accounts(self):
        accounts.register_account("Acc1", "111", "Name1")
        accounts.register_account("Acc2", "222", "Name2")
        accs = accounts.list_accounts()
        assert len(accs) == 2

    def test_remove_account(self):
        accounts.register_account("Duy Phong", "123456", "Nguyen Van A")
        assert accounts.remove_account("Duy Phong") is True
        assert accounts.find_account("Duy Phong") is None

    def test_remove_account_not_found(self):
        assert accounts.remove_account("nonexistent") is False

    def test_update_account(self):
        accounts.register_account("Duy Phong", "123456", "Nguyen Van A")
        updated = accounts.update_account("Duy Phong", display_name="Updated Name")
        assert updated["display_name"] == "Updated Name"

    def test_get_account_count(self):
        assert accounts.get_account_count() == 0
        accounts.register_account("Acc1", "111", "Name1")
        assert accounts.get_account_count() == 1

    def test_normalize_name(self):
        assert accounts._normalize_name("  Duy Phong  ") == "duy phong"
        assert accounts._normalize_name("DUY PHONG") == "duy phong"

    def test_auto_profile_name(self):
        acc = accounts.register_account("Shop ABC", "999", "Shop")
        assert "account_" in acc["profile"]
