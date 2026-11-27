"""Outcome and performance metrics persistence (M5 baseline)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class OutcomeRecord:
    id: str
    created_at: str
    kind: str
    ref_id: str
    status: str
    metrics: dict[str, Any]
    details: dict[str, Any]


class SQLiteOutcomeStore:
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

    def __enter__(self) -> "SQLiteOutcomeStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _init(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outcomes (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                ref_id TEXT NOT NULL,
                status TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                details_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_kind_created ON outcomes(kind, created_at DESC)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_ref ON outcomes(ref_id, created_at DESC)")
        cur = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if cur == 0:
            self._conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        elif cur != self.SCHEMA_VERSION:
            raise RuntimeError(f"Unsupported outcomes schema version {cur}")
        self._conn.commit()

    def record_outcome(self, *, kind: str, ref_id: str, status: str, metrics: dict[str, Any] | None = None, details: dict[str, Any] | None = None) -> OutcomeRecord:
        rec = OutcomeRecord(
            id=uuid.uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
            kind=kind.strip(),
            ref_id=ref_id.strip(),
            status=status.strip(),
            metrics=metrics or {},
            details=details or {},
        )
        if not rec.kind or not rec.ref_id or not rec.status:
            raise ValueError("kind, ref_id, status required")
        with self._conn:
            self._conn.execute(
                "INSERT INTO outcomes(id,created_at,kind,ref_id,status,metrics_json,details_json) VALUES (?,?,?,?,?,?,?)",
                (rec.id, rec.created_at, rec.kind, rec.ref_id, rec.status, json.dumps(rec.metrics, sort_keys=True), json.dumps(rec.details, sort_keys=True)),
            )
        return rec

    def list_outcomes(self, *, kind: str | None = None, ref_id: str | None = None, limit: int = 100) -> list[OutcomeRecord]:
        q = "SELECT * FROM outcomes WHERE 1=1"
        params: list[Any] = []
        if kind:
            q += " AND kind=?"
            params.append(kind)
        if ref_id:
            q += " AND ref_id=?"
            params.append(ref_id)
        q += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        return [self._row(r) for r in rows]

    def summary(self, *, kind: str | None = None) -> dict[str, Any]:
        rows = self.list_outcomes(kind=kind, limit=1000)
        total = len(rows)
        by_status: dict[str, int] = {}
        for r in rows:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        success = by_status.get("passed", 0) + by_status.get("ok", 0) + by_status.get("executed", 0)
        failure = by_status.get("failed", 0) + by_status.get("error", 0)
        rate = (success / total) if total else None
        return {"total": total, "by_status": by_status, "success_rate": rate, "failures": failure}

    @staticmethod
    def _success_rate(items: list[OutcomeRecord]) -> float | None:
        if not items:
            return None
        success = sum(1 for r in items if r.status in {"passed", "ok", "executed"})
        return success / len(items)

    def detect_regressions(self, *, kind: str | None = None, window: int = 20, min_samples: int = 5, drop_threshold: float = 0.2) -> dict[str, Any]:
        """Deterministic regression signal: compare recent window vs previous window.

        No autonomous action is taken; this returns observable evidence for review.
        """
        if window < 1 or min_samples < 1:
            raise ValueError("window and min_samples must be >= 1")
        rows = self.list_outcomes(kind=kind, limit=window * 2)
        recent = rows[:window]
        previous = rows[window : window * 2]

        recent_rate = self._success_rate(recent)
        prev_rate = self._success_rate(previous)
        enough = len(recent) >= min_samples and len(previous) >= min_samples
        drop = (prev_rate - recent_rate) if (recent_rate is not None and prev_rate is not None) else None
        regressed = bool(enough and drop is not None and drop >= drop_threshold)
        return {
            "kind": kind,
            "window": window,
            "min_samples": min_samples,
            "drop_threshold": drop_threshold,
            "recent_count": len(recent),
            "previous_count": len(previous),
            "recent_success_rate": recent_rate,
            "previous_success_rate": prev_rate,
            "drop": drop,
            "enough_samples": enough,
            "regressed": regressed,
        }

    def compare_baseline_candidate(
        self,
        *,
        kind: str,
        baseline_ref: str,
        candidate_ref: str,
        min_samples: int = 1,
    ) -> dict[str, Any]:
        """Deterministic baseline vs candidate comparison. No automatic action."""
        if min_samples < 1:
            raise ValueError("min_samples must be >= 1")
        base = self.list_outcomes(kind=kind, ref_id=baseline_ref, limit=1000)
        cand = self.list_outcomes(kind=kind, ref_id=candidate_ref, limit=1000)
        base_rate = self._success_rate(base)
        cand_rate = self._success_rate(cand)
        enough = len(base) >= min_samples and len(cand) >= min_samples
        delta = (cand_rate - base_rate) if (base_rate is not None and cand_rate is not None) else None
        if not enough or delta is None:
            recommendation = "insufficient_data"
        elif delta > 0:
            recommendation = "candidate_better"
        elif delta < 0:
            recommendation = "baseline_better"
        else:
            recommendation = "equal"
        return {
            "kind": kind,
            "baseline_ref": baseline_ref,
            "candidate_ref": candidate_ref,
            "baseline_count": len(base),
            "candidate_count": len(cand),
            "baseline_success_rate": base_rate,
            "candidate_success_rate": cand_rate,
            "delta": delta,
            "enough_samples": enough,
            "recommendation": recommendation,
        }

    @staticmethod
    def _row(r: sqlite3.Row) -> OutcomeRecord:
        return OutcomeRecord(
            id=r["id"], created_at=r["created_at"], kind=r["kind"], ref_id=r["ref_id"], status=r["status"],
            metrics=json.loads(r["metrics_json"] or "{}"), details=json.loads(r["details_json"] or "{}"),
        )
