
from dataclasses import dataclass
from enum import StrEnum


class IntentType(StrEnum):
    CONVERSATION = "conversation"
    QUESTION = "question"
    GOAL = "goal"
    INSTRUCTION = "instruction"
    UNCLEAR = "unclear"


@dataclass(frozen=True, slots=True)
class IntentResult:
    intent: IntentType
    confidence: float
    needs_clarification: bool
    explanation: str


class IntentClassifier:
    """Classifies messages using simple, explicit language patterns."""

    CONVERSATION_PATTERNS = (
        "ciao",
        "buongiorno",
        "buonasera",
        "buonanotte",
        "come stai",
        "grazie",
        "arrivederci",
        "hello",
        "hi",
        "thank you",
    )

    GOAL_PATTERNS = (
        "voglio creare",
        "voglio costruire",
        "voglio sviluppare",
        "vorrei creare",
        "vorrei costruire",
        "vorrei sviluppare",
        "il mio obiettivo è",
        "desidero realizzare",
        "mi piacerebbe creare",
    )

    INSTRUCTION_PATTERNS = (
        "apri ",
        "chiudi ",
        "crea ",
        "modifica ",
        "elimina ",
        "scrivi ",
        "leggi ",
        "esegui ",
        "salva ",
        "open ",
        "close ",
        "create ",
        "modify ",
        "delete ",
        "write ",
        "run ",
        "save ",
    )

    QUESTION_PATTERNS = (
        "chi ",
        "cosa ",
        "come ",
        "quando ",
        "dove ",
        "perché ",
        "quanto ",
        "quale ",
        "quali ",
        "posso ",
        "puoi ",
        "is ",
        "what ",
        "how ",
        "when ",
        "where ",
        "why ",
        "can ",
    )

    def classify(self, message: str) -> IntentResult:
        text = message.strip().lower()

        if not text:
            return IntentResult(
                IntentType.UNCLEAR,
                0.0,
                True,
                "The message is empty.",
            )

        if any(text.startswith(p) for p in self.CONVERSATION_PATTERNS):
            return IntentResult(
                IntentType.CONVERSATION,
                0.95,
                False,
                "A conversational expression was recognized.",
            )

        if any(text.startswith(p) for p in self.GOAL_PATTERNS):
            return IntentResult(
                IntentType.GOAL,
                0.90,
                False,
                "An explicit goal expression was recognized.",
            )

        if text.endswith("?") or any(
            text.startswith(p) for p in self.QUESTION_PATTERNS
        ):
            return IntentResult(
                IntentType.QUESTION,
                0.90,
                False,
                "A question structure was recognized.",
            )

        if any(text.startswith(p) for p in self.INSTRUCTION_PATTERNS):
            return IntentResult(
                IntentType.INSTRUCTION,
                0.90,
                False,
                "An imperative expression was recognized.",
            )

        return IntentResult(
            IntentType.UNCLEAR,
            0.0,
            True,
            "The intention could not be identified reliably.",
        )
