"""Tests for the first DigitalBrain milestone."""

import unittest

from digitalbrain.core.brain import DigitalBrain, GoalStatus


class DigitalBrainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.brain = DigitalBrain()

    def test_processes_non_empty_goal(self) -> None:
        result = self.brain.process_goal("Build a note-taking app")

        self.assertEqual(result.goal, "Build a note-taking app")
        self.assertEqual(result.status, GoalStatus.ACCEPTED)
        self.assertGreaterEqual(len(result.plan), 3)

    def test_trims_surrounding_whitespace(self) -> None:
        result = self.brain.process_goal("  Organize project files  ")
        self.assertEqual(result.goal, "Organize project files")

    def test_rejects_empty_goal(self) -> None:
        with self.assertRaises(ValueError):
            self.brain.process_goal("   ")


if __name__ == "__main__":
    unittest.main()
