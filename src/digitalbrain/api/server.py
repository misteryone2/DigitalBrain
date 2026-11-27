"""Minimal authenticated read-only API (M7 baseline).

Uses stdlib http.server. Exposes real state from configured stores. No
autonomous mutation endpoints.
"""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from digitalbrain.core.audit import AuditLog
from digitalbrain.learning import SQLiteOutcomeStore
from digitalbrain.memory import SQLiteMemoryStore
from digitalbrain.planning import SQLitePlanStore


class ApiConfig:
    def __init__(self) -> None:
        self.token = os.environ.get("DIGITALBRAIN_API_TOKEN", "")
        self.memory_db = os.environ.get("DIGITALBRAIN_MEMORY_DB")
        self.plan_db = os.environ.get("DIGITALBRAIN_PLAN_DB")
        self.audit_db = os.environ.get("DIGITALBRAIN_AUDIT_DB")
        self.outcomes_db = os.environ.get("DIGITALBRAIN_OUTCOMES_DB")


def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    config = ApiConfig()

    def log_message(self, fmt: str, *args: object) -> None:  # quieter
        return

    def _auth_ok(self) -> bool:
        token = self.config.token
        if not token:
            return False
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {token}"

    def do_OPTIONS(self) -> None:  # noqa: N802
        _json(self, HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:  # noqa: N802
        if not self._auth_ok():
            _json(self, HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        limit = int((qs.get("limit") or ["20"])[0])
        try:
            if parsed.path == "/health":
                _json(self, 200, {"ok": True, "service": "digitalbrain-api"})
                return
            if parsed.path == "/plans":
                if not self.config.plan_db:
                    _json(self, 400, {"error": "DIGITALBRAIN_PLAN_DB not configured"})
                    return
                with SQLitePlanStore(self.config.plan_db) as store:
                    plans = [p.__dict__ for p in store.list_plans(limit=limit)]
                _json(self, 200, {"plans": plans})
                return
            if parsed.path == "/memory":
                if not self.config.memory_db:
                    _json(self, 400, {"error": "DIGITALBRAIN_MEMORY_DB not configured"})
                    return
                with SQLiteMemoryStore(self.config.memory_db) as store:
                    recs = [r.__dict__ for r in store.list_records(limit=limit)]
                _json(self, 200, {"memory": recs})
                return
            if parsed.path == "/audit":
                if not self.config.audit_db:
                    _json(self, 400, {"error": "DIGITALBRAIN_AUDIT_DB not configured"})
                    return
                with AuditLog(self.config.audit_db) as store:
                    ev = [e.__dict__ for e in store.list_events(limit=limit)]
                _json(self, 200, {"audit": ev})
                return
            if parsed.path == "/outcomes":
                if not self.config.outcomes_db:
                    _json(self, 400, {"error": "DIGITALBRAIN_OUTCOMES_DB not configured"})
                    return
                with SQLiteOutcomeStore(self.config.outcomes_db) as store:
                    rows = [r.__dict__ for r in store.list_outcomes(limit=limit)]
                    summary = store.summary()
                _json(self, 200, {"outcomes": rows, "summary": summary})
                return
            _json(self, 404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            _json(self, 500, {"error": str(exc)})


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"DigitalBrain API listening on http://{host}:{port}")
    server.serve_forever()
