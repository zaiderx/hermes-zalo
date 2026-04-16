"""Hermes bridge - forward messages to Hermes agent, return response."""

import json
import logging
import urllib.request
import urllib.error

import config

logger = logging.getLogger("beargate.hermes")


def call_hermes(prompt: str, sender_name: str = None, thread_id: str = None) -> str:
    """Send prompt to Hermes agent and return response text.

    Args:
        prompt: The message text
        sender_name: Display name of sender (for context)
        thread_id: Zalo thread ID (for context)

    Returns:
        Response text from Hermes, or error message
    """
    logger.info(f"[HERMES] Gửi prompt ({len(prompt)} ký tự): {prompt[:80]}...")

    # Build context-enriched prompt
    context_parts = []
    if sender_name:
        context_parts.append(f"From: {sender_name}")
    if thread_id:
        context_parts.append(f"Thread: {thread_id}")

    if context_parts:
        full_prompt = f"[{', '.join(context_parts)}]\n{prompt}"
    else:
        full_prompt = prompt

    payload = json.dumps({
        "message": full_prompt,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }
    if config.HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {config.HERMES_API_KEY}"

    try:
        req = urllib.request.Request(
            config.HERMES_API_URL,
            data=payload,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=config.HERMES_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            response = data.get("response") or data.get("message") or data.get("text", "")
            logger.info(f"[HERMES] Nhận được phản hồi ({len(response)} ký tự).")
            return response

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        logger.error(f"[HERMES] HTTP {e.code}: {error_body}")
        return f"Lỗi: HTTP {e.code}"

    except urllib.error.URLError as e:
        logger.error(f"[HERMES] Connection error: {e.reason}")
        return "Không thể kết nối tới Hermes"

    except Exception as e:
        logger.error(f"[HERMES] Unexpected error: {e}")
        return f"Lỗi: {e}"
