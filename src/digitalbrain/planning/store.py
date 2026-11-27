"""SQLite-backed plan storage for DigitalBrain.

Plans are stored as append-only versioned records. Replanning creates a new
record linked to the previous version; history is preserved for audit/review.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from digitalbrain.planning.lifecycle import evaluate_execution_gate, record_step_outcome


@dataclass(frozen=True, slots=True)
class PlanRecord:
    id: str
    created_at: str
    goal: str
    status: str
    lifecycle_status: str
    version: int
    parent_plan_id: str | None
    source: str
    warnings: tuple[str, ...]
    context_summary: dict[str, Any]
    steps: tuple[dict[str, Any], ...]
    metadata: dict[str, Any]

    @property
    def is_latest(self) -> bool:
        # caller can determine via query; kept for convenience when set externally
        return True


class SQLitePlanStore:
    """Persist and retrieve plan versions in SQLite."""

    SCHEMA_VERSION = 2

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

    def __enter__(self) -> "SQLitePlanStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _initialize(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_records (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL,
                lifecycle_status TEXT NOT NULL DEFAULT 'active',
                version INTEGER NOT NULL,
                parent_plan_id TEXT,
                source TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                context_summary_json TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (parent_plan_id) REFERENCES plan_records(id)
            )
            """
        )
        self._ensure_columns()
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_records_goal_created ON plan_records(goal, created_at DESC)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_records_parent ON plan_records(parent_plan_id)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_records_lifecycle ON plan_records(lifecycle_status, created_at DESC)"
        )
        current = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if current == 0:
            self._connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        elif current == 1:
            self._connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        elif current != self.SCHEMA_VERSION:
            raise RuntimeError(f"Unsupported plan schema version {current}")
        self._connection.commit()

    def _ensure_columns(self) -> None:
        cols = {row["name"] for row in self._connection.execute("PRAGMA table_info(plan_records)").fetchall()}
        if "lifecycle_status" not in cols:
            self._connection.execute(
                "ALTER TABLE plan_records ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'active'"
            )
        if "metadata_json" not in cols:
            self._connection.execute(
                "ALTER TABLE plan_records ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'"
            )

    def save_plan(
        self,
        *,
        goal: str,
        status: str,
        steps: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        source: str,
        warnings: list[str] | tuple[str, ...] = (),
        context_summary: dict[str, Any] | None = None,
        parent_plan_id: str | None = None,
        lifecycle_status: str = "active",
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> PlanRecord:
        goal_n = goal.strip()
        status_n = status.strip()
        source_n = source.strip()
        lifecycle_n = lifecycle_status.strip()
        if not goal_n:
            raise ValueError("Goal must not be empty.")
        if not status_n:
            raise ValueError("Status must not be empty.")
        if not source_n:
            raise ValueError("Source must not be empty.")
        if not lifecycle_n:
            raise ValueError("Lifecycle status must not be empty.")
        if not steps:
            raise ValueError("Steps must not be empty.")

        with self._connection:
            version = 1
            if parent_plan_id is not None:
                parent = self._get_row(parent_plan_id)
                if parent is None:
                    raise ValueError(f"Unknown parent plan: {parent_plan_id}")
                version = int(parent["version"]) + 1
                self._set_lifecycle(parent_plan_id, "superseded", reason="replanned")
            record = PlanRecord(
                id=uuid.uuid4().hex,
                created_at=(created_at or datetime.now(timezone.utc)).isoformat(),
                goal=goal_n,
                status=status_n,
                lifecycle_status=lifecycle_n,
                version=version,
                parent_plan_id=parent_plan_id,
                source=source_n,
                warnings=tuple(str(w) for w in warnings),
                context_summary=dict(context_summary or {}),
                steps=tuple(dict(s) for s in steps),
                metadata=dict(metadata or {}),
            )
            self._connection.execute(
                """
                INSERT INTO plan_records (
                    id, created_at, goal, status, lifecycle_status, version, parent_plan_id, source,
                    warnings_json, context_summary_json, steps_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.created_at,
                    record.goal,
                    record.status,
                    record.lifecycle_status,
                    record.version,
                    record.parent_plan_id,
                    record.source,
                    json.dumps(list(record.warnings), ensure_ascii=False),
                    json.dumps(record.context_summary, sort_keys=True, ensure_ascii=False),
                    json.dumps(list(record.steps), ensure_ascii=False),
                    json.dumps(record.metadata, sort_keys=True, ensure_ascii=False),
                ),
            )
        return record

    def get(self, plan_id: str) -> PlanRecord | None:
        row = self._get_row(plan_id)
        return self._row_to_record(row) if row else None

    def list_plans(self, *, limit: int = 100, goal: str | None = None) -> list[PlanRecord]:
        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")
        query = ["SELECT * FROM plan_records WHERE 1=1"]
        params: list[Any] = []
        if goal is not None:
            goal_n = goal.strip()
            if not goal_n:
                raise ValueError("Goal filter must not be empty.")
            query.append("AND goal = ?")
            params.append(goal_n)
        query.append("ORDER BY created_at DESC, rowid DESC LIMIT ?")
        params.append(limit)
        rows = self._connection.execute("\n".join(query), params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def latest_for_goal(self, goal: str) -> PlanRecord | None:
        plans = self.list_plans(limit=1, goal=goal)
        return plans[0] if plans else None

    def set_lifecycle_status(self, plan_id: str, lifecycle_status: str, *, reason: str | None = None) -> PlanRecord:
        lifecycle_n = lifecycle_status.strip()
        if not lifecycle_n:
            raise ValueError("Lifecycle status must not be empty.")
        with self._connection:
            row = self._get_row(plan_id)
            if row is None:
                raise ValueError(f"Unknown plan: {plan_id}")
            self._set_lifecycle(plan_id, lifecycle_n, reason=reason)
        record = self.get(plan_id)
        if record is None:  # pragma: no cover
            raise RuntimeError("Plan not found after update")
        return record

    def approve_execution(
        self,
        plan_id: str,
        *,
        reason: str | None = None,
        actor: str = "cli",
        tool_name: str | None = None,
        risk_class: str | None = None,
    ) -> PlanRecord:
        """Record explicit execution approval. Does not execute tools automatically.

        Approval is scoped to plan, and optionally to a tool/risk class for finer control.
        """
        with self._connection:
            row = self._get_row(plan_id)
            if row is None:
                raise ValueError(f"Unknown plan: {plan_id}")
            record = self._row_to_record(row)
            gate = evaluate_execution_gate(record.steps, record.warnings)
            if gate.status != "ready":
                raise ValueError(
                    f"Plan {plan_id} is not ready for approval: {gate.status}; reasons={list(gate.reasons)}"
                )
            metadata = dict(record.metadata)
            approval = {
                "approved": True,
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "actor": actor,
                "reason": reason,
                "gate_status": gate.status,
                "tool_name": tool_name,
                "risk_class": risk_class,
                "plan_id": plan_id,
                "consumed_at": None,
                "consumed_by_tool": None,
            }
            metadata["execution_approval"] = approval
            approvals = metadata.get("execution_approvals", [])
            if not isinstance(approvals, list):
                approvals = [approvals]
            approvals.append(approval)
            metadata["execution_approvals"] = approvals
            self._connection.execute(
                "UPDATE plan_records SET metadata_json = ? WHERE id = ?",
                (json.dumps(metadata, sort_keys=True, ensure_ascii=False), plan_id),
            )
            self._set_lifecycle(plan_id, "approved_for_execution", reason=reason or "explicit approval")
        updated = self.get(plan_id)
        if updated is None:  # pragma: no cover
            raise RuntimeError("Plan not found after approval")
        return updated

    def reserve_execution_approval(
        self,
        plan_id: str,
        *,
        approved_at: str,
        tool_name: str,
        risk_class: str | None = None,
    ) -> PlanRecord:
        with self._connection:
            row = self._get_row(plan_id)
            if row is None:
                raise ValueError(f"Unknown plan: {plan_id}")
            metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            if not isinstance(metadata, dict):
                metadata = {"value": metadata}
            approvals = metadata.get("execution_approvals", [])
            if not isinstance(approvals, list):
                approvals = [approvals]
            now = datetime.now(timezone.utc).isoformat()
            found = False
            for item in approvals:
                if not isinstance(item, dict) or item.get("approved_at") != approved_at:
                    continue
                if item.get("tool_name") and item.get("tool_name") != tool_name:
                    continue
                if item.get("risk_class") and risk_class and item.get("risk_class") != risk_class:
                    continue
                if item.get("consumed_at"):
                    raise ValueError("Approval already consumed.")
                if item.get("reserved_at") and not item.get("finalized_at"):
                    raise ValueError("Approval already reserved.")
                item["reserved_at"] = now
                item["reserved_by_tool"] = tool_name
                item["execution_state"] = "reserved"
                found = True
                if metadata.get("execution_approval", {}).get("approved_at") == approved_at:
                    current = dict(metadata.get("execution_approval", {}))
                    current["reserved_at"] = now
                    current["reserved_by_tool"] = tool_name
                    current["execution_state"] = "reserved"
                    metadata["execution_approval"] = current
                break
            if not found:
                raise ValueError("Approval not found for reservation.")
            metadata["execution_approvals"] = approvals
            self._connection.execute(
                "UPDATE plan_records SET metadata_json = ? WHERE id = ?",
                (json.dumps(metadata, sort_keys=True, ensure_ascii=False), plan_id),
            )
        rec = self.get(plan_id)
        if rec is None:  # pragma: no cover
            raise RuntimeError("Plan not found after approval reservation")
        return rec

    def finalize_execution_approval(
        self,
        plan_id: str,
        *,
        approved_at: str,
        tool_name: str,
        risk_class: str | None = None,
        ok: bool,
        error: str | None = None,
    ) -> PlanRecord:
        with self._connection:
            row = self._get_row(plan_id)
            if row is None:
                raise ValueError(f"Unknown plan: {plan_id}")
            metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            if not isinstance(metadata, dict):
                metadata = {"value": metadata}
            approvals = metadata.get("execution_approvals", [])
            if not isinstance(approvals, list):
                approvals = [approvals]
            now = datetime.now(timezone.utc).isoformat()
            found = False
            for item in approvals:
                if not isinstance(item, dict) or item.get("approved_at") != approved_at:
                    continue
                if item.get("tool_name") and item.get("tool_name") != tool_name:
                    continue
                if item.get("risk_class") and risk_class and item.get("risk_class") != risk_class:
                    continue
                if not item.get("reserved_at"):
                    raise ValueError("Approval is not reserved.")
                if item.get("finalized_at"):
                    raise ValueError("Approval already finalized.")
                item["finalized_at"] = now
                item["consumed_at"] = now
                item["consumed_by_tool"] = tool_name
                item["execution_state"] = "executed" if ok else "failed"
                item["execution_error"] = error
                found = True
                if metadata.get("execution_approval", {}).get("approved_at") == approved_at:
                    current = dict(metadata.get("execution_approval", {}))
                    current["finalized_at"] = now
                    current["consumed_at"] = now
                    current["consumed_by_tool"] = tool_name
                    current["execution_state"] = item["execution_state"]
                    current["execution_error"] = error
                    metadata["execution_approval"] = current
                break
            if not found:
                raise ValueError("Approval not found for finalization.")
            metadata["execution_approvals"] = approvals
            self._connection.execute(
                "UPDATE plan_records SET metadata_json = ? WHERE id = ?",
                (json.dumps(metadata, sort_keys=True, ensure_ascii=False), plan_id),
            )
        rec = self.get(plan_id)
        if rec is None:  # pragma: no cover
            raise RuntimeError("Plan not found after approval finalization")
        return rec

    def consume_execution_approval(
        self,
        plan_id: str,
        *,
        approved_at: str,
        tool_name: str,
        risk_class: str | None = None,
    ) -> PlanRecord:
        # Backward-compatible alias: reserve+finalize as executed.
        self.reserve_execution_approval(plan_id, approved_at=approved_at, tool_name=tool_name, risk_class=risk_class)
        return self.finalize_execution_approval(
            plan_id,
            approved_at=approved_at,
            tool_name=tool_name,
            risk_class=risk_class,
            ok=True,
            error=None,
        )

    def record_step_outcome(
        self,
        plan_id: str,
        step_id: str,
        outcome: str,
        *,
        reason: str | None = None,
    ) -> tuple[PlanRecord, dict[str, Any]]:
        with self._connection:
            row = self._get_row(plan_id)
            if row is None:
                raise ValueError(f"Unknown plan: {plan_id}")
            record = self._row_to_record(row)
            updated_steps, event = record_step_outcome(record.steps, step_id=step_id, outcome=outcome, reason=reason)
            gate = evaluate_execution_gate(updated_steps, record.warnings)
            metadata = dict(record.metadata)
            metadata["execution_gate"] = gate.to_dict()
            metadata["last_step_outcome"] = event
            proposal = event.get("replan_proposal")
            if isinstance(proposal, dict):
                proposal = {
                    **proposal,
                    "plan_id": plan_id,
                    "goal": record.goal,
                    "suggested_command": f'digitalbrain --plan-db <plan-db> --replan "{record.goal}" --reason "{proposal.get("reason", "")}"',
                }
                event["replan_proposal"] = proposal
                metadata["last_replan_proposal"] = proposal
            self._connection.execute(
                "UPDATE plan_records SET steps_json = ?, metadata_json = ? WHERE id = ?",
                (
                    json.dumps(updated_steps, ensure_ascii=False),
                    json.dumps(metadata, sort_keys=True, ensure_ascii=False),
                    plan_id,
                ),
            )
        updated = self.get(plan_id)
        if updated is None:  # pragma: no cover
            raise RuntimeError("Plan not found after update")
        return updated, event

    def _set_lifecycle(self, plan_id: str, lifecycle_status: str, *, reason: str | None = None) -> None:
        row = self._get_row(plan_id)
        if row is None:
            raise ValueError(f"Unknown plan: {plan_id}")
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        if not isinstance(metadata, dict):
            metadata = {"value": metadata}
        history = metadata.get("lifecycle_history", [])
        if not isinstance(history, list):
            history = [history]
        history.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "status": lifecycle_status,
                "reason": reason,
            }
        )
        metadata["lifecycle_history"] = history
        self._connection.execute(
            "UPDATE plan_records SET lifecycle_status = ?, metadata_json = ? WHERE id = ?",
            (lifecycle_status, json.dumps(metadata, sort_keys=True, ensure_ascii=False), plan_id),
        )

    def _get_row(self, plan_id: str) -> sqlite3.Row | None:
        return self._connection.execute("SELECT * FROM plan_records WHERE id = ?", (plan_id,)).fetchone()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> PlanRecord:
        warnings = json.loads(row["warnings_json"]) if row["warnings_json"] else []
        context_summary = json.loads(row["context_summary_json"]) if row["context_summary_json"] else {}
        steps = json.loads(row["steps_json"]) if row["steps_json"] else []
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        if not isinstance(warnings, list):
            warnings = [warnings]
        if not isinstance(context_summary, dict):
            context_summary = {"value": context_summary}
        if not isinstance(steps, list):
            steps = [steps]
        if not isinstance(metadata, dict):
            metadata = {"value": metadata}
        keys = row.keys()
        lifecycle_status = row["lifecycle_status"] if "lifecycle_status" in keys else "active"
        return PlanRecord(
            id=row["id"],
            created_at=row["created_at"],
            goal=row["goal"],
            status=row["status"],
            lifecycle_status=lifecycle_status,
            version=int(row["version"]),
            parent_plan_id=row["parent_plan_id"],
            source=row["source"],
            warnings=tuple(str(w) for w in warnings),
            context_summary=context_summary,
            steps=tuple(dict(s) if isinstance(s, dict) else {"value": s} for s in steps),
            metadata=metadata,
        )
