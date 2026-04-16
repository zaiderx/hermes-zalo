"""Zalo listener - spawn openzca listen per profile and parse stdout."""

import json
import logging
import subprocess
import threading
import time
import os
import signal
from typing import Dict, Optional

import config
import db_local
import db_mariadb
import hermes_bridge
import commands as cmd_handler
import sync

logger = logging.getLogger("hermes-zalo.listener")

# Track all active listener processes per profile
_processes: Dict[str, subprocess.Popen] = {}
_threads: Dict[str, threading.Thread] = {}
_stop_event = threading.Event()


def _send_zalo_reply(thread_id: str, text: str, profile: str = "default"):
    """Send reply back to Zalo via openzca msg send."""
    if not text or not text.strip():
        return

    # Truncate to 2000 chars (Zalo limit)
    text = text.strip()[:2000]

    cmd = [
        config.OPENZCA_BIN,
        "--profile", profile,
        "msg", "send",
        str(thread_id),
        text,
    ]

    logger.info(f"[OUTBOUND][{profile}] Gửi tới threadId={thread_id} ({len(text)} ký tự).")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"[OUTBOUND][{profile}] Send failed: {result.stderr}")
        else:
            logger.debug(f"[OUTBOUND][{profile}] Sent OK")
    except subprocess.TimeoutExpired:
        logger.error(f"[OUTBOUND][{profile}] Send timeout")
    except Exception as e:
        logger.error(f"[OUTBOUND][{profile}] Send error: {e}")


def _send_zalo_image(thread_id: str, image_path: str, caption: str = "", profile: str = "default"):
    """Send an image file to Zalo via openzca msg image."""
    # openzca msg image accepts -u for URL or file path
    args = [
        config.OPENZCA_BIN,
        "--profile", profile,
        "msg", "image",
        str(thread_id),
        "-u", image_path,
    ]
    if caption:
        args.extend(["-m", caption])

    logger.info(f"[OUTBOUND][{profile}] Gửi ảnh tới threadId={thread_id}")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"[OUTBOUND][{profile}] Image send failed: {result.stderr}")
        else:
            logger.debug(f"[OUTBOUND][{profile}] Image sent OK")
    except subprocess.TimeoutExpired:
        logger.error(f"[OUTBOUND][{profile}] Image send timeout")
    except Exception as e:
        logger.error(f"[OUTBOUND][{profile}] Image send error: {e}")


