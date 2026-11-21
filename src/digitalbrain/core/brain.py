"""Core orchestration for DigitalBrain.

This module coordinates baseline intent handling and goal planning. It
establishes stable interfaces before adding broader reasoning, knowledge,
learning, tools, or autonomous evolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from digitalbrain.core.intent import (
    IntentClassifier,
    IntentResult,
    IntentType,
)
from digitalbrain.memory import MemoryType, SQLiteMemoryStore


class GoalStatus(StrEnum):
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class GoalResult:
    goal: str
    status: GoalStatus
    plan: tuple[str, ...]
    memory_record_id: str | None = None


@dataclass(frozen=True, slots=True)
class MessageResult:
    message: str
    intent: IntentResult
    response: str
    goal_result: GoalResult | None = None


class DigitalBrain:
    """Central coordinator of the DigitalBrain system."""

    def __init__(self, memory: SQLiteMemoryStore | None = None) -> None:
        self.intent_classifier = IntentClassifier()
        self._memory = memory

    def process_message(self, message: str) -> MessageResult:
        normalized_message = message.strip()

        intent_result = self.intent_classifier.classify(normalized_message)
        goal_result = None

        if intent_result.intent == IntentType.CONVERSATION:
            response = (
                "Conversazione riconosciuta. "
                "Il modulo di dialogo non è ancora disponibile."
            )

        elif intent_result.intent == IntentType.QUESTION:
            response = (
                "Domanda riconosciuta. "
                "Il modulo di risposta non è ancora disponibile."
            )

        elif intent_result.intent == IntentType.GOAL:
            goal_result = self.process_goal(normalized_message)
            response = "Obiettivo riconosciuto. Piano iniziale generato."

        elif intent_result.intent == IntentType.INSTRUCTION:
            response = (
                "Istruzione riconosciuta. "
                "Il modulo di esecuzione non è ancora disponibile."
            )

        else:
            response = (
                "Non sono riuscito a identificare la tua intenzione. "
                "Puoi spiegarmi meglio cosa desideri?"
            )

        if self._memory is not None and normalized_message:
            self._memory.add_record(
                normalized_message,
                memory_type=MemoryType.EPISODIC,
                source="core.process_message",
                confidence=float(intent_result.confidence),
                metadata={
                    "intent": intent_result.intent.value,
                    "needs_clarification": intent_result.needs_clarification,
                    "explanation": intent_result.explanation,
                    "response": response,
                    "goal_memory_record_id": (
                        goal_result.memory_record_id if goal_result else None
                    ),
                },
            )

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
        memory_record_id = None
        if self._memory is not None:
            record = self._memory.add_record(
                normalized_goal,
                memory_type=MemoryType.GOAL,
                source="core.process_goal",
                confidence=1.0,
                metadata={
                    "status": GoalStatus.ACCEPTED.value,
                    "plan_steps": len(plan),
                },
            )
            memory_record_id = record.id
        return GoalResult(
            goal=normalized_goal,
            status=GoalStatus.ACCEPTED,
            plan=plan,
            memory_record_id=memory_record_id,
        )
