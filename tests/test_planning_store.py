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

    def test_approve_execution_requires_ready_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "plans.db"
            with SQLitePlanStore(db) as store:
                blocked = store.save_plan(
                    goal="Blocked",
                    status="accepted_with_warnings",
                    steps=[{"id": "step-1", "title": "Resolve", "status": "blocked"}],
                    warnings=["conflict"],
                    source="test",
                )
                with self.assertRaises(ValueError):
                    store.approve_execution(blocked.id, reason="nope")

                ready = store.save_plan(
                    goal="Ready",
                    status="accepted",
                    steps=[{"id": "step-1", "title": "Do", "status": "pending"}],
                    source="test",
                )
                approved = store.approve_execution(ready.id, reason="ok", actor="test", tool_name="write_file", risk_class="low")
                self.assertEqual(approved.lifecycle_status, "approved_for_execution")
                self.assertTrue(approved.metadata["execution_approval"]["approved"])
                self.assertEqual(approved.metadata["execution_approval"]["tool_name"], "write_file")

    def test_consume_execution_approval_single_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "plans.db"
            with SQLitePlanStore(db) as store:
                plan = store.save_plan(
                    goal="Ready",
                    status="accepted",
                    steps=[{"id": "step-1", "title": "Do", "status": "pending"}],
                    source="test",
                )
                approved = store.approve_execution(plan.id, reason="ok", tool_name="write_file", risk_class="low")
                approval = approved.metadata["execution_approval"]
                consumed = store.consume_execution_approval(plan.id, approved_at=approval["approved_at"], tool_name="write_file", risk_class="low")
                self.assertIsNotNone(consumed.metadata["execution_approval"]["consumed_at"])
                self.assertEqual(consumed.metadata["execution_approval"]["execution_state"], "executed")
                with self.assertRaises(ValueError):
                    store.consume_execution_approval(plan.id, approved_at=approval["approved_at"], tool_name="write_file", risk_class="low")

    def test_reserve_and_finalize_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "plans.db"
            with SQLitePlanStore(db) as store:
                plan = store.save_plan(
                    goal="Ready",
                    status="accepted",
                    steps=[{"id": "step-1", "title": "Do", "status": "pending"}],
                    source="test",
                )
                approved = store.approve_execution(plan.id, reason="ok", tool_name="write_file", risk_class="low")
                at = approved.metadata["execution_approval"]["approved_at"]
                reserved = store.reserve_execution_approval(plan.id, approved_at=at, tool_name="write_file", risk_class="low")
                self.assertEqual(reserved.metadata["execution_approval"]["execution_state"], "reserved")
                finalized = store.finalize_execution_approval(plan.id, approved_at=at, tool_name="write_file", risk_class="low", ok=False, error="boom")
                self.assertEqual(finalized.metadata["execution_approval"]["execution_state"], "failed")
                with self.assertRaises(ValueError):
                    store.reserve_execution_approval(plan.id, approved_at=at, tool_name="write_file", risk_class="low")

    def test_admin_resolve_reserved_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "plans.db"
            with SQLitePlanStore(db) as store:
                plan = store.save_plan(
                    goal="Ready",
                    status="accepted",
                    steps=[{"id": "step-1", "title": "Do", "status": "pending"}],
                    source="test",
                )
                approved = store.approve_execution(plan.id, reason="ok", tool_name="write_file", risk_class="low")
                at = approved.metadata["execution_approval"]["approved_at"]
                store.reserve_execution_approval(plan.id, approved_at=at, tool_name="write_file", risk_class="low")
                rec = store.finalize_execution_approval(plan.id, approved_at=at, tool_name="write_file", risk_class="low", ok=False, error="manual", actor="admin", resolution="cancelled")
                self.assertEqual(rec.metadata["execution_approval"]["execution_state"], "cancelled")
                self.assertEqual(rec.metadata["execution_approval"]["finalized_by"], "admin")

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
