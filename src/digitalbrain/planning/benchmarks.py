"""Deterministic planning/failure/replanning benchmark scenarios.

These are measurable, testable checks - not opaque AI scoring.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from digitalbrain.planning.store import SQLitePlanStore


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    passed: bool
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_planning_benchmarks() -> list[BenchmarkResult]:
    from digitalbrain.core.brain import DigitalBrain, GoalStatus  # local import to avoid circular import

    results: list[BenchmarkResult] = []

    # 1) Deterministic planning structure
    brain = DigitalBrain()
    r = brain.process_goal("Build a local note app with storage and search")
    metrics = {
        "status": r.status.value,
        "plan_steps": len(r.plan),
        "warning_count": len(r.warnings),
        "has_verification": all(bool(s.verification) for s in r.plan_steps),
        "has_source_rule": all(bool(s.source_rule) for s in r.plan_steps),
        "has_alternatives": all(len(s.alternatives) >= 1 for s in r.plan_steps),
    }
    passed = (
        r.status in {GoalStatus.ACCEPTED, GoalStatus.ACCEPTED_WITH_WARNINGS}
        and metrics["plan_steps"] >= 3
        and metrics["has_verification"]
        and metrics["has_source_rule"]
        and metrics["has_alternatives"]
    )
    results.append(BenchmarkResult("planning_structure", passed, metrics))

    # 2) Failure -> replan proposal
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "plans.db"
        with SQLitePlanStore(db) as store:
            plan = store.save_plan(
                goal="Deploy service",
                status="accepted",
                steps=[
                    {"id": "step-1", "title": "Prepare", "status": "pending", "critical": True},
                    {"id": "step-2", "title": "Deploy", "status": "pending", "critical": False},
                ],
                source="benchmark",
                metadata={"execution_gate": {"status": "ready", "executable": True, "reasons": []}},
            )
            updated, event = store.record_step_outcome(plan.id, "step-1", "failed", reason="unit test failure")
            proposal = event.get("replan_proposal")
            gate = (updated.metadata or {}).get("execution_gate", {})
            metrics = {
                "outcome": event.get("outcome"),
                "critical": event.get("critical"),
                "has_replan_proposal": proposal is not None,
                "gate_status": gate.get("status"),
                "gate_executable": gate.get("executable"),
            }
            passed = (
                metrics["outcome"] == "failed"
                and metrics["critical"] is True
                and metrics["has_replan_proposal"] is True
                and metrics["gate_status"] == "needs_review"
                and metrics["gate_executable"] is False
            )
            results.append(BenchmarkResult("failure_replan_proposal", passed, metrics))

    # 3) Explicit replanning creates append-only version
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "plans.db"
        brain = DigitalBrain(plan_store=SQLitePlanStore(db))
        brain.plan_store = SQLitePlanStore(db)  # ensure instance
        with SQLitePlanStore(db) as store:
            b = DigitalBrain(plan_store=store)
            r1 = b.process_goal("Organize files")
            r2 = b.replan_goal("Organize files", reason="benchmark replanning")
            plans = store.list_plans(goal="Organize files")
        metrics = {
            "first_plan_id_present": bool(r1.plan_record_id),
            "second_plan_id_present": bool(r2.plan_record_id),
            "different_plan_ids": r1.plan_record_id != r2.plan_record_id,
            "versions": [p.version for p in plans],
            "statuses": [p.lifecycle_status for p in plans],
            "has_superseded": any(p.lifecycle_status == "superseded" for p in plans),
            "latest_is_active": plans[0].lifecycle_status == "active" if plans else False,
        }
        passed = (
            metrics["first_plan_id_present"]
            and metrics["second_plan_id_present"]
            and metrics["different_plan_ids"]
            and metrics["has_superseded"]
            and metrics["latest_is_active"]
            and max(metrics["versions"] or [0]) >= 2
        )
        results.append(BenchmarkResult("explicit_replanning_versioning", passed, metrics))

    return results
