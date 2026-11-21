"""Append-only audit log for core actions.

This is a minimal, inspectable baseline for traceability. It is not a security
boundary by itself; security controls must be enforced by Core/Execution layers.
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
class AuditEvent:
    id: str
    created_at: str
    event_type: str
    actor: str
    outcome: str
    details: dict[str, Any]


class AuditLog:
    """Append-only SQLite audit log."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path.parent) != ".":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "AuditLog":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _initialize(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                outcome TEXT NOT NULL,
                details_json TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at DESC)"
        )
        current = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if current == 0:
            self._connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        elif current != self.SCHEMA_VERSION:
            raise RuntimeError(f"Unsupported audit schema version {current}")
        self._connection.commit()

    def record(
        self,
        event_type: str,
        *,
        actor: str,
        outcome: str,
        details: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid.uuid4().hex,
            created_at=(created_at or datetime.now(timezone.utc)).isoformat(),
            event_type=event_type.strip(),
            actor=actor.strip(),
            outcome=outcome.strip(),
            details=details or {},
        )
        if not event.event_type or not event.actor or not event.outcome:
            raise ValueError("event_type, actor, and outcome must not be empty.")
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO audit_events (id, created_at, event_type, actor, outcome, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.created_at,
                    event.event_type,
                    event.actor,
                    event.outcome,
                    json.dumps(event.details, sort_keys=True, ensure_ascii=False),
                ),
            )
        return event

    def list_events(self, *, limit: int = 100) -> list[AuditEvent]:
        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")
        rows = self._connection.execute(
            "SELECT * FROM audit_events ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            AuditEvent(
                id=r["id"],
                created_at=r["created_at"],
                event_type=r["event_type"],
                actor=r["actor"],
                outcome=r["outcome"],
                details=json.loads(r["details_json"]) if r["details_json"] else {},
            )
            for r in rows
        ]
