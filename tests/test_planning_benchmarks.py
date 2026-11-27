"""Tests for M3 planning/failure/replanning benchmarks."""

import unittest

from digitalbrain.planning.benchmarks import run_planning_benchmarks


class PlanningBenchmarksTests(unittest.TestCase):
    def test_benchmarks_pass(self) -> None:
        results = run_planning_benchmarks()
        self.assertGreaterEqual(len(results), 3)
        for r in results:
            self.assertTrue(r.passed, msg=f"{r.name} failed: {r.metrics}")

    def test_benchmark_metrics_are_measurable(self) -> None:
        results = run_planning_benchmarks()
        names = {r.name for r in results}
        self.assertIn("planning_structure", names)
        self.assertIn("failure_replan_proposal", names)
        self.assertIn("explicit_replanning_versioning", names)
        for r in results:
            self.assertIsInstance(r.metrics, dict)
            self.assertGreater(len(r.metrics), 0)


if __name__ == "__main__":
    unittest.main()
