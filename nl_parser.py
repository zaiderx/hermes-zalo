"""Natural language command parser - parse Vietnamese commands from user messages."""

import re
import logging
from typing import Optional, Dict, Any, Tuple

import accounts
import zalo_api
import login as login_module
import config

logger = logging.getLogger("hermes-zalo.nl_parser")


def parse_command(text: str, sender_id: str = None, sender_name: str = None) -> Optional[Dict[str, Any]]:
    """Parse natural language text into a command.

    Returns a command dict or None if not a command.

    Supported patterns:
        "đăng nhập zalo với tên <name>"     → login
        "login zalo tên <name>"              → login
        "đăng xuất zalo tên <name>"          → logout
        "gửi cho <name> qua zalo <message>"  → send
        "gửi qua zalo <name> <message>"      → send
        "gui <name> zalo <message>"          → send
        "xem nhóm <name>"                    → list groups
        "danh sách acc zalo"                 → list accounts
        "trạng thái zalo"                    → account status
        "xóa acc zalo <name>"               → remove account
    """
    text = text.strip()
    text_lower = text.lower()

    # ─── Login: "đăng nhập zalo với tên X" ───────────────────────────
    login_patterns = [
        r"đăng\s*nhập\s+zalo\s+(?:với\s+)?tên\s+(.+)",
        r"login\s+zalo\s+(?:tên|ten|name)\s+(.+)",
        r"kết\s*nối\s+zalo\s+(?:với\s+)?tên\s+(.+)",
        r"zalo\s+login\s+(.+)",
        r"thêm\s+acc\s+zalo\s+(.+)",
    ]
    for pattern in login_patterns:
        match = re.match(pattern, text_lower, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean up common suffixes
            name = re.sub(r"\s*(nhé|nha|đi|đấy|ạ|ơi)\s*$", "", name, flags=re.IGNORECASE)
            return {"action": "login", "name": name}

    # ─── Logout: "đăng xuất zalo tên X" ──────────────────────────────
    logout_patterns = [
        r"đăng\s*xuất\s+zalo\s+(?:tên\s+)?(.+)",
        r"logout\s+zalo\s+(.+)",
        r"xóa\s+acc\s+zalo\s+(.+)",
        r"remove\s+zalo\s+(.+)",
    ]
    for pattern in logout_patterns:
        match = re.match(pattern, text_lower, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            return {"action": "logout", "name": name}

    # ─── Send: "gửi cho X qua zalo Y" ────────────────────────────────
    send_patterns = [
        r"gửi\s+cho\s+(.+?)\s+qua\s+zalo\s+(.+)",
        r"gửi\s+qua\s+zalo\s+(.+?)\s+(?:nội dung\s+|nói\s+|rằng\s+)?(.+)",
        r"send\s+(.+?)\s+zalo\s+(.+)",
        r"gui\s+(.+?)\s+zalo\s+(.+)",
        r"gửi\s+(.+?)\s+bằng\s+zalo\s+(.+)",
        r"nhắn\s+(.+?)\s+qua\s+zalo\s+(.+)",
        r"forward\s+(.+?)\s+zalo\s+(.+)",
    ]
    for pattern in send_patterns:
        match = re.match(pattern, text_lower, re.IGNORECASE)
        if match:
            account_name = match.group(1).strip()
            message = match.group(2).strip()
            # Remove trailing particles
            account_name = re.sub(r"\s*(nhé|nha|đi|ạ|ơi)\s*$", "", account_name)

            # Detect media type in message
            # "ảnh <url_or_path>"
            img_match = re.match(r"ảnh\s+(https?://\S+|/.+?\.(?:jpg|png|gif|webp))\s*(.*)", message, re.IGNORECASE)
            if img_match:
                return {
                    "action": "send_image",
                    "account_name": account_name,
                    "media_url": img_match.group(1),
                    "caption": img_match.group(2).strip(),
                }

            # "file <url_or_path>"
            file_match = re.match(r"file\s+(https?://\S+|/.+?\.\w+)\s*(.*)", message, re.IGNORECASE)
            if file_match:
                return {
                    "action": "send_file",
                    "account_name": account_name,
                    "media_url": file_match.group(1),
                    "caption": file_match.group(2).strip(),
                }

            # "voice <url_or_path>" or "ghi âm <url>"
            voice_match = re.match(r"(?:voice|ghi\s*âm|audio)\s+(https?://\S+|/.+?\.(?:ogg|mp3|wav|m4a))\s*(.*)", message, re.IGNORECASE)
            if voice_match:
                return {
                    "action": "send_voice",
                    "account_name": account_name,
                    "media_url": voice_match.group(1),
                }

            # "lịch <schedule> <message>" - cron scheduling
            cron_match = re.match(r"lịch\s+((?:mỗi\s+)?(?:\d+\s*(?:giờ|phút|ngày|tuần)|hàng\s+(?:ngày|tuần|tháng)|\d{1,2}:\d{2}).*?)\s+(.+)", message, re.IGNORECASE)
            if cron_match:
                return {
                    "action": "schedule",
                    "account_name": account_name,
                    "schedule": cron_match.group(1).strip(),
                    "message": cron_match.group(2).strip(),
                }

            return {
                "action": "send",
                "account_name": account_name,
                "message": message,
            }

    # ─── List groups: "xem nhóm của X" / "nhóm zalo X" ──────────────
    groups_patterns = [
        r"xem\s+nhóm\s+(?:của\s+)?(.+?)(?:\s+nhé|\s+nha)?$",
        r"nhóm\s+zalo\s+(.+)",
        r"list\s+groups?\s+(.+)",
        r"danh\s*sách\s+nhóm\s+(.+)",
    ]
    for pattern in groups_patterns:
        match = re.match(pattern, text_lower, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            return {"action": "list_groups", "account_name": name}

    # ─── List accounts: "danh sách acc zalo" ─────────────────────────
    if re.search(r"danh\s*sách\s+acc|list\s+acc|acc\s+zalo|tài\s*khoản\s+zalo", text_lower):
        return {"action": "list_accounts"}

    # ─── Account status: "trạng thái zalo" ───────────────────────────
    if re.search(r"trạng\s*thái\s+zalo|zalo\s+status|kiểm\s*tra\s+zalo", text_lower):
        return {"action": "status"}

    return None


def execute_command(cmd: Dict[str, Any]) -> str:
    """Execute a parsed NL command and return response text.

    Args:
        cmd: Parsed command dict from parse_command()

    Returns:
        Response text
    """
    action = cmd.get("action")

    # ─── Login ────────────────────────────────────────────────────────
    if action == "login":
        name = cmd.get("name", "").strip()
        if not name:
            return "❌ Thiếu tên. Ví dụ: 'đăng nhập zalo với tên Duy Phong'"

        # Check if already registered
        existing = accounts.find_account(name)
        if existing and existing.get("zalo_id"):
            return (
                f"✅ '{existing['name']}' đã đăng nhập rồi!\n"
                f"Zalo ID: {existing['zalo_id']}\n"
                f"Tên Zalo: {existing.get('display_name', '?')}"
            )

        # Generate profile name
        profile = f"account_{name.lower().replace(' ', '_')}"

        # Check openzca login status
        status = login_module.check_login_status(profile)
        if status.get("logged_in"):
            # Already logged in, just register
            account = accounts.register_account(
                name=name,
                zalo_id=status["user_id"],
                display_name=status["display_name"],
                profile=profile,
            )
            return (
                f"✅ '{name}' đã đăng nhập!\n"
                f"Zalo ID: {status['user_id']}\n"
                f"Tên Zalo: {status['display_name']}"
            )

        # Generate QR code
        result = login_module.login_qr(profile)
        if result.get("success"):
            account = accounts.register_account(
                name=name,
                zalo_id=result["user_id"],
                display_name=result.get("display_name", ""),
                profile=profile,
            )
            return (
                f"✅ Đăng nhập '{name}' thành công!\n"
                f"Zalo ID: {result['user_id']}\n"
                f"Tên Zalo: {result.get('display_name', '?')}"
            )
        elif result.get("qr_base64"):
            # Return special marker for QR image sending
            return _make_qr_response(name, profile, result)
        else:
            return f"❌ Không tạo được QR: {result.get('error') or result.get('message', 'Unknown')}"

    # ─── Logout ───────────────────────────────────────────────────────
    if action == "logout":
        name = cmd.get("name", "")
        account = accounts.find_account(name)
        if not account:
            return f"❌ Không tìm thấy acc '{name}'"

        profile = account.get("profile", "default")
        login_module.logout(profile)
        accounts.remove_account(name)
        return f"✅ Đã đăng xuất và xóa acc '{account['name']}'"

    # ─── Send message ─────────────────────────────────────────────────
    if action == "send":
        account_name = cmd.get("account_name", "")
        message = cmd.get("message", "")

        account = accounts.find_account(account_name)
        if not account:
            return f"❌ Không tìm thấy acc '{account_name}'. Gõ 'danh sách acc zalo' để xem."

        profile = account.get("profile")
        if not profile:
            return f"❌ Acc '{account['name']}' chưa có profile"

        # Check if message specifies a group target
        # Pattern: "nhóm <group_name> <actual_message>"
        group_match = re.match(r"nhóm\s+(.+?)\s+(.+)", message, re.IGNORECASE)
        if group_match:
            group_ref = group_match.group(1).strip()
            actual_message = group_match.group(2).strip()

            # Find the group
            group = zalo_api.find_group_by_name(group_ref, profile=profile)
            if not group:
                return f"❌ Không tìm thấy nhóm '{group_ref}' trong acc '{account['name']}'"

            target_id = group["groupId"]
            target_name = group.get("name", target_id)

            success = zalo_api.send_message(target_id, actual_message, is_group=True, profile=profile)
            if success:
                return f"✅ Đã gửi qua '{account['name']}' → nhóm {target_name}: {actual_message[:80]}..."
            else:
                return f"❌ Gửi thất bại"

        # No group specified - list groups and ask
        groups = zalo_api.list_groups(profile=profile)
        if not groups:
            return f"❌ Acc '{account['name']}' không có nhóm nào"

        if len(groups) == 1:
            # Only one group - send there
            target = groups[0]
            target_id = target.get("groupId")
            target_name = target.get("name", target_id)

            success = zalo_api.send_message(target_id, message, is_group=True, profile=profile)
            if success:
                return f"✅ Đã gửi qua '{account['name']}' → {target_name}: {message[:80]}..."
            else:
                return f"❌ Gửi thất bại"
        else:
            # Multiple groups - ask which one
            lines = [f"📋 Acc '{account['name']}' có {len(groups)} nhóm. Gửi vào nhóm nào?"]
            for i, g in enumerate(groups[:10], 1):
                name = g.get("name", "?")
                gid = g.get("groupId", "?")
                lines.append(f"  {i}. {name}")
            lines.append("")
            lines.append(f"💡 Gõ: 'gửi cho {account['name']} qua zalo nhóm <tên nhóm> <nội dung>'")
            return "\n".join(lines)

    # ─── List groups ──────────────────────────────────────────────────
    if action == "list_groups":
        account_name = cmd.get("account_name", "")
        account = accounts.find_account(account_name)
        if not account:
            return f"❌ Không tìm thấy acc '{account_name}'"

        profile = account.get("profile")
        groups = zalo_api.list_groups(profile=profile)
        if not groups:
            return f"❌ Acc '{account['name']}' không có nhóm nào"

        lines = [f"📋 {len(groups)} nhóm của '{account['name']}':"]
        for i, g in enumerate(groups, 1):
            name = g.get("name", "?")
            gid = g.get("groupId", "?")
            members = g.get("totalMember", "?")
            lines.append(f"  {i}. {name} ({members}tv) - ID: {gid}")
        return "\n".join(lines)

    # ─── List accounts ────────────────────────────────────────────────
    if action == "list_accounts":
        accs = accounts.list_accounts()
        if not accs:
            return "📱 Chưa có acc Zalo nào. Gõ 'đăng nhập zalo với tên <tên>' để thêm."

        lines = [f"📱 {len(accs)} acc Zalo:"]
        for acc in accs:
            name = acc.get("name", "?")
            zalo_id = acc.get("zalo_id", "?")
            display = acc.get("display_name", "")
            display_str = f" ({display})" if display else ""
            lines.append(f"  • {name}{display_str} - ID: {zalo_id}")
        return "\n".join(lines)

    # ─── Status ───────────────────────────────────────────────────────
    if action == "status":
        accs = accounts.list_accounts()
        if not accs:
            return "📱 Chưa có acc Zalo nào."

        lines = [f"📊 Trạng thái {len(accs)} acc Zalo:"]
        for acc in accs:
            profile = acc.get("profile")
            status = login_module.check_login_status(profile)
            name = acc.get("name", "?")
            if status.get("logged_in"):
                lines.append(f"  🟢 {name}: {status['user_id']} - {status['display_name']}")
            else:
                lines.append(f"  🔴 {name}: Mất kết nối")
        return "\n".join(lines)

    # ─── Send image ───────────────────────────────────────────────────
    if action == "send_image":
        account, profile, err = _resolve_account(cmd)
        if err:
            return err

        media_url = cmd.get("media_url", "")
        caption = cmd.get("caption", "")

        groups = zalo_api.list_groups(profile=profile)
        if not groups:
            return f"❌ Acc '{account['name']}' không có nhóm nào"

        target = groups[0]
        target_id = target["groupId"]
        target_name = target.get("name", target_id)

        success = zalo_api.send_image(target_id, media_url, caption=caption, is_group=True, profile=profile)
        if success:
            return f"✅ Đã gửi ảnh qua '{account['name']}' → {target_name}"
        else:
            return f"❌ Gửi ảnh thất bại"

    # ─── Send file ────────────────────────────────────────────────────
    if action == "send_file":
        account, profile, err = _resolve_account(cmd)
        if err:
            return err

        media_url = cmd.get("media_url", "")

        groups = zalo_api.list_groups(profile=profile)
        if not groups:
            return f"❌ Acc '{account['name']}' không có nhóm nào"

        target = groups[0]
        target_id = target["groupId"]
        target_name = target.get("name", target_id)

        # Send file as attachment via msg send with link
        success = zalo_api.send_message(target_id, f"📎 {media_url}", is_group=True, profile=profile)
        if success:
            return f"✅ Đã gửi file qua '{account['name']}' → {target_name}"
        else:
            return f"❌ Gửi file thất bại"

    # ─── Send voice ───────────────────────────────────────────────────
    if action == "send_voice":
        account, profile, err = _resolve_account(cmd)
        if err:
            return err

        media_url = cmd.get("media_url", "")

        groups = zalo_api.list_groups(profile=profile)
        if not groups:
            return f"❌ Acc '{account['name']}' không có nhóm nào"

        target = groups[0]
        target_id = target["groupId"]
        target_name = target.get("name", target_id)

        success = zalo_api.send_voice(target_id, media_url, is_group=True, profile=profile)
        if success:
            return f"✅ Đã gửi voice qua '{account['name']}' → {target_name}"
        else:
            return f"❌ Gửi voice thất bại"

    # ─── Schedule (cron) ──────────────────────────────────────────────
    if action == "schedule":
        account, profile, err = _resolve_account(cmd)
        if err:
            return err

        schedule_text = cmd.get("schedule", "")
        message = cmd.get("message", "")

        import scheduler
        schedule_config = scheduler.parse_schedule(schedule_text)
        if not schedule_config:
            return f"❌ Không hiểu lịch: '{schedule_text}'. Ví dụ: 'mỗi 1 giờ', 'hàng ngày 9h', 'mỗi 30 phút'"

        job = scheduler.create_job(
            account_name=account["name"],
            message=message,
            schedule_config=schedule_config,
        )

        if "error" in job:
            return f"❌ {job['error']}"

        desc = scheduler._describe_schedule(schedule_config)
        return (
            f"✅ Đã tạo lịch gửi!\n"
            f"Acc: {account['name']}\n"
            f"Lịch: {desc}\n"
            f"Nội dung: {message[:100]}...\n"
            f"Job ID: {job['id']}"
        )

    return "❓ Không hiểu lệnh"


def _make_qr_response(name: str, profile: str, result: Dict) -> Dict:
    """Create QR login response dict."""
    return {
        "_type": "qr_login",
        "name": name,
        "profile": profile,
        "qr_base64": result.get("qr_base64"),
        "qr_path": result.get("qr_path"),
        "message": f"📱 Quét QR code để đăng nhập Zalo '{name}'",
    }


def handle_after_qr_scan(name: str, profile: str) -> str:
    """Called after QR is scanned. Register the account and return confirmation."""
    status = login_module.check_login_status(profile)
    if status.get("logged_in"):
        account = accounts.register_account(
            name=name,
            zalo_id=status["user_id"],
            display_name=status["display_name"],
            profile=profile,
        )
        return (
            f"✅ Đăng nhập '{name}' thành công!\n"
            f"Zalo ID: {status['user_id']}\n"
            f"Tên Zalo: {status['display_name']}\n"
            f"Bây giờ anh có thể nói: 'gửi cho {name} qua zalo ...' để gửi tin nhắn."
        )
    return f"❌ Chưa quét QR hoặc login thất bại cho '{name}'"
