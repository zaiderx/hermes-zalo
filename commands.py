"""Command handler - process outbound commands from Zalo DMs or cron."""

import json
import logging
import re
from typing import Optional, Dict, Any

import zalo_api
import hermes_bridge
import config

logger = logging.getLogger("hermes-zalo.commands")


def process_command(sender_id: str, text: str, sender_name: str = None, profile: str = None) -> Optional[str]:
    """Process a command from a Zalo DM.

    Commands start with / or ! prefix. Returns response text or None.

    Supported commands:
        /profiles               - List all Zalo accounts
        /groups, /nhóm          - List all groups (current profile)
        /allgroups              - List groups across all profiles
        /find <name>            - Find group by name
        /send <group> <msg>     - Send message to group
        /members <group>        - List group members
        /info <group>           - Group info
        /me                     - Bot profile
        /ask <question>         - Ask Hermes AI
        /help                   - Show help
    """
    text = text.strip()
    if not text or text[0] not in ("/", "!"):
        return None

    parts = text.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    logger.info(f"[CMD] {sender_name or sender_id}: {text}")

    # ─── /help ────────────────────────────────────────────────────────
    if cmd in ("/help", "/giúp", "!help"):
        return (
            "🐾 Hermes-Zalo Commands:\n"
            "/login [acc] - Đăng nhập Zalo (QR code)\n"
            "/logout [acc] - Đăng xuất Zalo\n"
            "/status - Trạng thái các acc\n"
            "/profiles - Xem tất cả acc Zalo\n"
            "/groups - Xem nhóm (acc hiện tại)\n"
            "/allgroups - Xem tất cả nhóm (mọi acc)\n"
            "/find <tên> - Tìm nhóm\n"
            "/send <nhóm> <tin nhắn> - Gửi tin vào nhóm\n"
            "/members <nhóm> - Xem thành viên\n"
            "/info <nhóm> - Thông tin nhóm\n"
            "/me - Thông tin bot\n"
            "/ask <câu hỏi> - Hỏi Hermes AI\n"
            "/help - Menu này"
        )

    # ─── /profiles ────────────────────────────────────────────────────
    if cmd in ("/profiles", "/acc", "/tài khoản", "!profiles"):
        profiles = config.OPENZCA_PROFILES
        lines = [f"📱 {len(profiles)} Zalo accounts:"]
        for p in profiles:
            own_id = config.get_own_id(p) or "?"
            label = config.get_profile_config(p).get("label", "")
            status = "🟢" if own_id != "?" else "🔴"
            label_str = f" ({label})" if label else ""
            lines.append(f"  {status} {p}{label_str} - ID: {own_id}")
        return "\n".join(lines)

    # ─── /groups ──────────────────────────────────────────────────────
    if cmd in ("/groups", "/nhóm", "!groups"):
        groups = zalo_api.list_groups(profile=profile)
        if not groups:
            return "Không tìm thấy nhóm nào."
        p = profile or "default"
        lines = [f"📋 {len(groups)} nhóm ({p}):"]
        for i, g in enumerate(groups, 1):
            name = g.get("name", "Unknown")
            gid = g.get("groupId", "")
            members = g.get("totalMember", "?")
            lines.append(f"{i}. {name} ({members}tv)\n   ID: {gid}")
        return "\n".join(lines)

    # ─── /allgroups ───────────────────────────────────────────────────
    if cmd in ("/allgroups", "/tất cả nhóm", "!allgroups"):
        all_groups = zalo_api.list_all_profiles_groups()
        if not all_groups:
            return "Không tìm thấy nhóm nào."
        lines = []
        total = 0
        for p, groups in all_groups.items():
            lines.append(f"📱 {p} ({len(groups)} nhóm):")
            for g in groups[:5]:
                name = g.get("name", "?")
                members = g.get("totalMember", "?")
                lines.append(f"  • {name} ({members}tv)")
                total += 1
            if len(groups) > 5:
                lines.append(f"  ... +{len(groups) - 5} nhóm nữa")
        lines.insert(0, f"📋 Tổng {total} nhóm từ {len(all_groups)} acc:")
        return "\n".join(lines)

    # ─── /find <name> ────────────────────────────────────────────────
    if cmd in ("/find", "/tìm", "!find"):
        if not args:
            return "Cú pháp: /find <tên nhóm>"

        # Search in current profile first
        group = zalo_api.find_group_by_name(args, profile=profile)
        if group:
            p = profile or "default"
            return (
                f"🔍 Tìm thấy ({p}):\n"
                f"Tên: {group.get('name', '?')}\n"
                f"ID: {group.get('groupId', '?')}\n"
                f"Thành viên: {group.get('totalMember', '?')}"
            )

        # Search across all profiles
        group = zalo_api.find_group_across_profiles(args)
        if group:
            p = group.get("_profile", "?")
            return (
                f"🔍 Tìm thấy ở acc {p}:\n"
                f"Tên: {group.get('name', '?')}\n"
                f"ID: {group.get('groupId', '?')}\n"
                f"Thành viên: {group.get('totalMember', '?')}"
            )

        return f"Không tìm thấy nhóm nào có tên '{args}'"

    # ─── /send <group_name_or_id> <message> ──────────────────────────
    if cmd in ("/send", "/gửi", "!send"):
        parts = args.split(None, 1)
        if len(parts) < 2:
            return "Cú pháp: /send <tên hoặc ID nhóm> <tin nhắn>"

        group_ref, message = parts

        if group_ref.isdigit():
            target_id = group_ref
            group_name = group_ref
            send_profile = profile
        else:
            # Search in current profile
            group = zalo_api.find_group_by_name(group_ref, profile=profile)
            if group:
                target_id = group["groupId"]
                group_name = group.get("name", target_id)
                send_profile = profile
            else:
                # Search across profiles
                group = zalo_api.find_group_across_profiles(group_ref)
                if group:
                    target_id = group["groupId"]
                    group_name = group.get("name", target_id)
                    send_profile = group.get("_profile")
                else:
                    return f"Không tìm thấy nhóm '{group_ref}'. Dùng /find để tìm."

        success = zalo_api.send_message(target_id, message, is_group=True, profile=send_profile)
        if success:
            return f"✅ Đã gửi tới {group_name}: {message[:50]}..."
        else:
            return f"❌ Gửi thất bại tới {group_name}"

    # ─── /members <group_name_or_id> ─────────────────────────────────
    if cmd in ("/members", "/thành viên", "!members"):
        if not args:
            return "Cú pháp: /members <tên hoặc ID nhóm>"

        if args.isdigit():
            group_id = args
        else:
            group = zalo_api.find_group_by_name(args, profile=profile)
            if not group:
                group = zalo_api.find_group_across_profiles(args)
            if not group:
                return f"Không tìm thấy nhóm '{args}'"
            group_id = group["groupId"]

        members = zalo_api.list_group_members(group_id, profile=profile)
        if not members:
            return "Không lấy được danh sách thành viên."
        lines = [f"👥 {len(members)} thành viên:"]
        for m in members[:20]:
            name = m.get("displayName") or m.get("memberId", "?")
            lines.append(f"  • {name}")
        if len(members) > 20:
            lines.append(f"  ... và {len(members) - 20} người nữa")
        return "\n".join(lines)

    # ─── /info <group_name_or_id> ────────────────────────────────────
    if cmd in ("/info", "!info"):
        if not args:
            return "Cú pháp: /info <tên hoặc ID nhóm>"

        if args.isdigit():
            group_id = args
        else:
            group = zalo_api.find_group_by_name(args, profile=profile)
            if not group:
                group = zalo_api.find_group_across_profiles(args)
            if not group:
                return f"Không tìm thấy nhóm '{args}'"
            group_id = group["groupId"]

        info = zalo_api.get_group_info(group_id, profile=profile)
        if "error" in info:
            return f"Lỗi: {info['error']}"
        return json.dumps(info, ensure_ascii=False, indent=2)

    # ─── /me ─────────────────────────────────────────────────────────
    if cmd in ("/me", "!me"):
        profile_info = zalo_api.get_own_profile(profile=profile)
        if "error" in profile_info:
            return f"Lỗi: {profile_info['error']}"
        return json.dumps(profile_info, ensure_ascii=False, indent=2)

    # ─── /ask <question> ─────────────────────────────────────────────
    if cmd in ("/hỏi", "/ask", "!ask"):
        if not args:
            return "Cú pháp: /ask <câu hỏi>"
        response = hermes_bridge.call_hermes(
            prompt=args,
            sender_name=sender_name,
        )
        return response

    # ─── /login ──────────────────────────────────────────────────────
    if cmd in ("/login", "/đăng nhập", "!login"):
        import login as login_module
        target_profile = args.strip() if args else profile

        # Check current status first
        status = login_module.check_login_status(target_profile)
        if status.get("logged_in"):
            return (
                f"✅ Đã đăng nhập!\n"
                f"Profile: {target_profile}\n"
                f"Zalo ID: {status['user_id']}\n"
                f"Tên: {status['display_name']}"
            )

        # Generate QR code
        result = login_module.login_qr(target_profile)
        if result.get("success"):
            return (
                f"✅ Đăng nhập thành công!\n"
                f"Profile: {target_profile}\n"
                f"Zalo ID: {result['user_id']}\n"
                f"Tên: {result['display_name']}"
            )
        elif result.get("qr_base64"):
            # Return special marker for QR image
            return {
                "_type": "qr_login",
                "profile": target_profile,
                "qr_base64": result["qr_base64"],
                "qr_path": result.get("qr_path"),
                "message": f"📱 Quét QR code để đăng nhập acc '{target_profile}'",
            }
        else:
            return f"❌ Lỗi đăng nhập: {result.get('error') or result.get('message', 'Unknown')}"

    # ─── /logout ─────────────────────────────────────────────────────
    if cmd in ("/logout", "/đăng xuất", "!logout"):
        import login as login_module
        target_profile = args.strip() if args else profile
        result = login_module.logout(target_profile)
        if result.get("success"):
            return f"✅ Đã đăng xuất acc '{target_profile}'"
        else:
            return f"❌ Lỗi: {result.get('error')}"

    # ─── /status ─────────────────────────────────────────────────────
    if cmd in ("/status", "/trạng thái", "!status"):
        import login as login_module
        results = login_module.list_profiles_status()
        lines = [f"📊 Trạng thái {len(results)} acc:"]
        for r in results:
            p = r["profile"]
            label = r.get("label", "")
            label_str = f" ({label})" if label else ""
            if r.get("logged_in"):
                lines.append(f"  🟢 {p}{label_str}: {r['user_id']} - {r['display_name']}")
            else:
                lines.append(f"  🔴 {p}{label_str}: Chưa đăng nhập")
        return "\n".join(lines)

    return f"❓ Lệnh không hợp lệ: {cmd}. Gõ /help để xem danh sách lệnh."
