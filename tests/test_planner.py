"""Tests for deterministic planner."""

import unittest
from types import SimpleNamespace

from digitalbrain.core.planner import DeterministicPlanner, StepStatus


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = DeterministicPlanner()

    def test_baseline_plan(self) -> None:
        context = SimpleNamespace(relevant_facts=(), selected_facts=(), knowledge_conflicts=(), recent_goals=())
        plan = self.planner.plan("Build app", context)
        self.assertFalse(plan.has_warnings)
        self.assertGreaterEqual(len(plan.steps), 5)
        self.assertEqual(plan.steps[0].source_rule, "baseline.clarify")

    def test_conflicts_create_blocked_step_and_warning(self) -> None:
        context = SimpleNamespace(
            relevant_facts=({"fact": "Project uses SQLite"},),
            selected_facts=({"fact": "Project uses SQLite"},),
            knowledge_conflicts=({"subject": "Project", "predicate": "uses"},),
            recent_goals=(),
        )
        plan = self.planner.plan("Improve Project", context)
        self.assertTrue(plan.has_warnings)
        blocked = [s for s in plan.steps if s.status == StepStatus.BLOCKED]
        self.assertEqual(len(blocked), 1)
        self.assertIn("conflict", blocked[0].title.lower())
        self.assertTrue(blocked[0].alternatives)
        # downstream steps depend on conflict resolution
        later = [s for s in plan.steps if s.source_rule.startswith("baseline.") and s.id != "step-1" and s.id != "step-2"]
        self.assertTrue(any(blocked[0].id in s.depends_on for s in later))

    def test_recent_goals_add_step(self) -> None:
        context = SimpleNamespace(relevant_facts=(), selected_facts=(), knowledge_conflicts=(), recent_goals=("Old goal",))
        plan = self.planner.plan("New goal", context)
        self.assertTrue(any(s.source_rule == "context.recent_goals" for s in plan.steps))


if __name__ == "__main__":
    unittest.main()
