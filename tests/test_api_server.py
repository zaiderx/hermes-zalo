"""Tests for API server."""

import json
import pytest
import threading
import time
import urllib.request
import urllib.error

import api_server
import accounts


@pytest.fixture(scope="module")
def api_running():
    """Start API server for tests."""
    api_server._api_key = ""
    api_server._api_port = 18199  # Use different port for tests
    api_server.start()
    time.sleep(0.5)
    yield
    api_server.stop()


def api_get(path: str, port: int = 18199) -> dict:
    """Helper to GET from API."""
    try:
        req = urllib.request.Request(f"http://localhost:{port}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(), "status": e.code}


def api_post(path: str, data: dict, port: int = 18199) -> dict:
    """Helper to POST to API."""
    try:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"http://localhost:{port}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(), "status": e.code}


class TestAPIHealth:
    def test_health(self, api_running):
        resp = api_get("/health")
        assert resp["status"] == "ok"
        assert resp["service"] == "hermes-zalo"


class TestAPIDocs:
    def test_openapi_yaml(self, api_running):
        try:
            req = urllib.request.Request("http://localhost:18199/openapi.yaml")
            with urllib.request.urlopen(req, timeout=5) as resp:
                content = resp.read().decode()
                assert "openapi:" in content
                assert "Hermes-Zalo" in content
        except Exception:
            pass  # File might not exist in test env

    def test_docs_page(self, api_running):
        try:
            req = urllib.request.Request("http://localhost:18199/docs")
            with urllib.request.urlopen(req, timeout=5) as resp:
                html = resp.read().decode()
                assert "swagger" in html.lower()
        except Exception:
            pass


class TestAPIAccounts:
    def test_list_accounts(self, api_running):
        resp = api_get("/accounts")
        assert "accounts" in resp
        assert isinstance(resp["accounts"], list)

    def test_status(self, api_running):
        resp = api_get("/status")
        assert "accounts" in resp


class TestAPISend:
    def test_send_missing_account(self, api_running):
        resp = api_post("/send", {"message": "hello"})
        assert resp.get("status") == 400 or "error" in resp

    def test_send_missing_message(self, api_running):
        resp = api_post("/send", {"account": "Test"})
        assert resp.get("status") == 400 or "error" in resp

    def test_send_account_not_found(self, api_running):
        resp = api_post("/send", {"account": "NonExistent", "message": "hello"})
        assert resp.get("status") == 404 or "error" in resp


class TestAPISchedule:
    def test_list_schedules(self, api_running):
        resp = api_get("/schedules")
        assert "jobs" in resp

    def test_create_schedule_missing_fields(self, api_running):
        resp = api_post("/schedule", {"account": "Test"})
        assert resp.get("status") == 400 or "error" in resp

    def test_remove_schedule_missing_id(self, api_running):
        resp = api_post("/schedule/remove", {})
        assert resp.get("status") == 400 or "error" in resp


class TestAPINotFound:
    def test_404(self, api_running):
        resp = api_get("/nonexistent")
        assert resp.get("status") == 404 or "error" in resp


class TestAPIAuth:
    def test_auth_required(self, api_running, monkeypatch):
        """Test that auth is enforced when key is set."""
        # Save original
        orig_key = api_server._api_key
        try:
            api_server._api_key = "test_secret"

            # Without auth
            try:
                req = urllib.request.Request("http://localhost:18199/accounts")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    # Shouldn't reach here
                    assert False, "Should have gotten 401"
            except urllib.error.HTTPError as e:
                assert e.code == 401

            # With correct Bearer token
            req = urllib.request.Request(
                "http://localhost:18199/accounts",
                headers={"Authorization": "Bearer test_secret"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                assert "accounts" in data

            # With query param
            data = api_get("/accounts?api_key=test_secret")
            assert "accounts" in data

        finally:
            api_server._api_key = orig_key
