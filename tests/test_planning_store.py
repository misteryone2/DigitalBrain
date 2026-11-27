"""Tests for SQLite plan store."""

import tempfile
import unittest
from pathlib import Path

from digitalbrain.planning.store import SQLitePlanStore


class SQLitePlanStoreTests(unittest.TestCase):
    def test_save_and_list_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "plans.db"
            with SQLitePlanStore(db) as store:
                p1 = store.save_plan(
                    goal="Build app",
                    status="accepted",
                    steps=[{"id": "step-1", "title": "Clarify"}],
                    source="test",
                )
                p2 = store.save_plan(
                    goal="Build app",
                    status="accepted_with_warnings",
                    steps=[{"id": "step-1", "title": "Clarify"}],
                    source="test",
                    parent_plan_id=p1.id,
                    warnings=["conflict"],
                )
                plans = store.list_plans(goal="Build app")
                latest = store.latest_for_goal("Build app")
                p1_after = store.get(p1.id)

            self.assertEqual(p2.version, 2)
            self.assertEqual(p2.parent_plan_id, p1.id)
            self.assertEqual(p2.lifecycle_status, "active")
            self.assertIsNotNone(p1_after)
            assert p1_after is not None
            self.assertEqual(p1_after.lifecycle_status, "superseded")
            self.assertEqual(len(plans), 2)
            self.assertIsNotNone(latest)
            assert latest is not None
            self.assertEqual(latest.id, p2.id)

    def test_record_step_outcome_updates_gate_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "plans.db"
            with SQLitePlanStore(db) as store:
                plan = store.save_plan(
                    goal="Build app",
                    status="accepted",
                    steps=[{"id": "step-1", "title": "Do", "status": "pending", "critical": True}],
                    source="test",
                )
                updated, event = store.record_step_outcome(plan.id, "step-1", "failed", reason="test failed")
                self.assertEqual(event["outcome"], "failed")
                self.assertEqual(updated.metadata["last_step_outcome"]["step_id"], "step-1")
                self.assertIn("execution_gate", updated.metadata)
                self.assertEqual(updated.metadata["execution_gate"]["status"], "needs_review")
                self.assertIn("replan_proposal", event)
                self.assertIsNotNone(event["replan_proposal"])

    def test_rejects_invalid_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "plans.db"
            with SQLitePlanStore(db) as store:
                with self.assertRaises(ValueError):
                    store.save_plan(goal=" ", status="accepted", steps=[{"id": "s1"}], source="test")
                with self.assertRaises(ValueError):
                    store.save_plan(goal="g", status="accepted", steps=[], source="test")


if __name__ == "__main__":
    unittest.main()
