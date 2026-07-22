from __future__ import annotations

import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


USER = {"id": "admin-1", "role": "owner", "name": "Admin User", "initials": "AU"}
CONVERSATIONS = []
MESSAGES = {}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format, *args):
        return

    def _headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
        self.send_header("Content-Type", content_type)

    def _json(self, payload, status=200, extra_headers=None):
        body = json.dumps(payload).encode("utf-8")
        self._headers(status)
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_OPTIONS(self):
        self._headers(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/auth/refresh":
            if "eduflow_refresh_token=e2e-refresh" not in self.headers.get("Cookie", ""):
                return self._json({"detail": "Not authenticated"}, 401)
            return self._json({"success": True, "access_token": "e2e-access", "token": "e2e-access", "user": USER})
        if path == "/api/tokens/usage/me":
            return self._json({"success": True, "data": {"total_used": 0, "role_limit": 50000, "self_recharge_enabled": True}})
        if path == "/api/chat/conversations":
            return self._json({"success": True, "data": CONVERSATIONS})
        if path.startswith("/api/chat/conversations/") and path.endswith("/messages"):
            conversation_id = path.split("/")[4]
            return self._json({"success": True, "data": MESSAGES.get(conversation_id, [])})
        if path == "/api/search":
            return self._json({"success": True, "data": []})
        return self._json({"detail": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/auth/login":
            body = self._read_json()
            if body.get("username") != "admin" or body.get("password") != "admin123":
                return self._json({"detail": "Invalid username or password"}, 401)
            return self._json(
                {"success": True, "access_token": "e2e-access", "token": "e2e-access", "user": USER},
                extra_headers={"Set-Cookie": "eduflow_refresh_token=e2e-refresh; HttpOnly; SameSite=Lax; Path=/"},
            )
        if path == "/api/auth/refresh":
            if "eduflow_refresh_token=e2e-refresh" not in self.headers.get("Cookie", ""):
                return self._json({"detail": "Not authenticated"}, 401)
            return self._json({"success": True, "access_token": "e2e-access", "token": "e2e-access", "user": USER})
        if path == "/api/auth/logout":
            self._read_json()
            return self._json({"success": True}, extra_headers={"Set-Cookie": "eduflow_refresh_token=; Max-Age=0; Path=/"})
        if path.startswith("/api/tools/") and path.endswith("/execute"):
            self._read_json()
            # THIS DOUBLE'S JOB IS TO MIRROR PRODUCTION, NOT TO MODEL WHAT PRODUCTION
            # OUGHT TO DO. It already returned the single, correct envelope while the
            # real server returned a double-wrapped one — so every browser test passed
            # against a server that did not exist, and eleven screens showed zeros for
            # an entire initiative before a human noticed (UI Sweep, Epic 4).
            # If you change the endpoint's shape, change it here in the same commit.
            return self._json({
                "success": True,
                "data": {
                    "summary": {
                        "attendance_rate": "92%",
                        "total_students": 120,
                        "attendance_marked_today": True,
                    },
                    "fee_stats": {"paid": "Rs 10,000"},
                    "active_alerts": 0,
                },
                "meta": {"count": 120},
                "message": "",
                "denied": False,
            })
        if path == "/api/chat/conversations":
            self._read_json()
            conversation = {"id": str(uuid.uuid4()), "title": "E2E conversation", "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            CONVERSATIONS.insert(0, conversation)
            MESSAGES[conversation["id"]] = []
            return self._json({"success": True, "data": conversation})
        if path.startswith("/api/chat/conversations/") and path.endswith("/messages"):
            return self._stream_chat()
        return self._json({"detail": "Not found"}, 404)

    def _stream_chat(self):
        self._read_json()
        self._headers(200, "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        events = [
            {"type": "thinking", "step": "lookup", "message": "Checking school data"},
            {"type": "text_delta", "delta": "Here is a concise school summary for your request."},
            {"type": "done", "message_id": str(uuid.uuid4()), "tokens_used": 12},
        ]
        for event in events:
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode("utf-8"))
            self.wfile.flush()
        self.close_connection = True


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
