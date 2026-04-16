"""Zalo API wrapper - group management and messaging via openzca CLI."""

import json
import logging
import subprocess
import shlex
from typing import Optional, List, Dict, Any

import config

logger = logging.getLogger("hermes-zalo.zalo_api")


def _run_openzca(args: List[str], profile: str = None, timeout: int = 30) -> Dict[str, Any]:
    """Run openzca command and return parsed output.

    Args:
        args: Command arguments (e.g. ["group", "list", "-j"])
        profile: OpenZCA profile name (default: first configured profile)
        timeout: Command timeout in seconds
    """
    profile = profile or config.OPENZCA_PROFILES[0] if config.OPENZCA_PROFILES else "default"
    cmd = [config.OPENZCA_BIN, "--profile", profile] + args
    logger.debug(f"[ZALO][{profile}] {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            logger.error(f"[ZALO][{profile}] Command failed: {error}")
            return {"error": error, "returncode": result.returncode}

        output = result.stdout.strip()
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"output": output}

    except subprocess.TimeoutExpired:
        logger.error(f"[ZALO][{profile}] Command timeout: {cmd}")
        return {"error": "timeout"}
    except Exception as e:
        logger.error(f"[ZALO][{profile}] Command error: {e}")
        return {"error": str(e)}


# ─── Group operations ─────────────────────────────────────────────────────────

def list_groups(profile: str = None) -> List[Dict[str, Any]]:
    """List all Zalo groups for a profile."""
    result = _run_openzca(["group", "list", "-j"], profile=profile)
    if isinstance(result, list):
        return result
    if "error" in result:
        logger.error(f"[ZALO] list_groups error: {result['error']}")
    return []


def get_group_info(group_id: str, profile: str = None) -> Dict[str, Any]:
    """Get detailed info for a group."""
    return _run_openzca(["group", "info", str(group_id)], profile=profile)


def list_group_members(group_id: str, profile: str = None) -> List[Dict[str, Any]]:
    """List members of a group."""
    result = _run_openzca(["group", "members", str(group_id), "-j"], profile=profile)
    if isinstance(result, list):
        return result
    return []


def find_group_by_name(name: str, profile: str = None) -> Optional[Dict[str, Any]]:
    """Find a group by name (case-insensitive partial match)."""
    groups = list_groups(profile=profile)
    name_lower = name.lower()
    for g in groups:
        group_name = g.get("name", "")
        if name_lower in group_name.lower():
            return g
    return None


def find_group_across_profiles(name: str) -> Optional[Dict[str, Any]]:
    """Search for a group across ALL configured profiles."""
    for profile in config.OPENZCA_PROFILES:
        group = find_group_by_name(name, profile=profile)
        if group:
            group["_profile"] = profile
            return group
    return None


# ─── Messaging ────────────────────────────────────────────────────────────────

def send_message(target_id: str, text: str, is_group: bool = True, profile: str = None) -> bool:
    """Send a text message to a user or group."""
    text = text.strip()[:2000]
    if not text:
        logger.warning("[ZALO] Empty message, skip")
        return False

    args = ["msg", "send", str(target_id), text]
    if is_group:
        args.append("-g")

    result = _run_openzca(args, profile=profile)
    success = "error" not in result
    p = profile or "default"
    if success:
        logger.info(f"[OUTBOUND][{p}] Gửi tới {'group' if is_group else 'DM'} {target_id} ({len(text)} ký tự)")
    else:
        logger.error(f"[OUTBOUND][{p}] Send failed: {result.get('error')}")
    return success


def send_image(target_id: str, image_url: str, caption: str = "", is_group: bool = True, profile: str = None) -> bool:
    """Send an image to a user or group."""
    args = ["msg", "image", str(target_id), "-u", image_url]
    if caption:
        args.extend(["-m", caption])
    if is_group:
        args.append("-g")

    result = _run_openzca(args, profile=profile)
    return "error" not in result


def send_voice(target_id: str, audio_url: str, is_group: bool = True, profile: str = None) -> bool:
    """Send a voice message to a user or group."""
    args = ["msg", "voice", str(target_id), "-u", audio_url]
    if is_group:
        args.append("-g")

    result = _run_openzca(args, profile=profile)
    return "error" not in result


def send_file(target_id: str, file_url: str, caption: str = "", is_group: bool = True, profile: str = None) -> bool:
    """Send a file to a user or group."""
    args = ["msg", "file", str(target_id), "-u", file_url]
    if caption:
        args.extend(["-m", caption])
    if is_group:
        args.append("-g")

    result = _run_openzca(args, profile=profile)
    return "error" not in result


def send_link(target_id: str, url: str, is_group: bool = True, profile: str = None) -> bool:
    """Send a link preview to a user or group."""
    args = ["msg", "link", str(target_id), url]
    if is_group:
        args.append("-g")

    result = _run_openzca(args, profile=profile)
    return "error" not in result


# ─── Account / Profile ────────────────────────────────────────────────────────

def get_own_id(profile: str = None) -> Optional[str]:
    """Get the bot's own Zalo ID for a profile."""
    result = _run_openzca(["me", "id"], profile=profile)
    if isinstance(result, dict) and "output" in result:
        return result["output"].strip()
    if isinstance(result, str):
        return result.strip()
    return None


def get_own_profile(profile: str = None) -> Dict[str, Any]:
    """Get the bot's full profile info."""
    return _run_openzca(["me", "info", "-j"], profile=profile)


def list_friends(profile: str = None) -> List[Dict[str, Any]]:
    """List all friends for a profile."""
    result = _run_openzca(["friend", "list", "-j"], profile=profile)
    if isinstance(result, list):
        return result
    return []


def find_friend(name: str, profile: str = None) -> Optional[Dict[str, Any]]:
    """Find a friend by name."""
    result = _run_openzca(["friend", "find", name, "-j"], profile=profile)
    if isinstance(result, list) and result:
        return result[0]
    return None


# ─── Multi-account helpers ────────────────────────────────────────────────────

def list_all_profiles_groups() -> Dict[str, List[Dict]]:
    """List groups from ALL configured profiles. Returns {profile: [groups]}."""
    all_groups = {}
    for profile in config.OPENZCA_PROFILES:
        groups = list_groups(profile=profile)
        all_groups[profile] = groups
        logger.info(f"[{profile}] Found {len(groups)} groups")
    return all_groups
