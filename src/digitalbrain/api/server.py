"""Minimal authenticated read-only API (M7 baseline).

Uses stdlib http.server. Exposes real state from configured stores. No
autonomous mutation endpoints.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from digitalbrain.core.audit import AuditLog
from digitalbrain.evolution import SQLitePromotionStore
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
        self.promotion_db = os.environ.get("DIGITALBRAIN_PROMOTION_DB")
        scopes = os.environ.get("DIGITALBRAIN_API_SCOPES", "read:*")
        self.scopes = {s.strip() for s in scopes.split(",") if s.strip()}


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
        import hmac

        token = self.config.token
        if not token:
            return False
        auth = self.headers.get("Authorization", "")
        return hmac.compare_digest(auth, f"Bearer {token}")

    def _scope_ok(self, scope: str) -> bool:
        scopes = getattr(self.config, "scopes", None) or {"read:*"}
        return "read:*" in scopes or scope in scopes

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
            if parsed.path in {"/health", "/v1/health"}:
                _json(self, 200, {"ok": True, "service": "digitalbrain-api", "version": "v1"})
                return
            if parsed.path in {"/plans", "/v1/plans"}:
                if not self._scope_ok("read:plans"):
                    _json(self, 403, {"error": "forbidden"})
                    return
                if not self.config.plan_db:
                    _json(self, 400, {"error": "DIGITALBRAIN_PLAN_DB not configured"})
                    return
                with SQLitePlanStore(self.config.plan_db) as store:
                    plans = [asdict(p) if is_dataclass(p) else p.__dict__ for p in store.list_plans(limit=limit)]
                _json(self, 200, {"plans": plans, "version": "v1"})
                return
            if parsed.path in {"/memory", "/v1/memory"}:
                if not self._scope_ok("read:memory"):
                    _json(self, 403, {"error": "forbidden"})
                    return
                if not self.config.memory_db:
                    _json(self, 400, {"error": "DIGITALBRAIN_MEMORY_DB not configured"})
                    return
                with SQLiteMemoryStore(self.config.memory_db) as store:
                    recs = [asdict(r) if is_dataclass(r) else r.__dict__ for r in store.list_records(limit=limit)]
                _json(self, 200, {"memory": recs, "version": "v1"})
                return
            if parsed.path in {"/audit", "/v1/audit"}:
                if not self._scope_ok("read:audit"):
                    _json(self, 403, {"error": "forbidden"})
                    return
                if not self.config.audit_db:
                    _json(self, 400, {"error": "DIGITALBRAIN_AUDIT_DB not configured"})
                    return
                with AuditLog(self.config.audit_db) as store:
                    ev = [asdict(e) if is_dataclass(e) else e.__dict__ for e in store.list_events(limit=limit)]
                _json(self, 200, {"audit": ev, "version": "v1"})
                return
            if parsed.path in {"/outcomes", "/v1/outcomes"}:
                if not self._scope_ok("read:outcomes"):
                    _json(self, 403, {"error": "forbidden"})
                    return
                if not self.config.outcomes_db:
                    _json(self, 400, {"error": "DIGITALBRAIN_OUTCOMES_DB not configured"})
                    return
                with SQLiteOutcomeStore(self.config.outcomes_db) as store:
                    rows = [asdict(r) if is_dataclass(r) else r.__dict__ for r in store.list_outcomes(limit=limit)]
                    summary = store.summary()
                    regression = store.detect_regressions()
                gate = None
                base = (qs.get("baseline_ref") or [None])[0]
                cand = (qs.get("candidate_ref") or [None])[0]
                kind = (qs.get("kind") or [None])[0]
                if base and cand and kind:
                    gate = evaluate_promotion_gate(store, kind=kind, baseline_ref=base, candidate_ref=cand)
                _json(self, 200, {"outcomes": rows, "summary": summary, "regression": regression, "evaluation_gate": gate, "version": "v1"})
                return
            if parsed.path in {"/promotions", "/v1/promotions"}:
                if not self._scope_ok("read:promotions"):
                    _json(self, 403, {"error": "forbidden"})
                    return
                if not self.config.promotion_db:
                    _json(self, 400, {"error": "DIGITALBRAIN_PROMOTION_DB not configured"})
                    return
                with SQLitePromotionStore(self.config.promotion_db) as store:
                    rows = [asdict(r) if is_dataclass(r) else r.__dict__ for r in store.list(limit=limit)]
                _json(self, 200, {"promotions": rows, "version": "v1"})
                return
            _json(self, 404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            _json(self, 500, {"error": str(exc)})


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"DigitalBrain API listening on http://{host}:{port}")
    server.serve_forever()
