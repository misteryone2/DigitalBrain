"""SQLite-backed knowledge store for DigitalBrain.

Knowledge records are structured facts with provenance and confidence. They are
separate from episodic memory: memory captures experiences/events; knowledge
captures asserted facts that can be queried, corrected, and superseded.
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
class KnowledgeRecord:
    """A persisted knowledge fact."""

    id: str
    created_at: str
    subject: str
    predicate: str
    object: str
    source: str
    confidence: float
    metadata: dict[str, Any]
    supersedes: str | None
    superseded_by: str | None

    @property
    def is_active(self) -> bool:
        return self.superseded_by is None

    @property
    def fact(self) -> str:
        return f"{self.subject} {self.predicate} {self.object}"


class SQLiteKnowledgeStore:
    """Persist and retrieve structured knowledge facts in SQLite."""

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

    def __enter__(self) -> "SQLiteKnowledgeStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _initialize(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_records (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                metadata_json TEXT NOT NULL,
                supersedes TEXT,
                superseded_by TEXT,
                FOREIGN KEY (supersedes) REFERENCES knowledge_records(id),
                FOREIGN KEY (superseded_by) REFERENCES knowledge_records(id)
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_subject_predicate
            ON knowledge_records(subject, predicate, created_at DESC)
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_active
            ON knowledge_records(superseded_by)
            """
        )
        current_version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if current_version == 0:
            self._connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        elif current_version != self.SCHEMA_VERSION:
            raise RuntimeError(
                f"Unsupported knowledge schema version {current_version}; "
                f"expected {self.SCHEMA_VERSION}"
            )
        self._connection.commit()

    def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        *,
        source: str,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
        supersedes: str | None = None,
        created_at: datetime | None = None,
    ) -> KnowledgeRecord:
        subject_n = self._normalize_field(subject, "Subject")
        predicate_n = self._normalize_field(predicate, "Predicate")
        object_n = self._normalize_field(obj, "Object")
        source_n = self._normalize_field(source, "Source")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0.")

        record_id = uuid.uuid4().hex
        timestamp = (created_at or datetime.now(timezone.utc)).isoformat()
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
                INSERT INTO knowledge_records (
                    id, created_at, subject, predicate, object, source, confidence,
                    metadata_json, supersedes, superseded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    record_id, timestamp, subject_n, predicate_n, object_n,
                    source_n, float(confidence), metadata_json, supersedes,
                ),
            )
            if supersedes is not None:
                self._connection.execute(
                    "UPDATE knowledge_records SET superseded_by = ? WHERE id = ? AND superseded_by IS NULL",
                    (record_id, supersedes),
                )

        record = self.get(record_id)
        if record is None:  # pragma: no cover
            raise RuntimeError("Knowledge record was not persisted.")
        return record

    def get(self, record_id: str) -> KnowledgeRecord | None:
        row = self._get_row(record_id)
        return self._row_to_record(row) if row is not None else None

    def list_facts(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        subject: str | None = None,
        predicate: str | None = None,
        source: str | None = None,
        include_superseded: bool = False,
        search: str | None = None,
    ) -> list[KnowledgeRecord]:
        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")
        if offset < 0:
            raise ValueError("Offset must be zero or greater.")
        query = ["SELECT * FROM knowledge_records WHERE 1=1"]
        params: list[Any] = []
        for field, value in (("subject", subject), ("predicate", predicate), ("source", source)):
            if value is not None:
                normalized = self._normalize_field(value, field.capitalize())
                query.append(f"AND {field} = ?")
                params.append(normalized)
        if search is not None:
            normalized_search = self._normalize_field(search, "Search")
            query.append("AND (subject LIKE ? OR predicate LIKE ? OR object LIKE ?)")
            like = f"%{normalized_search}%"
            params.extend([like, like, like])
        if not include_superseded:
            query.append("AND superseded_by IS NULL")
        query.append("ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?")
        params.extend([limit, offset])
        rows = self._connection.execute("\n".join(query), params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def find_conflicts(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Find active facts with same subject+predicate but different object."""
        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")
        rows = self._connection.execute(
            """
            SELECT subject, predicate
            FROM knowledge_records
            WHERE superseded_by IS NULL
            GROUP BY subject, predicate
            HAVING COUNT(DISTINCT object) > 1
            ORDER BY subject, predicate
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        conflicts: list[dict[str, Any]] = []
        for row in rows:
            facts = self.list_facts(
                subject=row["subject"],
                predicate=row["predicate"],
                include_superseded=False,
                limit=100,
            )
            conflicts.append(
                {
                    "subject": row["subject"],
                    "predicate": row["predicate"],
                    "facts": [
                        {
                            "id": f.id,
                            "object": f.object,
                            "source": f.source,
                            "confidence": f.confidence,
                        }
                        for f in facts
                    ],
                }
            )
        return conflicts

    def correct(
        self,
        record_id: str,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        obj: str | None = None,
        source: str | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> KnowledgeRecord:
        existing = self.get(record_id)
        if existing is None:
            raise ValueError(f"Cannot correct unknown record: {record_id}")
        if existing.superseded_by is not None:
            raise ValueError(f"Cannot correct superseded record: {record_id}")
        merged_metadata = dict(existing.metadata)
        if metadata:
            merged_metadata.update(metadata)
        merged_metadata["correction_of"] = record_id
        return self.add_fact(
            subject if subject is not None else existing.subject,
            predicate if predicate is not None else existing.predicate,
            obj if obj is not None else existing.object,
            source=source or existing.source,
            confidence=existing.confidence if confidence is None else confidence,
            metadata=merged_metadata,
            supersedes=record_id,
            created_at=created_at,
        )

    def stats(self) -> dict[str, Any]:
        total = self._connection.execute("SELECT COUNT(*) AS c FROM knowledge_records").fetchone()["c"]
        active = self._connection.execute(
            "SELECT COUNT(*) AS c FROM knowledge_records WHERE superseded_by IS NULL"
        ).fetchone()["c"]
        return {
            "schema_version": self.SCHEMA_VERSION,
            "total_facts": int(total),
            "active_facts": int(active),
            "superseded_facts": int(total) - int(active),
        }

    def _get_row(self, record_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM knowledge_records WHERE id = ?", (record_id,)
        ).fetchone()

    @staticmethod
    def _normalize_field(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{name} must not be empty.")
        return normalized

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> KnowledgeRecord:
        metadata_raw = row["metadata_json"]
        metadata = json.loads(metadata_raw) if metadata_raw else {}
        if not isinstance(metadata, dict):
            metadata = {"value": metadata}
        return KnowledgeRecord(
            id=row["id"],
            created_at=row["created_at"],
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            source=row["source"],
            confidence=float(row["confidence"]),
            metadata=metadata,
            supersedes=row["supersedes"],
            superseded_by=row["superseded_by"],
        )
