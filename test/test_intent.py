
import unittest

from digitalbrain.core.intent import IntentClassifier, IntentType


class IntentClassifierTests(unittest.TestCase):

    def setUp(self):
        self.classifier = IntentClassifier()

    def test_recognizes_conversation(self):
        result = self.classifier.classify("Ciao, come stai?")
        self.assertEqual(result.intent, IntentType.CONVERSATION)
        self.assertFalse(result.needs_clarification)

    def test_recognizes_question(self):
        result = self.classifier.classify("Quanto costa un computer?")
        self.assertEqual(result.intent, IntentType.QUESTION)

    def test_recognizes_goal(self):
        result = self.classifier.classify("Voglio creare un'applicazione")
        self.assertEqual(result.intent, IntentType.GOAL)

    def test_recognizes_instruction(self):
        result = self.classifier.classify("Apri il file principale")
        self.assertEqual(result.intent, IntentType.INSTRUCTION)

    def test_requests_clarification_for_unknown_message(self):
        result = self.classifier.classify("La montagna è blu")
        self.assertEqual(result.intent, IntentType.UNCLEAR)
        self.assertTrue(result.needs_clarification)

    def test_requests_clarification_for_empty_message(self):
        result = self.classifier.classify("   ")
        self.assertEqual(result.intent, IntentType.UNCLEAR)
        self.assertTrue(result.needs_clarification)


if __name__ == "__main__":
    unittest.main()
