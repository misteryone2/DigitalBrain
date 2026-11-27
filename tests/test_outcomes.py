"""Tests for M5 outcomes/metacognition baseline."""

import tempfile
import unittest
from pathlib import Path

from digitalbrain.learning import SQLiteOutcomeStore, capability_report


class OutcomeTests(unittest.TestCase):
    def test_outcome_summary_and_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "o.db"
            with SQLiteOutcomeStore(db) as store:
                store.record_outcome(kind="tool", ref_id="1", status="executed", details={"capability": "tool.write_file"})
                store.record_outcome(kind="tool", ref_id="2", status="failed", details={"capability": "tool.write_file"})
                summary = store.summary(kind="tool")
                self.assertEqual(summary["total"], 2)
                self.assertEqual(summary["failures"], 1)
                rep = capability_report(store, capability="tool.write_file", kind="tool")
                self.assertEqual(rep.total, 2)
                self.assertEqual(rep.failures, 1)


if __name__ == "__main__":
    unittest.main()
