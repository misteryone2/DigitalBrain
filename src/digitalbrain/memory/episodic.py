
"""Legacy episodic memory store.

DEPRECATED: kept for backward compatibility with early tests/experiments.
New code should use `digitalbrain.memory.store.SQLiteMemoryStore`, which
supports typed records, metadata, confidence, and correction/supersession.
"""

from __future__ import annotations

import sqlite3

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Episode:
    id: int
    message: str
    intent: str
    response: str
    created_at: str


class MemoryStore:
    """Stores and retrieves DigitalBrain interactions."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize_database()

    def _initialize_database(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def remember_interaction(
        self,
        message: str,
        intent: str,
        response: str,
    ) -> None:
        created_at = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO episodes (
                    message,
                    intent,
                    response,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (message, intent, response, created_at),
            )

    def get_recent_interactions(self) -> list[Episode]:
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                """
                SELECT id, message, intent, response, created_at
                FROM episodes
                ORDER BY id DESC
                """
            ).fetchall()

        return [
            Episode(
                id=row["id"],
                message=row["message"],
                intent=row["intent"],
                response=row["response"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
