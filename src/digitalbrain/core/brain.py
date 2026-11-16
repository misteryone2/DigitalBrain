
"""Core orchestration for DigitalBrain."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from digitalbrain.core.intent import (
    IntentClassifier,
    IntentResult,
    IntentType,
)


class GoalStatus(StrEnum):
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class GoalResult:
    goal: str
    status: GoalStatus
    plan: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MessageResult:
    message: str
    intent: IntentResult
    response: str
    goal_result: GoalResult | None = None


class DigitalBrain:
    """Central coordinator of the DigitalBrain system."""

    def __init__(self) -> None:
        self.intent_classifier = IntentClassifier()

    def process_message(self, message: str) -> MessageResult:
        normalized_message = message.strip()

        intent_result = self.intent_classifier.classify(
            normalized_message
        )

        if intent_result.intent == IntentType.CONVERSATION:
            response = (
                "Conversazione riconosciuta. "
                "Il modulo di dialogo non è ancora disponibile."
            )
            goal_result = None

        elif intent_result.intent == IntentType.QUESTION:
            response = (
                "Domanda riconosciuta. "
                "Il modulo di risposta non è ancora disponibile."
            )
            goal_result = None

        elif intent_result.intent == IntentType.GOAL:
            goal_result = self.process_goal(normalized_message)
            response = "Obiettivo riconosciuto. Piano iniziale generato."

        elif intent_result.intent == IntentType.INSTRUCTION:
            response = (
                "Istruzione riconosciuta. "
                "Il modulo di esecuzione non è ancora disponibile."
            )
            goal_result = None

        else:
            response = (
                "Non sono riuscito a identificare la tua intenzione. "
                "Puoi spiegarmi meglio cosa desideri?"
            )
            goal_result = None

        return MessageResult(
            message=normalized_message,
            intent=intent_result,
            response=response,
            goal_result=goal_result,
        )

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
