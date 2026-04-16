"""Tests for scheduler module."""

import pytest
import scheduler


class TestParseSchedule:
    def test_every_hour(self):
        result = scheduler.parse_schedule("mỗi 1 giờ")
        assert result is not None
        assert result["type"] == "interval"
        assert result["seconds"] == 3600

    def test_every_30_minutes(self):
        result = scheduler.parse_schedule("mỗi 30 phút")
        assert result is not None
        assert result["type"] == "interval"
        assert result["seconds"] == 1800

    def test_every_day(self):
        result = scheduler.parse_schedule("mỗi 1 ngày")
        assert result is not None
        assert result["type"] == "interval"
        assert result["seconds"] == 86400

    def test_every_week(self):
        result = scheduler.parse_schedule("mỗi 1 tuần")
        assert result is not None
        assert result["type"] == "interval"
        assert result["seconds"] == 604800

    def test_daily(self):
        result = scheduler.parse_schedule("hàng ngày")
        assert result is not None
        assert result["type"] == "daily"
        assert result["time"] == "08:00"

    def test_daily_at_time(self):
        result = scheduler.parse_schedule("hàng ngày 9h")
        assert result is not None
        assert result["type"] == "daily"
        assert result["time"] == "09:00"

    def test_time_only(self):
        result = scheduler.parse_schedule("9:00 hàng ngày")
        assert result is not None
        assert result["type"] == "daily"
        assert "09:00" in result["time"] or result["time"] == "9:00"

    def test_time_colon(self):
        result = scheduler.parse_schedule("14:30")
        assert result is not None
        assert result["type"] == "daily"
        assert result["time"] == "14:30"

    def test_every_2_hours(self):
        result = scheduler.parse_schedule("mỗi 2 giờ")
        assert result is not None
        assert result["seconds"] == 7200

    def test_invalid(self):
        result = scheduler.parse_schedule("some random text")
        assert result is None


class TestDescribeSchedule:
    def test_interval_hours(self):
        desc = scheduler._describe_schedule({"type": "interval", "seconds": 3600})
        assert "giờ" in desc

    def test_interval_minutes(self):
        desc = scheduler._describe_schedule({"type": "interval", "seconds": 1800})
        assert "phút" in desc

    def test_daily(self):
        desc = scheduler._describe_schedule({"type": "daily", "time": "09:00"})
        assert "hàng ngày" in desc
        assert "09:00" in desc


class TestUnitToSeconds:
    def test_hours(self):
        assert scheduler._unit_to_seconds(1, "giờ") == 3600
        assert scheduler._unit_to_seconds(2, "giờ") == 7200

    def test_minutes(self):
        assert scheduler._unit_to_seconds(30, "phút") == 1800

    def test_days(self):
        assert scheduler._unit_to_seconds(1, "ngày") == 86400


class TestJobManagement:
    def test_list_jobs_empty(self):
        jobs = scheduler.list_jobs()
        assert jobs == []

    def test_remove_nonexistent(self):
        result = scheduler.remove_job("nonexistent")
        assert result is False
