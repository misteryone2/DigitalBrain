"""Tests for the DigitalBrain core."""

import tempfile
import unittest
from pathlib import Path

from digitalbrain.core.brain import DigitalBrain, GoalStatus
from digitalbrain.core.intent import IntentType
from digitalbrain.memory import MemoryType, SQLiteMemoryStore


class DigitalBrainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.brain = DigitalBrain()

    def test_processes_non_empty_goal(self) -> None:
        result = self.brain.process_goal("Build a note-taking app")

        self.assertEqual(result.goal, "Build a note-taking app")
        self.assertEqual(result.status, GoalStatus.ACCEPTED)
        self.assertGreaterEqual(len(result.plan), 3)
        self.assertIsNone(result.memory_record_id)

    def test_trims_surrounding_whitespace(self) -> None:
        result = self.brain.process_goal("  Organize project files  ")
        self.assertEqual(result.goal, "Organize project files")

    def test_rejects_empty_goal(self) -> None:
        with self.assertRaises(ValueError):
            self.brain.process_goal("   ")

    def test_records_goal_when_memory_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as memory:
                brain = DigitalBrain(memory=memory)
                result = brain.process_goal("Track expenses")

                self.assertIsNotNone(result.memory_record_id)
                assert result.memory_record_id is not None
                record = memory.get(result.memory_record_id)

            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record.memory_type, MemoryType.GOAL.value)
            self.assertEqual(record.content, "Track expenses")
            self.assertEqual(record.source, "core.process_goal")
            self.assertIn("context", record.metadata)
            self.assertIsNotNone(result.context_summary)

    def test_process_message_records_episodic_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.db"
            with SQLiteMemoryStore(db_path) as memory:
                brain = DigitalBrain(memory=memory)
                result = brain.process_message("Ciao")

                self.assertEqual(result.intent.intent, IntentType.CONVERSATION)
                records = memory.list_records(memory_type=MemoryType.EPISODIC)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].content, "Ciao")
            self.assertEqual(records[0].source, "core.process_message")
            self.assertEqual(records[0].metadata["intent"], "conversation")


if __name__ == "__main__":
    unittest.main()
