"""Tests for natural language command parser."""

import pytest
import nl_parser


class TestNLParserLogin:
    def test_login_vietnamese(self):
        cmd = nl_parser.parse_command("đăng nhập zalo với tên Duy Phong")
        assert cmd is not None
        assert cmd["action"] == "login"
        assert cmd["name"] == "duy phong"

    def test_login_with_particle(self):
        cmd = nl_parser.parse_command("đăng nhập zalo với tên Duy Phong nhé")
        assert cmd is not None
        assert cmd["action"] == "login"
        assert "nhé" not in cmd["name"]

    def test_login_english(self):
        cmd = nl_parser.parse_command("login zalo tên Shop ABC")
        assert cmd is not None
        assert cmd["action"] == "login"

    def test_login_short(self):
        cmd = nl_parser.parse_command("zalo login Test")
        assert cmd is not None
        assert cmd["action"] == "login"

    def test_login_add(self):
        cmd = nl_parser.parse_command("thêm acc zalo Công ty")
        assert cmd is not None
        assert cmd["action"] == "login"


class TestNLParserLogout:
    def test_logout(self):
        cmd = nl_parser.parse_command("đăng xuất zalo Duy Phong")
        assert cmd is not None
        assert cmd["action"] == "logout"
        assert cmd["name"] == "duy phong"

    def test_logout_english(self):
        cmd = nl_parser.parse_command("logout zalo Test")
        assert cmd is not None
        assert cmd["action"] == "logout"


class TestNLParserSend:
    def test_send_basic(self):
        cmd = nl_parser.parse_command("gửi cho Duy Phong qua zalo chào cả nhà")
        assert cmd is not None
        assert cmd["action"] == "send"
        assert cmd["account_name"] == "duy phong"
        assert cmd["message"] == "chào cả nhà"

    def test_send_with_group(self):
        cmd = nl_parser.parse_command("gửi cho Duy Phong qua zalo nhóm Công ty báo cáo")
        assert cmd is not None
        assert cmd["action"] == "send"
        assert cmd["account_name"] == "duy phong"

    def test_send_image(self):
        cmd = nl_parser.parse_command("gửi cho Duy Phong qua zalo ảnh https://example.com/photo.jpg")
        assert cmd is not None
        assert cmd["action"] == "send_image"
        assert cmd["media_url"] == "https://example.com/photo.jpg"

    def test_send_image_with_caption(self):
        cmd = nl_parser.parse_command("gửi cho Duy Phong qua zalo ảnh https://example.com/photo.jpg báo cáo đây")
        assert cmd is not None
        assert cmd["action"] == "send_image"
        assert cmd["caption"] == "báo cáo đây"

    def test_send_voice(self):
        cmd = nl_parser.parse_command("gửi cho Duy Phong qua zalo voice https://example.com/audio.ogg")
        assert cmd is not None
        assert cmd["action"] == "send_voice"
        assert cmd["media_url"] == "https://example.com/audio.ogg"

    def test_send_file(self):
        cmd = nl_parser.parse_command("gửi cho Duy Phong qua zalo file /path/to/report.pdf")
        assert cmd is not None
        assert cmd["action"] == "send_file"
        assert cmd["media_url"] == "/path/to/report.pdf"

    def test_send_alt_pattern(self):
        cmd = nl_parser.parse_command("gửi qua zalo Duy Phong hello world")
        assert cmd is not None
        assert cmd["action"] == "send"

    def test_send_nhan(self):
        cmd = nl_parser.parse_command("nhắn Duy Phong qua zalo hello")
        assert cmd is not None
        assert cmd["action"] == "send"


class TestNLParserSchedule:
    def test_schedule_every_hour(self):
        cmd = nl_parser.parse_command("gửi cho Duy Phong qua zalo lịch mỗi 1 giờ nhắc họp")
        assert cmd is not None
        assert cmd["action"] == "schedule"
        assert cmd["schedule"] == "mỗi 1 giờ"
        assert cmd["message"] == "nhắc họp"

    def test_schedule_every_30_min(self):
        cmd = nl_parser.parse_command("gửi cho Test qua zalo lịch mỗi 30 phút check status")
        assert cmd is not None
        assert cmd["action"] == "schedule"

    def test_schedule_daily(self):
        cmd = nl_parser.parse_command("gửi cho Test qua zalo lịch hàng ngày 9h chào buổi sáng")
        assert cmd is not None
        assert cmd["action"] == "schedule"


class TestNLParserOther:
    def test_list_accounts(self):
        cmd = nl_parser.parse_command("danh sách acc zalo")
        assert cmd is not None
        assert cmd["action"] == "list_accounts"

    def test_status(self):
        cmd = nl_parser.parse_command("trạng thái zalo")
        assert cmd is not None
        assert cmd["action"] == "status"

    def test_list_groups(self):
        cmd = nl_parser.parse_command("xem nhóm Duy Phong")
        assert cmd is not None
        assert cmd["action"] == "list_groups"

    def test_not_a_command(self):
        cmd = nl_parser.parse_command("hello how are you")
        assert cmd is None

    def test_empty_string(self):
        cmd = nl_parser.parse_command("")
        assert cmd is None
