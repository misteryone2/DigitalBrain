
import tempfile
import unittest
from pathlib import Path

from digitalbrain.memory.episodic import MemoryStore


class EpisodicMemoryTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temp_dir.name) / "memory.db"
        )
        self.memory = MemoryStore(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_stores_an_interaction(self):
        self.memory.remember_interaction(
            message="Ciao",
            intent="conversation",
            response="Conversazione riconosciuta.",
        )

        episodes = self.memory.get_recent_interactions()

        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0].message, "Ciao")
        self.assertEqual(episodes[0].intent, "conversation")

    def test_preserves_interactions_after_reopening(self):
        self.memory.remember_interaction(
            message="Voglio creare un programma",
            intent="goal",
            response="Obiettivo riconosciuto.",
        )

        reopened_memory = MemoryStore(self.database_path)
        episodes = reopened_memory.get_recent_interactions()

        self.assertEqual(len(episodes), 1)
        self.assertEqual(
            episodes[0].message,
            "Voglio creare un programma",
        )

    def test_returns_empty_list_when_no_memory_exists(self):
        episodes = self.memory.get_recent_interactions()

        self.assertEqual(episodes, [])

    def test_returns_newest_interactions_first(self):
        self.memory.remember_interaction(
            message="Primo messaggio",
            intent="conversation",
            response="Prima risposta",
        )

        self.memory.remember_interaction(
            message="Secondo messaggio",
            intent="question",
            response="Seconda risposta",
        )

        episodes = self.memory.get_recent_interactions()

        self.assertEqual(
            episodes[0].message,
            "Secondo messaggio",
        )


if __name__ == "__main__":
    unittest.main()
