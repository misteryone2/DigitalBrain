"""Small, deterministic orchestration core.

This is intentionally a baseline. It establishes stable interfaces before
adding model-based reasoning, memory, tools, or autonomous code execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GoalStatus(StrEnum):
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class GoalResult:
    goal: str
    status: GoalStatus
    plan: tuple[str, ...]


class DigitalBrain:
    """Accept an objective and produce a safe, inspectable starter plan."""

    def process_goal(self, goal: str) -> GoalResult:
        normalized_goal = goal.strip()
        if not normalized_goal:
            raise ValueError("The goal must not be empty.")

        plan = (
            "Clarify the desired outcome and define measurable success criteria.",
            "Identify constraints, available resources, and potential risks.",
            "Break the objective into small, independently verifiable tasks.",
            "Choose an approach and implement the smallest useful first step.",
            "Run checks, evaluate the results, and record what was learned.",
        )
        return GoalResult(
            goal=normalized_goal,
            status=GoalStatus.ACCEPTED,
            plan=plan,
        )