def _process_message(line: str, profile: str):
    """Process one JSON line from openzca listen output."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        # Not JSON - might be a status line like "Connected to Zalo websocket."
        logger.debug(f"[RAW][{profile}] {line}")
        return

    # Filter lifecycle events
    if data.get("kind") == "lifecycle":
        logger.debug(f"[LIFECYCLE][{profile}] {data.get('event')}")
        return

    # Must have content and threadId
    thread_id = data.get("threadId")
    content = data.get("content", "").strip()
    sender_id = str(data.get("senderId", ""))

    if not thread_id or not content:
        return

    # Filter own messages (per-profile)
    own_id = config.get_own_id(profile) or config.OWN_ID
    if own_id and sender_id == own_id:
        logger.debug(f"[SKIP][{profile}] Own message from {sender_id}")
        return

    sender_name = data.get("senderName") or data.get("senderDisplayName") or sender_id
    chat_type = data.get("chatType", "user")

    # Tag data with profile
    data["_profile"] = profile

    logger.info(
        f"[INBOUND][{profile}] {'DM' if chat_type == 'user' else 'GROUP'} "
        f"threadId={thread_id} senderId={sender_id} name='{sender_name}' | {content[:100]}"
    )

    # Save to local DB
    try:
        db_local.insert_message(data)
    except Exception as e:
        logger.error(f"[DB][{profile}] SQLite insert error: {e}")

    # Save to MariaDB (real-time)
    try:
        db_mariadb.insert_single(data)
    except Exception as e:
        logger.error(f"[DB][{profile}] MariaDB insert error (will retry on sync): {e}")
    # Only process DMs (skip groups unless configured)
    if chat_type != "user":
        logger.debug(f"[SKIP][{profile}] Group message - not forwarding")
        return

    # ─── 1. Check natural language commands first ─────────────────────
    import nl_parser
    nl_cmd = nl_parser.parse_command(content, sender_id=sender_id, sender_name=sender_name)
    if nl_cmd:
        logger.info(f"[NL-CMD][{profile}] {sender_name}: {nl_cmd['action']}")
        response = nl_parser.execute_command(nl_cmd)

        # Handle QR login - send image
        if isinstance(response, dict) and response.get("_type") == "qr_login":
            qr_path = response.get("qr_path")
            message = response.get("message", "Quét QR code này")
            if qr_path and os.path.exists(qr_path):
                _send_zalo_image(thread_id, qr_path, caption=message, profile=profile)
            else:
                _send_zalo_reply(thread_id, message, profile=profile)
        elif response:
            _send_zalo_reply(thread_id, response, profile=profile)
        return

    # ─── 2. Check slash commands ──────────────────────────────────────
    cmd_response = cmd_handler.process_command(
        sender_id=sender_id,
        text=content,
        sender_name=sender_name,
        profile=profile,
    )

    if cmd_response:
        # Handle QR login - send image
        if isinstance(cmd_response, dict) and cmd_response.get("_type") == "qr_login":
            qr_path = cmd_response.get("qr_path")
            message = cmd_response.get("message", "Quét QR code này")
            if qr_path and os.path.exists(qr_path):
                _send_zalo_image(thread_id, qr_path, caption=message, profile=profile)
            else:
                _send_zalo_reply(thread_id, message, profile=profile)
            return

        _send_zalo_reply(thread_id, cmd_response, profile=profile)
        return

    # ─── 3. Forward to Hermes (default) ──────────────────────────────
    logger.info(f"[PROC][{profile}] DM threadId={thread_id} senderId={sender_id}")
    response = hermes_bridge.call_hermes(
        prompt=content,
        sender_name=sender_name,
        thread_id=thread_id,
    )

    # Send reply back
    if response:
        _send_zalo_reply(thread_id, response, profile=profile)


def _detect_own_id(profile: str):
    """Detect own Zalo ID for a profile."""
    existing = config.get_own_id(profile)
    if existing:
        return

    try:
        result = subprocess.run(
            [config.OPENZCA_BIN, "--profile", profile, "me", "id"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            own_id = result.stdout.strip()
            if own_id:
                config.set_own_id(profile, own_id)
                logger.info(f"[{profile}] Own ID: {own_id}")
    except Exception as e:
        logger.warning(f"[{profile}] Không thể detect own ID: {e}")


def _listen_loop(profile: str):
    """Main listener loop for one profile."""
    global _processes

    cmd = [
        config.OPENZCA_BIN,
        "--profile", profile,
        "listen",
        "--raw",
        "--keep-alive",
    ]

    logger.info(f"[{profile}] Khởi động listener: {' '.join(cmd)}")

    while not _stop_event.is_set():
        logger.info(f"=== [{profile}] Hermes-Zalo listener khởi động ===")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            _processes[profile] = proc
            logger.info(f"[{profile}] PID {proc.pid} started")

            for line in proc.stdout:
                if _stop_event.is_set():
                    break
                line = line.strip()
                if line:
                    _process_message(line, profile)

            proc.wait()
            exit_code = proc.returncode

            if exit_code == 0:
                logger.info(f"[{profile}] Process exited normally")
            elif exit_code == 75:
                logger.info(f"[{profile}] Recycle exit - restarting")
            else:
                logger.warning(f"[{profile}] Exit code {exit_code}")
                if proc.stderr:
                    stderr = proc.stderr.read()
                    if stderr:
                        logger.error(f"[{profile}] stderr: {stderr}")

        except FileNotFoundError:
            logger.error(f"[{profile}] openzca not found at '{config.OPENZCA_BIN}'")
            _stop_event.wait(30)
        except Exception as e:
            logger.error(f"[{profile}] Unexpected error: {e}")

        if not _stop_event.is_set():
            delay = 2
            logger.info(f"[{profile}] Restarting in {delay}s...")
            _stop_event.wait(delay)

    _processes.pop(profile, None)
    logger.info(f"[{profile}] Listener stopped")


def start_profile(profile: str):
    """Start listener for a single profile."""
    if profile in _threads and _threads[profile].is_alive():
        logger.warning(f"[{profile}] Listener already running")
        return

    _detect_own_id(profile)
    thread = threading.Thread(
        target=_listen_loop,
        args=(profile,),
        daemon=True,
        name=f"listener-{profile}",
    )
    thread.start()
    _threads[profile] = thread
    logger.info(f"[{profile}] Listener thread started")


def start_all():
    """Start listeners for all configured profiles."""
    profiles = config.OPENZCA_PROFILES
    logger.info(f"Starting listeners for {len(profiles)} profiles: {profiles}")
    for profile in profiles:
        start_profile(profile)
        time.sleep(1)  # Stagger startup


def stop():
    """Stop all listeners."""
    global _processes
    _stop_event.set()

    for profile, proc in list(_processes.items()):
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        logger.info(f"[{profile}] Stopped")

    _processes.clear()
    logger.info("All listeners stopped")


def get_status() -> Dict[str, dict]:
    """Get status of all listener profiles."""
    status = {}
    for profile in config.OPENZCA_PROFILES:
        proc = _processes.get(profile)
        thread = _threads.get(profile)
        status[profile] = {
            "running": thread is not None and thread.is_alive(),
            "pid": proc.pid if proc else None,
            "own_id": config.get_own_id(profile),
        }
    return status
