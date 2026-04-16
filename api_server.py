"""HTTP API server - receive commands from Hermes cron or external callers."""

import json
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any
from urllib.parse import urlparse, parse_qs

import config
import zalo_api
import accounts
import scheduler
import login as login_module

logger = logging.getLogger("hermes-zalo.api")

_server: HTTPServer | None = None
_api_key = os.getenv("HERMES_ZALO_API_KEY", "")
_api_port = int(os.getenv("HERMES_ZALO_API_PORT", "8199"))


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for hermes-zalo API."""

    def log_message(self, format, *args):
        logger.debug(f"[API] {format % args}")

    def _check_auth(self) -> bool:
        """Check API key if configured."""
        if not _api_key:
            return True  # No auth required

        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return token == _api_key

        # Also check query param
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        api_key_param = params.get("api_key", [None])[0]
        return api_key_param == _api_key

    def _respond(self, status: int, data: Any):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _read_body(self) -> Dict:
        """Read and parse JSON body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body)

    def do_GET(self):
        if not self._check_auth():
            self._respond(401, {"error": "Unauthorized"})
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # GET /health
        if path == "/health":
            self._respond(200, {"status": "ok", "service": "hermes-zalo"})
            return

        # GET /openapi.yaml - OpenAPI spec
        if path == "/openapi.yaml" or path == "/openapi.json":
            spec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openapi.yaml")
            try:
                with open(spec_path, "r", encoding="utf-8") as f:
                    spec = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/yaml; charset=utf-8")
                self.end_headers()
                self.wfile.write(spec.encode("utf-8"))
            except FileNotFoundError:
                self._respond(404, {"error": "openapi.yaml not found"})
            return

        # GET /docs - Swagger UI redirect
        if path == "/docs" or path == "/swagger":
            html = """<!DOCTYPE html>
<html><head><title>Hermes-Zalo API Docs</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head><body><div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url: '/openapi.yaml', dom_id: '#swagger-ui'})</script>
</body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # GET /accounts
        if path == "/accounts":
            accs = accounts.list_accounts()
            self._respond(200, {"accounts": accs})
            return

        # GET /accounts/{name}/groups
        if path.startswith("/accounts/") and path.endswith("/groups"):
            parts = path.split("/")
            if len(parts) >= 3:
                name = parts[2]
                account = accounts.find_account(name)
                if not account:
                    self._respond(404, {"error": f"Account '{name}' not found"})
                    return
                groups = zalo_api.list_groups(profile=account["profile"])
                self._respond(200, {"groups": groups})
                return

        # GET /status
        if path == "/status":
            accs = accounts.list_accounts()
            results = []
            for acc in accs:
                status = login_module.check_login_status(acc["profile"])
                results.append({
                    "name": acc["name"],
                    "logged_in": status.get("logged_in", False),
                    "user_id": status.get("user_id"),
                    "display_name": status.get("display_name"),
                })
            self._respond(200, {"accounts": results})
            return

        # GET /schedules
        if path == "/schedules":
            jobs = scheduler.list_jobs()
            self._respond(200, {"jobs": jobs})
            return

        self._respond(404, {"error": f"Not found: {path}"})

    def do_POST(self):
        if not self._check_auth():
            self._respond(401, {"error": "Unauthorized"})
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_body()

        # POST /send - Send message
        # Body: {"account": "Duy Phong", "group": "Công ty", "message": "Hello"}
        if path == "/send":
            account_name = body.get("account", "")
            group_name = body.get("group", "")
            message = body.get("message", "")

            if not account_name or not message:
                self._respond(400, {"error": "Missing 'account' or 'message'"})
                return

            account = accounts.find_account(account_name)
            if not account:
                self._respond(404, {"error": f"Account '{account_name}' not found"})
                return

            profile = account["profile"]

            # Find target group
            if group_name:
                group = zalo_api.find_group_by_name(group_name, profile=profile)
                if not group:
                    self._respond(404, {"error": f"Group '{group_name}' not found"})
                    return
                target_id = group["groupId"]
                target_name = group.get("name", target_id)
            else:
                groups = zalo_api.list_groups(profile=profile)
                if not groups:
                    self._respond(404, {"error": "No groups found"})
                    return
                target_id = groups[0]["groupId"]
                target_name = groups[0].get("name", target_id)

            success = zalo_api.send_message(target_id, message, is_group=True, profile=profile)
            if success:
                self._respond(200, {
                    "success": True,
                    "account": account_name,
                    "group": target_name,
                    "message_length": len(message),
                })
            else:
                self._respond(500, {"error": "Send failed"})
            return

        # POST /send-image - Send image
        # Body: {"account": "Duy Phong", "group": "Công ty", "url": "https://...", "caption": ""}
        if path == "/send-image":
            account_name = body.get("account", "")
            url = body.get("url", "")
            caption = body.get("caption", "")

            if not account_name or not url:
                self._respond(400, {"error": "Missing 'account' or 'url'"})
                return

            account = accounts.find_account(account_name)
            if not account:
                self._respond(404, {"error": f"Account '{account_name}' not found"})
                return

            profile = account["profile"]
            groups = zalo_api.list_groups(profile=profile)
            if not groups:
                self._respond(404, {"error": "No groups found"})
                return

            target = groups[0]
            success = zalo_api.send_image(target["groupId"], url, caption=caption, is_group=True, profile=profile)
            self._respond(200, {"success": success})
            return

        # POST /send-voice - Send voice
        # Body: {"account": "Duy Phong", "url": "https://..."}
        if path == "/send-voice":
            account_name = body.get("account", "")
            url = body.get("url", "")

            if not account_name or not url:
                self._respond(400, {"error": "Missing 'account' or 'url'"})
                return

            account = accounts.find_account(account_name)
            if not account:
                self._respond(404, {"error": f"Account '{account_name}' not found"})
                return

            profile = account["profile"]
            groups = zalo_api.list_groups(profile=profile)
            if not groups:
                self._respond(404, {"error": "No groups found"})
                return

            target = groups[0]
            success = zalo_api.send_voice(target["groupId"], url, is_group=True, profile=profile)
            self._respond(200, {"success": success})
            return

        # POST /schedule - Create scheduled job
        # Body: {"account": "Duy Phong", "group": "Công ty", "message": "...", "schedule": "mỗi 1 giờ"}
        if path == "/schedule":
            account_name = body.get("account", "")
            message = body.get("message", "")
            schedule_text = body.get("schedule", "")
            group_name = body.get("group", None)

            if not account_name or not message or not schedule_text:
                self._respond(400, {"error": "Missing required fields"})
                return

            schedule_config = scheduler.parse_schedule(schedule_text)
            if not schedule_config:
                self._respond(400, {"error": f"Cannot parse schedule: {schedule_text}"})
                return

            job = scheduler.create_job(
                account_name=account_name,
                message=message,
                schedule_config=schedule_config,
                group_name=group_name,
            )

            if "error" in job:
                self._respond(400, job)
            else:
                self._respond(200, {"success": True, "job": job})
            return

        # POST /schedule/remove - Remove scheduled job
        # Body: {"job_id": "abc123"}
        if path == "/schedule/remove":
            job_id = body.get("job_id", "")
            if not job_id:
                self._respond(400, {"error": "Missing 'job_id'"})
                return

            success = scheduler.remove_job(job_id)
            self._respond(200, {"success": success})
            return

        self._respond(404, {"error": f"Not found: {path}"})


def start():
    """Start the API server."""
    global _server
    _server = HTTPServer(("0.0.0.0", _api_port), APIHandler)
    thread = threading.Thread(target=_server.serve_forever, daemon=True, name="api-server")
    thread.start()
    logger.info(f"[API] Server started on port {_api_port}")


def stop():
    """Stop the API server."""
    global _server
    if _server:
        _server.shutdown()
        _server = None
        logger.info("[API] Server stopped")
