"""SQLite-backed memory for DigitalBrain.

This module provides a small, inspectable persistence layer for milestone M1.
Records are append-oriented where possible: corrections create a new record and
mark the previous record as superseded for traceability.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


class MemoryType(StrEnum):
    """Supported memory record categories."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    GOAL = "goal"
    OUTCOME = "outcome"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """A persisted memory record."""

    id: str
    created_at: str
    memory_type: str
    source: str
    content: str
    confidence: float
    metadata: dict[str, Any]
    supersedes: str | None
    superseded_by: str | None

    @property
    def is_active(self) -> bool:
        return self.superseded_by is None


class SQLiteMemoryStore:
    """Persist and retrieve memory records in SQLite."""

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

    def __enter__(self) -> "SQLiteMemoryStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    SCHEMA_VERSION = 1

    def _initialize(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                source TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL NOT NULL,
                metadata_json TEXT NOT NULL,
                supersedes TEXT,
                superseded_by TEXT,
                FOREIGN KEY (supersedes) REFERENCES memory_records(id),
                FOREIGN KEY (superseded_by) REFERENCES memory_records(id)
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_records_type_created
            ON memory_records(memory_type, created_at DESC)
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_records_superseded_by
            ON memory_records(superseded_by)
            """
        )
        current_version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if current_version == 0:
            self._connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        elif current_version != self.SCHEMA_VERSION:
            raise RuntimeError(
                f"Unsupported memory schema version {current_version}; "
                f"expected {self.SCHEMA_VERSION}"
            )
        self._connection.commit()

    def add_record(
        self,
        content: str,
        *,
        memory_type: MemoryType | str = MemoryType.EPISODIC,
        source: str,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
        supersedes: str | None = None,
        created_at: datetime | None = None,
    ) -> MemoryRecord:
        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("Memory content must not be empty.")
        normalized_source = source.strip()
        if not normalized_source:
            raise ValueError("Memory source must not be empty.")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0.")

        record_id = uuid.uuid4().hex
        timestamp = (created_at or datetime.now(timezone.utc)).isoformat()
        record_type = (
            memory_type.value if isinstance(memory_type, MemoryType) else str(memory_type)
        ).strip()
        if not record_type:
            raise ValueError("Memory type must not be empty.")
        metadata_json = json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False)

        with self._connection:
            if supersedes is not None:
                existing = self._get_row(supersedes)
                if existing is None:
                    raise ValueError(f"Cannot supersede unknown record: {supersedes}")
                if existing["superseded_by"] is not None:
                    raise ValueError(f"Record is already superseded: {supersedes}")
            self._connection.execute(
                """
                INSERT INTO memory_records (
                    id, created_at, memory_type, source, content, confidence,
                    metadata_json, supersedes, superseded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    record_id,
                    timestamp,
                    record_type,
                    normalized_source,
                    normalized_content,
                    float(confidence),
                    metadata_json,
                    supersedes,
                ),
            )
            if supersedes is not None:
                self._connection.execute(
                    "UPDATE memory_records SET superseded_by = ? WHERE id = ? AND superseded_by IS NULL",
                    (record_id, supersedes),
                )

        record = self.get(record_id)
        if record is None:  # pragma: no cover - defensive
            raise RuntimeError("Memory record was not persisted.")
        return record

    def get(self, record_id: str) -> MemoryRecord | None:
        row = self._get_row(record_id)
        return self._row_to_record(row) if row is not None else None

    def list_records(
        self,
        *,
        limit: int = 100,
        memory_type: MemoryType | str | None = None,
        source: str | None = None,
        include_superseded: bool = False,
        search: str | None = None,
    ) -> list[MemoryRecord]:
        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")

        query = ["SELECT * FROM memory_records WHERE 1=1"]
        params: list[Any] = []
        if memory_type is not None:
            record_type = (
                memory_type.value if isinstance(memory_type, MemoryType) else str(memory_type)
            )
            query.append("AND memory_type = ?")
            params.append(record_type)
        if source is not None:
            normalized_source = source.strip()
            if not normalized_source:
                raise ValueError("Source filter must not be empty.")
            query.append("AND source = ?")
            params.append(normalized_source)
        if search is not None:
            normalized_search = search.strip()
            if not normalized_search:
                raise ValueError("Search must not be empty.")
            query.append("AND content LIKE ?")
            params.append(f"%{normalized_search}%")
        if not include_superseded:
            query.append("AND superseded_by IS NULL")
        query.append("ORDER BY created_at DESC, rowid DESC LIMIT ?")
        params.append(limit)

        rows = self._connection.execute("\n".join(query), params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def count_records(
        self,
        *,
        memory_type: MemoryType | str | None = None,
        source: str | None = None,
        include_superseded: bool = False,
        search: str | None = None,
    ) -> int:
        query = ["SELECT COUNT(*) AS c FROM memory_records WHERE 1=1"]
        params: list[Any] = []
        if memory_type is not None:
            record_type = (
                memory_type.value if isinstance(memory_type, MemoryType) else str(memory_type)
            )
            query.append("AND memory_type = ?")
            params.append(record_type)
        if source is not None:
            normalized_source = source.strip()
            if not normalized_source:
                raise ValueError("Source filter must not be empty.")
            query.append("AND source = ?")
            params.append(normalized_source)
        if search is not None:
            normalized_search = search.strip()
            if not normalized_search:
                raise ValueError("Search must not be empty.")
            query.append("AND content LIKE ?")
            params.append(f"%{normalized_search}%")
        if not include_superseded:
            query.append("AND superseded_by IS NULL")
        row = self._connection.execute("\n".join(query), params).fetchone()
        return int(row["c"]) if row else 0

    def stats(self) -> dict[str, Any]:
        total = self.count_records(include_superseded=True)
        active = self.count_records(include_superseded=False)
        by_type_rows = self._connection.execute(
            """
            SELECT memory_type, COUNT(*) AS c
            FROM memory_records
            WHERE superseded_by IS NULL
            GROUP BY memory_type
            ORDER BY memory_type
            """
        ).fetchall()
        by_type = {row["memory_type"]: int(row["c"]) for row in by_type_rows}
        return {
            "schema_version": self.SCHEMA_VERSION,
            "total_records": total,
            "active_records": active,
            "superseded_records": total - active,
            "active_by_type": by_type,
        }

    def correct(
        self,
        record_id: str,
        content: str,
        *,
        source: str | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MemoryRecord:
        existing = self.get(record_id)
        if existing is None:
            raise ValueError(f"Cannot correct unknown record: {record_id}")
        if existing.superseded_by is not None:
            raise ValueError(f"Cannot correct superseded record: {record_id}")

        merged_metadata = dict(existing.metadata)
        if metadata:
            merged_metadata.update(metadata)
        merged_metadata["correction_of"] = record_id

        return self.add_record(
            content,
            memory_type=existing.memory_type,
            source=source or existing.source,
            confidence=existing.confidence if confidence is None else confidence,
            metadata=merged_metadata,
            supersedes=record_id,
            created_at=created_at,
        )

    def _get_row(self, record_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM memory_records WHERE id = ?",
            (record_id,),
        ).fetchone()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        metadata_raw = row["metadata_json"]
        metadata = json.loads(metadata_raw) if metadata_raw else {}
        if not isinstance(metadata, dict):
            metadata = {"value": metadata}
        return MemoryRecord(
            id=row["id"],
            created_at=row["created_at"],
            memory_type=row["memory_type"],
            source=row["source"],
            content=row["content"],
            confidence=float(row["confidence"]),
            metadata=metadata,
            supersedes=row["supersedes"],
            superseded_by=row["superseded_by"],
        )
