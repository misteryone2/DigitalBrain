"""Plan lifecycle and execution gate utilities.

Deterministic, inspectable rules only. No autonomous execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class PlanLifecycleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ExecutionGateResult:
    executable: bool
    status: str  # "ready" | "needs_review"
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "executable": self.executable,
            "status": self.status,
            "reasons": list(self.reasons),
        }


def evaluate_execution_gate(plan_steps: list[dict[str, Any]] | tuple[dict[str, Any], ...], warnings: tuple[str, ...] | list[str]) -> ExecutionGateResult:
    reasons: list[str] = []
    for step in plan_steps:
        status = str(step.get("status", "pending"))
        if status == "blocked":
            reasons.append(f"Step {step.get('id', '?')} is blocked: {step.get('title', '')}")
    for warning in warnings:
        reasons.append(f"Warning: {warning}")
    # dedupe while preserving order
    deduped = tuple(dict.fromkeys(reasons))
    if deduped:
        return ExecutionGateResult(executable=False, status="needs_review", reasons=deduped)
    return ExecutionGateResult(executable=True, status="ready", reasons=())


def record_step_outcome(
    steps: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    step_id: str,
    outcome: str,
    reason: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized_outcome = outcome.strip().lower()
    if normalized_outcome not in {"passed", "failed", "skipped"}:
        raise ValueError("Outcome must be passed, failed, or skipped.")
    updated: list[dict[str, Any]] = []
    found: dict[str, Any] | None = None
    for raw in steps:
        step = dict(raw)
        if step.get("id") == step_id:
            history = step.get("outcome_history", [])
            if not isinstance(history, list):
                history = [history]
            event = {
                "at": datetime.now(timezone.utc).isoformat(),
                "outcome": normalized_outcome,
                "reason": reason,
            }
            history.append(event)
            step["outcome_history"] = history
            step["last_outcome"] = normalized_outcome
            found = {"step_id": step_id, "outcome": normalized_outcome, "reason": reason}
        updated.append(step)
    if found is None:
        raise ValueError(f"Unknown step id: {step_id}")
    return updated, found