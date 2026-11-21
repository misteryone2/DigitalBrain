"""SQLite-backed plan storage for DigitalBrain.

Plans are stored as append-only versioned records. Replanning creates a new
record linked to the previous version; history is preserved for audit/review.
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
class PlanRecord:
    id: str
    created_at: str
    goal: str
    status: str
    version: int
    parent_plan_id: str | None
    source: str
    warnings: tuple[str, ...]
    context_summary: dict[str, Any]
    steps: tuple[dict[str, Any], ...]

    @property
    def is_latest(self) -> bool:
        # caller can determine via query; kept for convenience when set externally
        return True


class SQLitePlanStore:
    """Persist and retrieve plan versions in SQLite."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path.parent) != ".":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLitePlanStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _initialize(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_records (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER NOT NULL,
                parent_plan_id TEXT,
                source TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                context_summary_json TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                FOREIGN KEY (parent_plan_id) REFERENCES plan_records(id)
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_records_goal_created ON plan_records(goal, created_at DESC)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_records_parent ON plan_records(parent_plan_id)"
        )
        current = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if current == 0:
            self._connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        elif current != self.SCHEMA_VERSION:
            raise RuntimeError(f"Unsupported plan schema version {current}")
        self._connection.commit()

    def save_plan(
        self,
        *,
        goal: str,
        status: str,
        steps: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        source: str,
        warnings: list[str] | tuple[str, ...] = (),
        context_summary: dict[str, Any] | None = None,
        parent_plan_id: str | None = None,
        created_at: datetime | None = None,
    ) -> PlanRecord:
        goal_n = goal.strip()
        status_n = status.strip()
        source_n = source.strip()
        if not goal_n:
            raise ValueError("Goal must not be empty.")
        if not status_n:
            raise ValueError("Status must not be empty.")
        if not source_n:
            raise ValueError("Source must not be empty.")
        if not steps:
            raise ValueError("Steps must not be empty.")

        with self._connection:
            version = 1
            if parent_plan_id is not None:
                parent = self._get_row(parent_plan_id)
                if parent is None:
                    raise ValueError(f"Unknown parent plan: {parent_plan_id}")
                version = int(parent["version"]) + 1
            record = PlanRecord(
                id=uuid.uuid4().hex,
                created_at=(created_at or datetime.now(timezone.utc)).isoformat(),
                goal=goal_n,
                status=status_n,
                version=version,
                parent_plan_id=parent_plan_id,
                source=source_n,
                warnings=tuple(str(w) for w in warnings),
                context_summary=dict(context_summary or {}),
                steps=tuple(dict(s) for s in steps),
            )
            self._connection.execute(
                """
                INSERT INTO plan_records (
                    id, created_at, goal, status, version, parent_plan_id, source,
                    warnings_json, context_summary_json, steps_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.created_at,
                    record.goal,
                    record.status,
                    record.version,
                    record.parent_plan_id,
                    record.source,
                    json.dumps(list(record.warnings), ensure_ascii=False),
                    json.dumps(record.context_summary, sort_keys=True, ensure_ascii=False),
                    json.dumps(list(record.steps), ensure_ascii=False),
                ),
            )
        return record

    def get(self, plan_id: str) -> PlanRecord | None:
        row = self._get_row(plan_id)
        return self._row_to_record(row) if row else None

    def list_plans(self, *, limit: int = 100, goal: str | None = None) -> list[PlanRecord]:
        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")
        query = ["SELECT * FROM plan_records WHERE 1=1"]
        params: list[Any] = []
        if goal is not None:
            goal_n = goal.strip()
            if not goal_n:
                raise ValueError("Goal filter must not be empty.")
            query.append("AND goal = ?")
            params.append(goal_n)
        query.append("ORDER BY created_at DESC, rowid DESC LIMIT ?")
        params.append(limit)
        rows = self._connection.execute("\n".join(query), params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def latest_for_goal(self, goal: str) -> PlanRecord | None:
        plans = self.list_plans(limit=1, goal=goal)
        return plans[0] if plans else None

    def _get_row(self, plan_id: str) -> sqlite3.Row | None:
        return self._connection.execute("SELECT * FROM plan_records WHERE id = ?", (plan_id,)).fetchone()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> PlanRecord:
        warnings = json.loads(row["warnings_json"]) if row["warnings_json"] else []
        context_summary = json.loads(row["context_summary_json"]) if row["context_summary_json"] else {}
        steps = json.loads(row["steps_json"]) if row["steps_json"] else []
        if not isinstance(warnings, list):
            warnings = [warnings]
        if not isinstance(context_summary, dict):
            context_summary = {"value": context_summary}
        if not isinstance(steps, list):
            steps = [steps]
        return PlanRecord(
            id=row["id"],
            created_at=row["created_at"],
            goal=row["goal"],
            status=row["status"],
            version=int(row["version"]),
            parent_plan_id=row["parent_plan_id"],
            source=row["source"],
            warnings=tuple(str(w) for w in warnings),
            context_summary=context_summary,
            steps=tuple(dict(s) if isinstance(s, dict) else {"value": s} for s in steps),
        )
