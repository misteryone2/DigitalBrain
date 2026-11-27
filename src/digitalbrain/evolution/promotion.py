"""Environment separation and promotion records (M6 baseline).

This module provides deterministic environment/promotion records and rollback
markers. It does not execute deployments or self-modify code.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PromotionRecord:
    id: str
    created_at: str
    artifact: str
    from_env: str
    to_env: str
    status: str
    reason: str
    metadata: dict[str, Any]


class SQLitePromotionStore:
    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path.parent) != ".":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SQLitePromotionStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _init(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS promotions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                artifact TEXT NOT NULL,
                from_env TEXT NOT NULL,
                to_env TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_promotions_created ON promotions(created_at DESC)")
        cur = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if cur == 0:
            self._conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        elif cur != self.SCHEMA_VERSION:
            raise RuntimeError(f"Unsupported promotion schema {cur}")
        self._conn.commit()

    def record(self, *, artifact: str, from_env: str, to_env: str, status: str, reason: str, metadata: dict[str, Any] | None = None) -> PromotionRecord:
        rec = PromotionRecord(uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(), artifact, from_env, to_env, status, reason, metadata or {})
        allowed_envs = {"lab", "validation", "production"}
        if rec.from_env not in allowed_envs or rec.to_env not in allowed_envs:
            raise ValueError("env must be lab|validation|production")
        allowed_status = {"proposed", "approved", "rejected", "promoted", "rolled_back", "failed"}
        if rec.status not in allowed_status:
            raise ValueError(f"status must be one of {sorted(allowed_status)}")

        # Deterministic workflow guardrails. No autonomous deployment.
        history = [r for r in self.list(limit=1000) if r.artifact == rec.artifact and r.from_env == rec.from_env and r.to_env == rec.to_env]
        statuses = {r.status for r in history}
        if rec.status == "approved" and "proposed" not in statuses:
            raise ValueError("Promotion must be proposed before approval.")
        if rec.status == "promoted":
            if "approved" not in statuses and not bool((rec.metadata or {}).get("human_approval", False)):
                raise ValueError("Promotion requires prior approved record or explicit human_approval metadata.")
        if rec.to_env == "production" and rec.status in {"approved", "promoted"}:
            if not bool((rec.metadata or {}).get("human_approval", False)):
                raise ValueError("Production promotion requires metadata.human_approval=true (no autonomous promotion).")

        with self._conn:
            self._conn.execute(
                "INSERT INTO promotions(id,created_at,artifact,from_env,to_env,status,reason,metadata_json) VALUES (?,?,?,?,?,?,?,?)",
                (rec.id, rec.created_at, rec.artifact, rec.from_env, rec.to_env, rec.status, rec.reason, json.dumps(rec.metadata, sort_keys=True)),
            )
        return rec

    def list(self, limit: int = 100) -> list[PromotionRecord]:
        rows = self._conn.execute("SELECT * FROM promotions ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
        return [PromotionRecord(r["id"], r["created_at"], r["artifact"], r["from_env"], r["to_env"], r["status"], r["reason"], json.loads(r["metadata_json"] or "{}")) for r in rows]
