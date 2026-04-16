"""Account registry - maps friendly names to Zalo profiles/accounts."""

import json
import os
import logging
import time
from typing import Optional, Dict, Any, List

logger = logging.getLogger("hermes-zalo.accounts")

ACCOUNTS_FILE = os.path.expanduser("~/.hermes-zalo/accounts.json")


def _load() -> Dict[str, Any]:
    """Load accounts from JSON file."""
    if not os.path.exists(ACCOUNTS_FILE):
        return {}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Load accounts error: {e}")
        return {}


def _save(data: Dict[str, Any]):
    """Save accounts to JSON file."""
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_name(name: str) -> str:
    """Normalize account name for lookup."""
    return name.strip().lower()


def register_account(name: str, zalo_id: str, display_name: str = "", profile: str = None) -> Dict[str, Any]:
    """Register a Zalo account with a friendly name.

    Args:
        name: Friendly name (e.g. "Duy Phong", "Công ty", "Shop")
        zalo_id: Zalo user ID
        display_name: Zalo display name (from profile)
        profile: openzca profile name (auto-generated if None)

    Returns:
        Account record
    """
    data = _load()
    key = _normalize_name(name)

    # Auto-generate profile name if not provided
    if not profile:
        profile = f"account_{key.replace(' ', '_')}"

    account = {
        "name": name.strip(),
        "key": key,
        "zalo_id": zalo_id,
        "display_name": display_name,
        "profile": profile,
        "registered_at": time.time(),
        "registered_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    data[key] = account
    _save(data)

    logger.info(f"[ACCOUNTS] Đăng ký: '{name}' → ID: {zalo_id}, profile: {profile}")
    return account


def find_account(name: str) -> Optional[Dict[str, Any]]:
    """Find account by friendly name (case-insensitive, partial match)."""
    data = _load()
    key = _normalize_name(name)

    # Exact match first
    if key in data:
        return data[key]

    # Partial match
    for k, account in data.items():
        if key in k or key in account.get("name", "").lower():
            return account

    return None


def list_accounts() -> List[Dict[str, Any]]:
    """List all registered accounts."""
    data = _load()
    return list(data.values())


def remove_account(name: str) -> bool:
    """Remove an account by name."""
    data = _load()
    key = _normalize_name(name)

    if key in data:
        del data[key]
        _save(data)
        logger.info(f"[ACCOUNTS] Xóa: '{name}'")
        return True

    # Partial match
    for k in list(data.keys()):
        if key in k:
            del data[k]
            _save(data)
            logger.info(f"[ACCOUNTS] Xóa: '{k}'")
            return True

    return False


def update_account(name: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Update account fields."""
    data = _load()
    key = _normalize_name(name)

    account = None
    actual_key = None
    for k, v in data.items():
        if key == k or key in k:
            account = v
            actual_key = k
            break

    if not account:
        return None

    for field, value in kwargs.items():
        if value is not None:
            account[field] = value

    data[actual_key] = account
    _save(data)
    return account


def get_account_count() -> int:
    """Get number of registered accounts."""
    return len(_load())
