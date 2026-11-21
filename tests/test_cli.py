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


if __name__ == "__main__":
    unittest.main()
