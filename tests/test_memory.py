"""Tests for the SQLite memory store."""

import tempfile
import unittest
from pathlib import Path

from digitalbrain.memory.store import MemoryType, SQLiteMemoryStore


class SQLiteMemoryStoreTests(unittest.TestCase):
    def test_add_and_get_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as store:
                record = store.add_record(
                    "User asked to build a finance app",
                    memory_type=MemoryType.GOAL,
                    source="cli",
                    confidence=0.9,
                    metadata={"channel": "test"},
                )
                loaded = store.get(record.id)

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.content, "User asked to build a finance app")
            self.assertEqual(loaded.memory_type, "goal")
            self.assertEqual(loaded.source, "cli")
            self.assertEqual(loaded.confidence, 0.9)
            self.assertEqual(loaded.metadata["channel"], "test")
            self.assertTrue(loaded.is_active)

    def test_persists_across_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as store:
                record = store.add_record(
                    "Persisted fact",
                    memory_type=MemoryType.SEMANTIC,
                    source="test",
                )
                record_id = record.id

            with SQLiteMemoryStore(db_path) as store:
                loaded = store.get(record_id)
                records = store.list_records()

            self.assertIsNotNone(loaded)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].id, record_id)

    def test_correction_supersedes_old_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as store:
                original = store.add_record(
                    "The project uses MySQL",
                    memory_type=MemoryType.SEMANTIC,
                    source="user",
                )
                corrected = store.correct(
                    original.id,
                    "The project uses SQLite for initial persistence",
                    source="docs",
                    confidence=0.95,
                )

                old = store.get(original.id)
                new = store.get(corrected.id)
                active = store.list_records(memory_type=MemoryType.SEMANTIC)
                all_records = store.list_records(
                    memory_type=MemoryType.SEMANTIC, include_superseded=True
                )

            self.assertIsNotNone(old)
            self.assertIsNotNone(new)
            assert old is not None and new is not None
            self.assertEqual(old.superseded_by, new.id)
            self.assertEqual(new.supersedes, old.id)
            self.assertFalse(old.is_active)
            self.assertTrue(new.is_active)
            self.assertEqual([r.id for r in active], [new.id])
            self.assertEqual(len(all_records), 2)

    def test_filters_by_type_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as store:
                store.add_record("goal", memory_type=MemoryType.GOAL, source="cli")
                store.add_record("fact", memory_type=MemoryType.SEMANTIC, source="test")
                store.add_record("goal2", memory_type=MemoryType.GOAL, source="core")

                goals = store.list_records(memory_type=MemoryType.GOAL)
                cli_goals = store.list_records(memory_type=MemoryType.GOAL, source="cli")

            self.assertEqual(len(goals), 2)
            self.assertEqual(len(cli_goals), 1)
            self.assertEqual(cli_goals[0].content, "goal")

    def test_search_count_and_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as store:
                first = store.add_record("build sqlite memory", memory_type=MemoryType.GOAL, source="cli")
                store.add_record("write tests", memory_type=MemoryType.OUTCOME, source="test")
                store.correct(first.id, "build sqlite memory store", source="cli")

                found = store.list_records(search="sqlite")
                self.assertEqual(len(found), 1)
                self.assertIn("store", found[0].content)
                self.assertEqual(store.count_records(search="sqlite", include_superseded=True), 2)

                stats = store.stats()
                self.assertEqual(stats["schema_version"], 1)
                self.assertEqual(stats["total_records"], 3)
                self.assertEqual(stats["active_records"], 2)
                self.assertEqual(stats["superseded_records"], 1)

    def test_rejects_invalid_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as store:
                with self.assertRaises(ValueError):
                    store.add_record("   ", source="test")
                with self.assertRaises(ValueError):
                    store.add_record("ok", source=" ")
                with self.assertRaises(ValueError):
                    store.add_record("ok", source="test", confidence=1.5)
                with self.assertRaises(ValueError):
                    store.list_records(limit=0)
                with self.assertRaises(ValueError):
                    store.list_records(source=" ")
                with self.assertRaises(ValueError):
                    store.list_records(search=" ")
                with self.assertRaises(ValueError):
                    store.count_records(search="   ")


if __name__ == "__main__":
    unittest.main()
