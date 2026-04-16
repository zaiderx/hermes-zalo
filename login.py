"""Zalo login - QR code authentication for multiple accounts."""

import json
import logging
import os
import subprocess
import tempfile
import base64
import time
from typing import Optional, Dict, Any, Tuple

import config

logger = logging.getLogger("hermes-zalo.login")


def _run_openzca(args: List[str], profile: str = "default", timeout: int = 60) -> Dict[str, Any]:
    """Run openzca command and return parsed output."""
    from typing import List
    profile = profile or (config.OPENZCA_PROFILES[0] if config.OPENZCA_PROFILES else "default")
    cmd = [config.OPENZCA_BIN, "--profile", profile] + args
    logger.debug(f"[LOGIN][{profile}] {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            logger.error(f"[LOGIN][{profile}] Failed: {error}")
            return {"error": error, "returncode": result.returncode}

        output = result.stdout.strip()
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"output": output}

    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}


def check_login_status(profile: str = "default") -> Dict[str, Any]:
    """Check if a profile is already logged in.

    Returns:
        {"logged_in": bool, "user_id": str, "display_name": str} or {"error": "..."}
    """
    # Try to get own ID
    result = _run_openzca(["me", "id"], profile=profile)
    if "error" in result:
        return {"logged_in": False, "error": result["error"]}

    user_id = None
    if isinstance(result, dict) and "output" in result:
        user_id = result["output"].strip()
    elif isinstance(result, str):
        user_id = result.strip()

    if not user_id:
        return {"logged_in": False}

    # Try to get profile info
    info = _run_openzca(["me", "info", "-j"], profile=profile)
    display_name = "?"
    if isinstance(info, dict) and "error" not in info:
        display_name = info.get("displayName") or info.get("name") or "?"

    return {
        "logged_in": True,
        "user_id": user_id,
        "display_name": display_name,
        "profile": profile,
    }


def login_qr(profile: str = "default", qr_base64: bool = True) -> Dict[str, Any]:
    """Login to Zalo using QR code.

    Args:
        profile: OpenZCA profile name
        qr_base64: If True, return QR as base64 PNG. If False, return file path.

    Returns:
        {
            "success": bool,
            "qr_base64": str,      # base64 PNG of QR code
            "qr_path": str,        # file path to QR image
            "user_id": str,        # Zalo ID after login
            "display_name": str,   # Display name
            "profile": str,
        }
        or {"error": "..."}
    """
    logger.info(f"[LOGIN][{profile}] Bắt đầu QR login...")

    # First check if already logged in
    status = check_login_status(profile)
    if status.get("logged_in"):
        logger.info(f"[LOGIN][{profile}] Đã login rồi: {status['user_id']}")
        return {
            "success": True,
            "already_logged_in": True,
            "user_id": status["user_id"],
            "display_name": status["display_name"],
            "profile": profile,
        }

    # Run openzca auth login with --qr-base64 flag
    cmd = [
        config.OPENZCA_BIN,
        "--profile", profile,
        "auth", "login",
    ]
    if qr_base64:
        cmd.append("--qr-base64")

    logger.info(f"[LOGIN][{profile}] Chạy: {' '.join(cmd)}")

    try:
        # This will output the QR code and wait for scan
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes to scan
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            logger.error(f"[LOGIN][{profile}] Login failed: {stderr or stdout}")
            return {"error": stderr or stdout, "returncode": result.returncode}

        # Parse output - openzca outputs JSON with qr_base64 or success
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            data = {"output": stdout}

        # Check for QR base64 in output
        qr_data = data.get("qr_base64") or data.get("qrBase64")
        qr_path = data.get("qr_path") or data.get("qrPath")

        # If openzca outputs base64 QR, save it to a temp file too
        temp_path = None
        if qr_data:
            temp_path = _save_base64_png(qr_data, profile)
        elif qr_path and os.path.exists(qr_path):
            temp_path = qr_path
            # Read it as base64 too
            with open(qr_path, "rb") as f:
                qr_data = base64.b64encode(f.read()).decode()

        # Check if login succeeded
        if data.get("success") or data.get("userId") or data.get("user_id"):
            user_id = data.get("userId") or data.get("user_id", "")
            display_name = data.get("displayName") or data.get("display_name", "?")

            # Also try to detect via me id
            if not user_id:
                time.sleep(1)
                id_result = _run_openzca(["me", "id"], profile=profile)
                if isinstance(id_result, dict) and "output" in id_result:
                    user_id = id_result["output"].strip()

            logger.info(f"[LOGIN][{profile}] Đăng nhập thành công! ID: {user_id}")
            return {
                "success": True,
                "user_id": user_id,
                "display_name": display_name,
                "profile": profile,
            }

        # QR code generated but not yet scanned
        if qr_data:
            logger.info(f"[LOGIN][{profile}] QR code generated, waiting for scan...")
            return {
                "success": False,
                "qr_base64": qr_data,
                "qr_path": temp_path,
                "message": "Quét QR code bằng Zalo trên điện thoại",
                "profile": profile,
            }

        # No QR data in output - try to find it in stderr or output
        return {
            "success": False,
            "message": stdout or stderr,
            "raw_output": stdout[:500],
            "profile": profile,
        }

    except subprocess.TimeoutExpired:
        logger.error(f"[LOGIN][{profile}] QR login timeout (2 minutes)")
        return {"error": "timeout", "message": "QR login timeout - anh scan chưa?"}
    except Exception as e:
        logger.error(f"[LOGIN][{profile}] Error: {e}")
        return {"error": str(e)}


def _save_base64_png(b64_data: str, profile: str) -> str:
    """Save base64 PNG to temp file and return path."""
    # Strip data URI prefix if present
    if "," in b64_data and b64_data.startswith("data:"):
        b64_data = b64_data.split(",", 1)[1]

    img_bytes = base64.b64decode(b64_data)

    save_dir = os.path.expanduser("~/.hermes-zalo/qrcodes")
    os.makedirs(save_dir, exist_ok=True)

    filepath = os.path.join(save_dir, f"qr_{profile}_{int(time.time())}.png")
    with open(filepath, "wb") as f:
        f.write(img_bytes)

    logger.info(f"[LOGIN] QR saved to {filepath}")
    return filepath


def logout(profile: str = "default") -> Dict[str, Any]:
    """Logout from a Zalo profile."""
    result = _run_openzca(["auth", "logout"], profile=profile)
    if "error" in result:
        return {"success": False, "error": result["error"]}
    logger.info(f"[LOGIN][{profile}] Logged out")
    return {"success": True, "profile": profile}


def list_profiles_status() -> list:
    """List login status for all configured profiles."""
    results = []
    for profile in config.OPENZCA_PROFILES:
        status = check_login_status(profile)
        label = config.get_profile_config(profile).get("label", "")
        results.append({
            "profile": profile,
            "label": label,
            **status,
        })
    return results
