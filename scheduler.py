"""Scheduler - cron-like scheduled Zalo messages."""

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import zalo_api
import accounts

logger = logging.getLogger("hermes-zalo.scheduler")

SCHEDULES_FILE = os.path.expanduser("~/.hermes-zalo/schedules.json")

_jobs: Dict[str, Dict[str, Any]] = {}
_threads: Dict[str, threading.Thread] = {}
_stop_event = threading.Event()


def _load() -> Dict[str, Any]:
    if not os.path.exists(SCHEDULES_FILE):
        return {}
    try:
        with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: Dict[str, Any]):
    os.makedirs(os.path.dirname(SCHEDULES_FILE), exist_ok=True)
    with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_schedule(text: str) -> Optional[Dict[str, Any]]:
    """Parse Vietnamese schedule text into cron-like config.

    Examples:
        "mỗi 1 giờ"      → {"type": "interval", "seconds": 3600}
        "mỗi 30 phút"    → {"type": "interval", "seconds": 1800}
        "mỗi 1 ngày"     → {"type": "interval", "seconds": 86400}
        "hàng ngày"      → {"type": "daily", "time": "08:00"}
        "hàng ngày 9h"   → {"type": "daily", "time": "09:00"}
        "hàng tuần"      → {"type": "weekly", "day": "monday", "time": "08:00"}
        "9:00 hàng ngày" → {"type": "daily", "time": "09:00"}
        "9:00"           → {"type": "daily", "time": "09:00"}
        "mỗi 2 giờ 30 phút" → {"type": "interval", "seconds": 9000}
    """
    text = text.strip().lower()

    # "mỗi N giờ/phút/ngày/tuần"
    interval_match = re_match = _re_match(
        r"mỗi\s+(\d+)\s*(giờ|phút|ngày|tuần|giay|phut|ngay|tuan)(?:\s+(\d+)\s*(giờ|phút|ngày|tuần|giay|phut|ngay|tuan))?",
        text
    )
    if interval_match:
        value1 = int(interval_match.group(1))
        unit1 = interval_match.group(2)
        seconds = _unit_to_seconds(value1, unit1)

        if interval_match.group(3) and interval_match.group(4):
            value2 = int(interval_match.group(3))
            unit2 = interval_match.group(4)
            seconds += _unit_to_seconds(value2, unit2)

        return {"type": "interval", "seconds": seconds}

    # "hàng ngày" / "hàng ngày 9h" / "9:00 hàng ngày"
    daily_match = _re_match(r"(?:hàng\s+ngày|hang\s+ngay)(?:\s+(\d{1,2})(?:h|:00)?)?", text)
    if not daily_match:
        daily_match = _re_match(r"(\d{1,2}:\d{2})\s+hàng\s+ngày", text)

    if daily_match:
        hour_str = daily_match.group(1)
        if hour_str and ":" in hour_str:
            return {"type": "daily", "time": hour_str}
        elif hour_str:
            return {"type": "daily", "time": f"{int(hour_str):02d}:00"}
        return {"type": "daily", "time": "08:00"}

    # "hàng tuần" / "thứ 2" / "monday"
    weekly_match = _re_match(r"hàng\s+tuần(?:\s+(thứ\s*\d|chủ\s*nhật|monday|tuesday|wednesday|thursday|friday|saturday|sunday))?(?:\s+(\d{1,2})(?:h|:00)?)?", text)
    if weekly_match:
        day = weekly_match.group(1) or "monday"
        hour = weekly_match.group(2) or "08"
        return {"type": "weekly", "day": day.lower(), "time": f"{int(hour):02d}:00"}

    # "9:00" - just a time → daily at that time
    time_match = _re_match(r"(\d{1,2}):(\d{2})", text)
    if time_match:
        return {"type": "daily", "time": f"{int(time_match.group(1)):02d}:{time_match.group(2)}"}

    return None


def _re_match(pattern, text):
    import re
    return re.match(pattern, text, re.IGNORECASE)


def _unit_to_seconds(value: int, unit: str) -> int:
    unit = unit.lower()
    if unit in ("giờ", "giay", "hour", "h"):
        return value * 3600
    if unit in ("phút", "phut", "minute", "m", "min"):
        return value * 60
    if unit in ("ngày", "ngay", "day", "d"):
        return value * 86400
    if unit in ("tuần", "tuan", "week", "w"):
        return value * 604800
    return value * 60


def create_job(
    account_name: str,
    message: str,
    schedule_config: Dict[str, Any],
    group_name: str = None,
) -> Dict[str, Any]:
    """Create a scheduled job.

    Args:
        account_name: Friendly account name
        message: Message to send
        schedule_config: From parse_schedule()
        group_name: Optional group name to send to

    Returns:
        Job record
    """
    import uuid
    job_id = str(uuid.uuid4())[:8]

    account = accounts.find_account(account_name)
    if not account:
        return {"error": f"Không tìm thấy acc '{account_name}'"}

    job = {
        "id": job_id,
        "account_name": account["name"],
        "account_key": account["key"],
        "profile": account["profile"],
        "group_name": group_name,
        "message": message,
        "schedule": schedule_config,
        "created_at": time.time(),
        "created_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_run": None,
        "run_count": 0,
        "active": True,
    }

    # Save to file
    data = _load()
    data[job_id] = job
    _save(data)

    # Start thread
    _start_job_thread(job)

    schedule_desc = _describe_schedule(schedule_config)
    logger.info(f"[SCHED] Tạo job {job_id}: '{message[:50]}...' → {account['name']} {schedule_desc}")
    return job


