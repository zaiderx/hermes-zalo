#!/usr/bin/env python3
"""BearGate CLI - manage Zalo accounts from terminal."""

import sys
import os
import json
import base64
import tempfile
import subprocess

# Add project dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import login as login_module


def cmd_login(args):
    """Login to a Zalo account.
    Usage: python cli.py login [profile_name]
    """
    profile = args[0] if args else (config.OPENZCA_PROFILES[0] if config.OPENZCA_PROFILES else "default")

    print(f"🐾 BearGate Login - Profile: {profile}")
    print("=" * 40)

    # Check if already logged in
    status = login_module.check_login_status(profile)
    if status.get("logged_in"):
        print(f"✅ Đã đăng nhập!")
        print(f"   Zalo ID: {status['user_id']}")
        print(f"   Tên: {status['display_name']}")
        return

    print("📱 Đang tạo QR code...")
    result = login_module.login_qr(profile)

    if result.get("success"):
        print(f"✅ Đăng nhập thành công!")
        print(f"   Zalo ID: {result['user_id']}")
        print(f"   Tên: {result['display_name']}")
        return

    if result.get("qr_base64"):
        qr_path = result.get("qr_path")
        print(f"📱 Quét QR code bằng Zalo trên điện thoại!")

        # Save QR as temp image and try to display
        if qr_path and os.path.exists(qr_path):
            print(f"   QR saved: {qr_path}")

            # Try to display in terminal using various methods
            if _try_display_qr_terminal(qr_path):
                pass
            else:
                print(f"   Không thể hiển thị QR trong terminal.")
                print(f"   Mở file: {qr_path}")
                print(f"   Hoặc dùng lệnh: python cli.py qr {profile}")

            # Wait for scan
            print("\n⏳ Đang chờ quét QR...")
            print("   (Timeout: 2 phút)")
            # openzca auth login will block until scanned or timeout
            try:
                recheck = login_module.login_qr(profile, qr_base64=False)
                if recheck.get("success") or recheck.get("user_id"):
                    user_id = recheck.get("user_id", "?")
                    print(f"\n✅ Đăng nhập thành công! Zalo ID: {user_id}")
                elif recheck.get("error") == "timeout":
                    print("\n❌ Timeout - anh chưa quét QR?")
                else:
                    print(f"\n❌ Lỗi: {recheck.get('error') or recheck.get('message', 'Unknown')}")
            except KeyboardInterrupt:
                print("\n⏹ Hủy đăng nhập")
        else:
            print(f"❌ Không tạo được QR image")
            print(f"   Raw: {result.get('message', '')[:200]}")
    else:
        print(f"❌ Lỗi: {result.get('error') or result.get('message', 'Unknown')}")


def _try_display_qr_terminal(qr_path: str) -> bool:
    """Try to display QR code in terminal using various tools."""
    methods = [
        # kitty icat
        ["kitten", "icat", qr_path],
        # chafa
        ["chafa", qr_path],
        # timg
        ["timg", qr_path],
        # viu (Rust)
        ["viu", qr_path],
        # jp2a (ascii art)
        ["jp2a", "--color", qr_path],
    ]

    for method in methods:
        try:
            result = subprocess.run(
                method,
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                sys.stdout.buffer.write(result.stdout)
                sys.stdout.flush()
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False


def cmd_status(args):
    """Show status of all Zalo accounts."""
    print("📊 BearGate Account Status")
    print("=" * 40)

    profiles = config.OPENZCA_PROFILES
    for profile in profiles:
        label = config.get_profile_config(profile).get("label", "")
        label_str = f" ({label})" if label else ""

        status = login_module.check_login_status(profile)
        if status.get("logged_in"):
            print(f"  🟢 {profile}{label_str}")
            print(f"     ID: {status['user_id']}")
            print(f"     Tên: {status['display_name']}")
        else:
            print(f"  🔴 {profile}{label_str} - Chưa đăng nhập")


def cmd_logout(args):
    """Logout from a Zalo account."""
    profile = args[0] if args else (config.OPENZCA_PROFILES[0] if config.OPENZCA_PROFILES else "default")
    result = login_module.logout(profile)
    if result.get("success"):
        print(f"✅ Đã đăng xuất '{profile}'")
    else:
        print(f"❌ Lỗi: {result.get('error')}")


def cmd_groups(args):
    """List groups for a profile."""
    import zalo_api
    profile = args[0] if args else None
    groups = zalo_api.list_groups(profile=profile)
    p = profile or (config.OPENZCA_PROFILES[0] if config.OPENZCA_PROFILES else "default")
    print(f"📋 {len(groups)} nhóm ({p}):")
    for i, g in enumerate(groups, 1):
        name = g.get("name", "?")
        gid = g.get("groupId", "?")
        members = g.get("totalMember", "?")
        print(f"  {i}. {name} ({members}tv) - ID: {gid}")


def cmd_profiles(args):
    """List all configured profiles."""
    print(f"📱 {len(config.OPENZCA_PROFILES)} Zalo profiles configured:")
    for p in config.OPENZCA_PROFILES:
        label = config.get_profile_config(p).get("label", "")
        label_str = f" ({label})" if label else ""
        print(f"  • {p}{label_str}")


def main():
    if len(sys.argv) < 2:
        print("🐾 BearGate CLI")
        print("Usage: python cli.py <command> [args]")
        print()
        print("Commands:")
        print("  login [profile]    - Login to Zalo (QR code)")
        print("  logout [profile]   - Logout from Zalo")
        print("  status             - Show account status")
        print("  profiles           - List configured profiles")
        print("  groups [profile]   - List groups")
        return

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    commands = {
        "login": cmd_login,
        "logout": cmd_logout,
        "status": cmd_status,
        "profiles": cmd_profiles,
        "groups": cmd_groups,
    }

    handler = commands.get(cmd)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {cmd}")
        print("Available: login, logout, status, profiles, groups")


if __name__ == "__main__":
    main()
