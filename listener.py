"""Zalo listener - spawn openzca listen and parse stdout."""

import json
import logging
import subprocess
import threading
import time
import os
import signal

import config
import db_local
import db_mariadb
import hermes_bridge
import sync

logger = logging.getLogger("hermes-zalo.listener")

_process: subprocess.Popen | None = None
_stop_event = threading.Event()


def _send_zalo_reply(thread_id: str, text: str):
    """Send reply back to Zalo via openzca msg send."""
    if not text or not text.strip():
        return

    # Truncate to 2000 chars (Zalo limit)
    text = text.strip()[:2000]

    cmd = [
        config.OPENZCA_BIN,
        "--profile", config.OPENZCA_PROFILE,
        "msg", "send",
        str(thread_id),
        text,
    ]

    logger.info(f"[OUTBOUND] Gửi tới threadId={thread_id} ({len(text)} ký tự).")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"[OUTBOUND] Send failed: {result.stderr}")
        else:
            logger.debug(f"[OUTBOUND] Sent OK")
    except subprocess.TimeoutExpired:
        logger.error(f"[OUTBOUND] Send timeout")
    except Exception as e:
        logger.error(f"[OUTBOUND] Send error: {e}")


def _process_message(line: str):
    """Process one JSON line from openzca listen output."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        # Not JSON - might be a status line like "Connected to Zalo websocket."
        logger.debug(f"[RAW] {line}")
        return

    # Filter lifecycle events
    if data.get("kind") == "lifecycle":
        logger.debug(f"[LIFECYCLE] {data.get('event')}")
        return

    # Must have content and threadId
    thread_id = data.get("threadId")
    content = data.get("content", "").strip()
    sender_id = str(data.get("senderId", ""))

    if not thread_id or not content:
        return

    # Filter own messages
    if config.OWN_ID and sender_id == config.OWN_ID:
        logger.debug(f"[SKIP] Own message from {sender_id}")
        return

    sender_name = data.get("senderName") or data.get("senderDisplayName") or sender_id
    chat_type = data.get("chatType", "user")

    logger.info(
        f"[INBOUND] {'DM' if chat_type == 'user' else 'GROUP'} "
        f"threadId={thread_id} senderId={sender_id} name='{sender_name}' | {content[:100]}"
    )

    # Save to local DB
    try:
        db_local.insert_message(data)
    except Exception as e:
        logger.error(f"[DB] SQLite insert error: {e}")

    # Save to MariaDB (real-time)
    try:
        db_mariadb.insert_single(data)
    except Exception as e:
        logger.error(f"[DB] MariaDB insert error (will retry on sync): {e}")

    # Only process DMs for Hermes (skip groups unless configured)
    if chat_type != "user":
        logger.debug(f"[SKIP] Group message - not forwarding to Hermes")
        return

    # Call Hermes
    logger.info(f"[PROC] DM threadId={thread_id} senderId={sender_id}")
    response = hermes_bridge.call_hermes(
        prompt=content,
        sender_name=sender_name,
        thread_id=thread_id,
    )

    # Send reply back
    if response:
        _send_zalo_reply(thread_id, response)


def _listen_loop():
    """Main listener loop - spawn openzca listen --raw --keep-alive."""
    cmd = [
        config.OPENZCA_BIN,
        "--profile", config.OPENZCA_PROFILE,
        "listen",
        "--raw",
        "--keep-alive",
    ]

    logger.info(f"listener: Khởi động listener: {' '.join(cmd)}")

    while not _stop_event.is_set():
        logger.info("=== BearGate khởi động ===")

        try:
            _process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            logger.info(f"listener: PID {_process.pid} started")

            # Read stdout line by line
            for line in _process.stdout:
                if _stop_event.is_set():
                    break
                line = line.strip()
                if line:
                    _process_message(line)

            # Check if process exited
            _process.wait()
            exit_code = _process.returncode

            if exit_code == 0:
                logger.info("listener: Process exited normally")
            elif exit_code == 75:
                logger.info("listener: Recycle exit code - restarting")
            else:
                logger.warning(f"listener: Process exited with code {exit_code}")
                if _process.stderr:
                    stderr = _process.stderr.read()
                    if stderr:
                        logger.error(f"listener stderr: {stderr}")

        except FileNotFoundError:
            logger.error(
                f"listener: openzca not found at '{config.OPENZCA_BIN}'. "
                f"Install: npm install -g openzca"
            )
            _stop_event.wait(30)

        except Exception as e:
            logger.error(f"listener: Unexpected error: {e}")

        if not _stop_event.is_set():
            delay = 2
            logger.info(f"listener: Restarting in {delay}s...")
            _stop_event.wait(delay)


def start():
    """Start the listener thread."""
    thread = threading.Thread(target=_listen_loop, daemon=True, name="listener")
    thread.start()
    return thread


def stop():
    """Stop the listener."""
    global _process
    _stop_event.set()
    if _process:
        try:
            _process.send_signal(signal.SIGTERM)
            _process.wait(timeout=5)
        except Exception:
            _process.kill()
        _process = None
    logger.info("listener: Stopped")
