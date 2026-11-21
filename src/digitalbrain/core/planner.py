"""Deterministic planning for DigitalBrain.

The planner converts a goal and context snapshot into an inspectable plan.
Rules are explicit and testable; no opaque scoring or external AI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class StepStatus(StrEnum):
    PENDING = "pending"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class PlanStep:
    """A single, inspectable plan step."""

    id: str
    title: str
    description: str
    verification: str
    status: StepStatus = StepStatus.PENDING
    depends_on: tuple[str, ...] = ()
    source_rule: str = "baseline"
    alternatives: tuple[dict[str, str], ...] = ()

    def to_text(self) -> str:
        prefix = "[BLOCKED] " if self.status == StepStatus.BLOCKED else ""
        return f"{prefix}{self.title}"


@dataclass(frozen=True, slots=True)
class Plan:
    """A structured plan with deterministic provenance."""

    goal: str
    steps: tuple[PlanStep, ...]
    warnings: tuple[str, ...] = ()

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    def to_text_tuple(self) -> tuple[str, ...]:
        return tuple(step.to_text() for step in self.steps)


class DeterministicPlanner:
    """Rule-based planner that consumes context signals explicitly."""

    def plan(self, goal: str, context: Any) -> Plan:
        normalized_goal = goal.strip()
        if not normalized_goal:
            raise ValueError("Goal must not be empty.")

        steps: list[PlanStep] = []
        warnings: list[str] = []
        n = 1

        def add(
            title: str,
            description: str,
            verification: str,
            *,
            status: StepStatus = StepStatus.PENDING,
            depends_on: tuple[str, ...] = (),
            source_rule: str,
            alternatives: tuple[dict[str, str], ...] = (),
        ) -> PlanStep:
            nonlocal n
            step = PlanStep(
                id=f"step-{n}",
                title=title,
                description=description,
                verification=verification,
                status=status,
                depends_on=depends_on,
                source_rule=source_rule,
                alternatives=alternatives,
            )
            steps.append(step)
            n += 1
            return step

        add(
            "Clarify the desired outcome and define measurable success criteria.",
            "Define what success means for the goal and how it will be measured.",
            "Success criteria are written and unambiguous.",
            source_rule="baseline.clarify",
        )
        add(
            "Identify constraints, available resources, and potential risks.",
            "Capture constraints, dependencies, resources, and known risks.",
            "Constraints and risks are documented.",
            source_rule="baseline.constraints",
        )

        selected_facts = tuple(getattr(context, "selected_facts", ()))
        relevant_facts = tuple(getattr(context, "relevant_facts", ()))
        conflicts = tuple(getattr(context, "knowledge_conflicts", ()))
        recent_goals = tuple(getattr(context, "recent_goals", ()))

        if relevant_facts:
            add(
                f"Review {len(selected_facts)} selected knowledge fact(s) relevant to the goal.",
                "Inspect selected facts, their provenance, confidence, and selection reasons before using them.",
                "Relevant facts are reviewed; low-confidence or conflicting facts are flagged.",
                source_rule="context.selected_facts",
            )

        conflict_step_id: str | None = None
        if conflicts:
            warning = f"{len(conflicts)} relevant knowledge conflict(s) require review before relying on affected facts."
            warnings.append(warning)
            conflict_step = add(
                f"Resolve {len(conflicts)} knowledge conflict(s) before relying on affected facts.",
                "Review conflicting facts, verify sources, and correct/supersede knowledge as needed.",
                "Conflicts are resolved or explicitly accepted with recorded rationale.",
                status=StepStatus.BLOCKED,
                source_rule="context.knowledge_conflicts",
                alternatives=(
                    {
                        "id": "resolve-by-source",
                        "title": "Verify authoritative source and correct knowledge",
                        "reason": "Preferred when provenance can be verified.",
                    },
                    {
                        "id": "defer-with-risk",
                        "title": "Defer decision and record explicit risk",
                        "reason": "Use only when verification is impossible now; keep conflict visible.",
                    },
                ),
            )
            conflict_step_id = conflict_step.id

        if recent_goals:
            add(
                f"Consider {len(recent_goals)} recent related goal(s) to avoid duplicate work.",
                "Check recent similar goals for reusable outcomes or known pitfalls.",
                "Related prior goals are considered and duplication is avoided.",
                source_rule="context.recent_goals",
            )

        breakdown_deps = (conflict_step_id,) if conflict_step_id else ()
        add(
            "Break the objective into small, independently verifiable tasks.",
            "Decompose the goal into ordered tasks with clear verification.",
            "Tasks are small, ordered, and each has a verification step.",
            depends_on=breakdown_deps,
            source_rule="baseline.breakdown",
        )
        add(
            "Choose an approach and implement the smallest useful first step.",
            "Select the simplest viable approach and implement the first verifiable increment.",
            "First increment is implemented or clearly specified.",
            depends_on=breakdown_deps,
            source_rule="baseline.implement",
            alternatives=(
                {
                    "id": "smallest-viable-step",
                    "title": "Implement the smallest verifiable increment",
                    "reason": "Default deterministic choice for low risk and fast feedback.",
                },
                {
                    "id": "prototype-first",
                    "title": "Build a throwaway prototype before implementation",
                    "reason": "Use when uncertainty is high but prototype cost is low.",
                },
            ),
        )
        add(
            "Run checks, evaluate the results, and record what was learned.",
            "Execute relevant checks, capture outcomes, and persist learnings.",
            "Checks run, outcomes recorded, and follow-up identified.",
            depends_on=breakdown_deps,
            source_rule="baseline.evaluate",
        )

        return Plan(goal=normalized_goal, steps=tuple(steps), warnings=tuple(warnings))
