"""Tests for the SQLite knowledge store."""

import tempfile
import unittest
from pathlib import Path

from digitalbrain.knowledge.store import SQLiteKnowledgeStore


class SQLiteKnowledgeStoreTests(unittest.TestCase):
    def test_add_get_and_list_fact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "knowledge.db"
            with SQLiteKnowledgeStore(db) as store:
                record = store.add_fact(
                    "DigitalBrain",
                    "uses",
                    "SQLite",
                    source="docs",
                    confidence=0.9,
                    metadata={"kind": "architecture"},
                )
                loaded = store.get(record.id)
                facts = store.list_facts(subject="DigitalBrain")

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.fact, "DigitalBrain uses SQLite")
            self.assertEqual(loaded.metadata["kind"], "architecture")
            self.assertEqual(len(facts), 1)
            self.assertTrue(facts[0].is_active)

    def test_correction_supersedes_fact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "knowledge.db"
            with SQLiteKnowledgeStore(db) as store:
                old = store.add_fact("Project", "uses", "MySQL", source="user")
                new = store.correct(old.id, obj="SQLite", source="docs", confidence=0.95)
                active = store.list_facts(subject="Project")
                all_facts = store.list_facts(subject="Project", include_superseded=True)

            self.assertEqual(new.object, "SQLite")
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0].id, new.id)
            self.assertEqual(len(all_facts), 2)

    def test_search_and_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "knowledge.db"
            with SQLiteKnowledgeStore(db) as store:
                store.add_fact("Memory", "stores", "episodes", source="test")
                store.add_fact("Knowledge", "stores", "facts", source="test")
                found = store.list_facts(search="facts")
                stats = store.stats()

            self.assertEqual(len(found), 1)
            self.assertEqual(stats["active_facts"], 2)
            self.assertEqual(stats["schema_version"], 1)

    def test_rejects_invalid_fact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "knowledge.db"
            with SQLiteKnowledgeStore(db) as store:
                with self.assertRaises(ValueError):
                    store.add_fact(" ", "uses", "x", source="test")
                with self.assertRaises(ValueError):
                    store.add_fact("s", "p", "o", source=" ", confidence=1.0)
                with self.assertRaises(ValueError):
                    store.add_fact("s", "p", "o", source="test", confidence=2.0)


if __name__ == "__main__":
    unittest.main()
