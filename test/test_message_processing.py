
import unittest

from digitalbrain.core.brain import DigitalBrain
from digitalbrain.core.intent import IntentType


class MessageProcessingTests(unittest.TestCase):

    def setUp(self):
        self.brain = DigitalBrain()

    def test_recognizes_conversation(self):
        result = self.brain.process_message("Ciao")

        self.assertEqual(
            result.intent.intent,
            IntentType.CONVERSATION
        )

    def test_recognizes_question(self):
        result = self.brain.process_message(
            "Quanto costa un computer?"
        )

        self.assertEqual(
            result.intent.intent,
            IntentType.QUESTION
        )

    def test_recognizes_goal(self):
        result = self.brain.process_message(
            "Voglio creare un'applicazione"
        )

        self.assertEqual(
            result.intent.intent,
            IntentType.GOAL
        )

        self.assertIsNotNone(result.goal_result)

    def test_recognizes_instruction(self):
        result = self.brain.process_message(
            "Apri il file principale"
        )

        self.assertEqual(
            result.intent.intent,
            IntentType.INSTRUCTION
        )

    def test_requests_clarification(self):
        result = self.brain.process_message(
            "La montagna è blu"
        )

        self.assertEqual(
            result.intent.intent,
            IntentType.UNCLEAR
        )

        self.assertTrue(
            result.intent.needs_clarification
        )


if __name__ == "__main__":
    unittest.main()