def _describe_schedule(config: Dict) -> str:
    if config["type"] == "interval":
        secs = config["seconds"]
        if secs >= 86400:
            return f"mỗi {secs // 86400} ngày"
        elif secs >= 3600:
            return f"mỗi {secs // 3600} giờ"
        else:
            return f"mỗi {secs // 60} phút"
    elif config["type"] == "daily":
        return f"hàng ngày lúc {config['time']}"
    elif config["type"] == "weekly":
        return f"hàng tuần ({config['day']}) lúc {config['time']}"
    return str(config)


def _start_job_thread(job: Dict):
    job_id = job["id"]
    if job_id in _threads and _threads[job_id].is_alive():
        return

    thread = threading.Thread(
        target=_job_loop,
        args=(job,),
        daemon=True,
        name=f"sched-{job_id}",
    )
    thread.start()
    _threads[job_id] = thread
    _jobs[job_id] = job


def _job_loop(job: Dict):
    job_id = job["id"]
    schedule = job["schedule"]

    logger.info(f"[SCHED][{job_id}] Started - {_describe_schedule(schedule)}")

    while not _stop_event.is_set() and job.get("active", True):
        if schedule["type"] == "interval":
            wait_seconds = schedule["seconds"]
        elif schedule["type"] == "daily":
            wait_seconds = _seconds_until_time(schedule["time"])
        elif schedule["type"] == "weekly":
            wait_seconds = _seconds_until_weekly(schedule["day"], schedule["time"])
        else:
            logger.error(f"[SCHED][{job_id}] Unknown schedule type: {schedule['type']}")
            break

        logger.debug(f"[SCHED][{job_id}] Next run in {wait_seconds}s")
        if _stop_event.wait(wait_seconds):
            break

        if not job.get("active", True):
            break

        # Execute
        _execute_job(job)


def _execute_job(job: Dict):
    job_id = job["id"]
    profile = job["profile"]
    message = job["message"]

    logger.info(f"[SCHED][{job_id}] Executing: '{message[:80]}...'")

    # Find target group
    if job.get("group_name"):
        group = zalo_api.find_group_by_name(job["group_name"], profile=profile)
        if not group:
            logger.error(f"[SCHED][{job_id}] Group '{job['group_name']}' not found")
            return
        target_id = group["groupId"]
        target_name = group.get("name", target_id)
    else:
        groups = zalo_api.list_groups(profile=profile)
        if not groups:
            logger.error(f"[SCHED][{job_id}] No groups found")
            return
        target = groups[0]
        target_id = target["groupId"]
        target_name = target.get("name", target_id)

    success = zalo_api.send_message(target_id, message, is_group=True, profile=profile)

    # Update job stats
    job["last_run"] = time.time()
    job["last_run_str"] = time.strftime("%Y-%m-%d %H:%M:%S")
    job["run_count"] = job.get("run_count", 0) + 1
    if success:
        logger.info(f"[SCHED][{job_id}] Sent to {target_name} (run #{job['run_count']})")
    else:
        logger.error(f"[SCHED][{job_id}] Send failed")

    # Save updated stats
    data = _load()
    data[job_id] = job
    _save(data)


def _seconds_until_time(time_str: str) -> int:
    """Seconds until next occurrence of HH:MM."""
    now = datetime.now()
    target_hour, target_min = map(int, time_str.split(":"))
    target = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return int((target - now).total_seconds())


def _seconds_until_weekly(day_str: str, time_str: str) -> int:
    """Seconds until next occurrence of weekday at HH:MM."""
    day_map = {
        "thứ 2": 0, "thứ hai": 0, "monday": 0, "t2": 0,
        "thứ 3": 1, "thứ ba": 1, "tuesday": 1, "t3": 1,
        "thứ 4": 2, "thứ tư": 2, "wednesday": 2, "t4": 2,
        "thứ 5": 3, "thứ năm": 3, "thursday": 3, "t5": 3,
        "thứ 6": 4, "thứ sáu": 4, "friday": 4, "t6": 4,
        "thứ 7": 5, "thứ bảy": 5, "saturday": 5, "t7": 5,
        "chủ nhật": 6, "sunday": 6, "cn": 6,
    }

    target_weekday = day_map.get(day_str.strip().lower(), 0)
    now = datetime.now()
    target_hour, target_min = map(int, time_str.split(":"))

    days_ahead = (target_weekday - now.weekday()) % 7
    if days_ahead == 0:
        target = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
        if target <= now:
            days_ahead = 7

    target = (now + timedelta(days=days_ahead)).replace(
        hour=target_hour, minute=target_min, second=0, microsecond=0
    )
    return int((target - now).total_seconds())


def list_jobs() -> List[Dict]:
    """List all scheduled jobs."""
    data = _load()
    return list(data.values())


def remove_job(job_id: str) -> bool:
    """Remove a scheduled job."""
    data = _load()
    if job_id in data:
        data[job_id]["active"] = False
        del data[job_id]
        _save(data)
        logger.info(f"[SCHED] Removed job {job_id}")
        return True

    # Partial match
    for k in list(data.keys()):
        if job_id in k:
            data[k]["active"] = False
            del data[k]
            _save(data)
            logger.info(f"[SCHED] Removed job {k}")
            return True

    return False


def start_all():
    """Start all saved jobs."""
    data = _load()
    for job_id, job in data.items():
        if job.get("active", True):
            _start_job_thread(job)
    logger.info(f"[SCHED] Started {len(data)} jobs")


def stop():
    """Stop all scheduler threads."""
    _stop_event.set()
    logger.info("[SCHED] Stopped all jobs")
