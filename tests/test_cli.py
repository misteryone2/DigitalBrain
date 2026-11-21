"""CLI integration tests."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from digitalbrain.cli import main
from digitalbrain.memory import SQLiteMemoryStore


class CLITests(unittest.TestCase):
    def test_goal_with_memory_db_creates_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["Track expenses", "--memory-db", str(db_path)])

            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("Goal: Track expenses", text)
            self.assertIn("Status: accepted", text)
            self.assertIn("Memory record:", text)

            with SQLiteMemoryStore(db_path) as store:
                records = store.list_records()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].content, "Track expenses")

    def test_list_memory_reads_existing_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as store:
                store.add_record("Remember this", source="test")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--memory-db", str(db_path), "--list-memory"])

            self.assertEqual(code, 0)
            self.assertIn("Remember this", text := output.getvalue())
            self.assertIn("source: test", text)

    def test_memory_stats_and_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as store:
                record = store.add_record("A fact", source="test")

            stats_out = io.StringIO()
            with redirect_stdout(stats_out):
                code = main(["--memory-db", str(db_path), "--memory-stats"])
            self.assertEqual(code, 0)
            self.assertIn("total_records: 1", stats_out.getvalue())

            get_out = io.StringIO()
            with redirect_stdout(get_out):
                code = main(["--memory-db", str(db_path), "--get-memory", record.id])
            self.assertEqual(code, 0)
            self.assertIn("A fact", get_out.getvalue())

    def test_search_and_correct_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as store:
                record = store.add_record("Old fact", source="test")

            search_out = io.StringIO()
            with redirect_stdout(search_out):
                code = main(["--memory-db", str(db_path), "--list-memory", "--search-memory", "Old"])
            self.assertEqual(code, 0)
            self.assertIn("Old fact", search_out.getvalue())

            correct_out = io.StringIO()
            with redirect_stdout(correct_out):
                code = main([
                    "--memory-db", str(db_path),
                    "--correct-memory", record.id,
                    "--content", "New fact",
                    "--source", "cli",
                ])
            self.assertEqual(code, 0)
            self.assertIn("Corrected record:", correct_out.getvalue())

            with SQLiteMemoryStore(db_path) as store:
                active = store.list_records(search="New")
                self.assertEqual(len(active), 1)
                self.assertEqual(active[0].source, "cli")

    def test_add_and_list_knowledge_fact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "knowledge.db"
            out = io.StringIO()
            with redirect_stdout(out):
                code = main([
                    "--knowledge-db", str(db_path),
                    "--add-fact", "DigitalBrain", "uses", "SQLite",
                    "--fact-source", "docs",
                ])
            self.assertEqual(code, 0)
            self.assertIn("DigitalBrain uses SQLite", out.getvalue())

            list_out = io.StringIO()
            with redirect_stdout(list_out):
                code = main(["--knowledge-db", str(db_path), "--list-facts"])
            self.assertEqual(code, 0)
            self.assertIn("DigitalBrain uses SQLite", list_out.getvalue())

    def test_plan_and_audit_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan_db = Path(tmp) / "plans.db"
            audit_db = Path(tmp) / "audit.db"
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--plan-db", str(plan_db), "--audit-db", str(audit_db), "Track expenses"])
            self.assertEqual(code, 0)
            self.assertIn("Plan record:", out.getvalue())

            plans_out = io.StringIO()
            with redirect_stdout(plans_out):
                code = main(["--plan-db", str(plan_db), "--list-plans"])
            self.assertEqual(code, 0)
            self.assertIn("Track expenses", plans_out.getvalue())

            audit_out = io.StringIO()
            with redirect_stdout(audit_out):
                code = main(["--audit-db", str(audit_db), "--list-audit"])
            self.assertEqual(code, 0)
            self.assertIn("plan.generated", audit_out.getvalue())


if __name__ == "__main__":
    unittest.main()
