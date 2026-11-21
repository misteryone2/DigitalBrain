"""Core orchestration for DigitalBrain.

This module coordinates baseline intent handling and goal planning. It
establishes stable interfaces before adding broader reasoning, knowledge,
learning, tools, or autonomous evolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from digitalbrain.core.audit import AuditLog
from digitalbrain.core.context import ContextAssembler
from digitalbrain.core.contracts import (
    ContextAssemblerProtocol,
    KnowledgeStoreProtocol,
    MemoryStoreProtocol,
    PlannerProtocol,
    PlanStoreProtocol,
)
from digitalbrain.core.intent import (
    IntentClassifier,
    IntentResult,
    IntentType,
)
from digitalbrain.core.planner import DeterministicPlanner, Plan, PlanStep
from digitalbrain.knowledge import SQLiteKnowledgeStore
from digitalbrain.memory import MemoryType, SQLiteMemoryStore
from digitalbrain.planning import SQLitePlanStore


class GoalStatus(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNINGS = "accepted_with_warnings"


@dataclass(frozen=True, slots=True)
class GoalResult:
    goal: str
    status: GoalStatus
    plan: tuple[str, ...]
    memory_record_id: str | None = None
    context_summary: dict[str, int] | None = None
    plan_steps: tuple[PlanStep, ...] = ()
    warnings: tuple[str, ...] = ()
    plan_record_id: str | None = None


@dataclass(frozen=True, slots=True)
class MessageResult:
    message: str
    intent: IntentResult
    response: str
    goal_result: GoalResult | None = None


class DigitalBrain:
    """Central coordinator of the DigitalBrain system."""

    def __init__(
        self,
        memory: MemoryStoreProtocol | SQLiteMemoryStore | None = None,
        knowledge: KnowledgeStoreProtocol | SQLiteKnowledgeStore | None = None,
        context_assembler: ContextAssemblerProtocol | None = None,
        planner: PlannerProtocol | None = None,
        plan_store: PlanStoreProtocol | SQLitePlanStore | None = None,
        audit_log: AuditLog | None = None,
    ) -> None:
        self.intent_classifier = IntentClassifier()
        self._memory = memory
        self._knowledge = knowledge
        self._context = context_assembler or ContextAssembler(memory=memory, knowledge=knowledge)
        self._planner = planner or DeterministicPlanner()
        self._plan_store = plan_store
        self._audit = audit_log

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

        context = self._context.assemble(normalized_goal)
        plan_obj: Plan = self._planner.plan(normalized_goal, context)
        plan = plan_obj.to_text_tuple()
        status = (
            GoalStatus.ACCEPTED_WITH_WARNINGS
            if plan_obj.has_warnings
            else GoalStatus.ACCEPTED
        )

        memory_record_id = None
        plan_record_id = None
        if self._memory is not None:
            record = self._memory.add_record(
                normalized_goal,
                memory_type=MemoryType.GOAL,
                source="core.process_goal",
                confidence=1.0,
                metadata={
                    "status": status.value,
                    "plan_steps": len(plan),
                    "warnings": list(plan_obj.warnings),
                    "context": {
                        "recent_goals": len(context.recent_goals),
                        "relevant_memories": len(context.relevant_memories),
                        "relevant_facts": len(context.relevant_facts),
                        "selected_facts": len(context.selected_facts),
                        "knowledge_conflicts": len(context.knowledge_conflicts),
                    },
                    "context_notes": list(context.context_notes),
                    "plan": [self._step_to_dict(step) for step in plan_obj.steps],
                },
            )
            memory_record_id = record.id
        if self._plan_store is not None:
            parent = self._plan_store.latest_for_goal(normalized_goal)
            plan_record = self._plan_store.save_plan(
                goal=normalized_goal,
                status=status.value,
                steps=[self._step_to_dict(step) for step in plan_obj.steps],
                source="core.process_goal",
                warnings=list(plan_obj.warnings),
                context_summary={
                    "recent_goals": len(context.recent_goals),
                    "relevant_memories": len(context.relevant_memories),
                    "relevant_facts": len(context.relevant_facts),
                    "selected_facts": len(context.selected_facts),
                    "knowledge_conflicts": len(context.knowledge_conflicts),
                },
                parent_plan_id=parent.id if parent else None,
            )
            plan_record_id = plan_record.id
        if self._audit is not None:
            if context.knowledge_conflicts:
                self._audit.record(
                    "context.conflict_detected",
                    actor="DigitalBrain",
                    outcome="warning",
                    details={
                        "goal": normalized_goal,
                        "conflicts": len(context.knowledge_conflicts),
                    },
                )
            self._audit.record(
                "plan.generated",
                actor="DeterministicPlanner",
                outcome=status.value,
                details={
                    "goal": normalized_goal,
                    "plan_steps": len(plan),
                    "warnings": list(plan_obj.warnings),
                    "rules": [s.source_rule for s in plan_obj.steps],
                },
            )
            self._audit.record(
                "goal.processed",
                actor="DigitalBrain",
                outcome=status.value,
                details={
                    "goal": normalized_goal,
                    "memory_record_id": memory_record_id,
                    "plan_record_id": plan_record_id,
                    "plan_steps": len(plan),
                    "warnings": list(plan_obj.warnings),
                    "context_summary": {
                        "recent_goals": len(context.recent_goals),
                        "relevant_memories": len(context.relevant_memories),
                        "relevant_facts": len(context.relevant_facts),
                        "selected_facts": len(context.selected_facts),
                        "knowledge_conflicts": len(context.knowledge_conflicts),
                    },
                },
            )
        return GoalResult(
            goal=normalized_goal,
            status=status,
            plan=plan,
            memory_record_id=memory_record_id,
            context_summary={
                "recent_goals": len(context.recent_goals),
                "relevant_memories": len(context.relevant_memories),
                "relevant_facts": len(context.relevant_facts),
                "selected_facts": len(context.selected_facts),
                "knowledge_conflicts": len(context.knowledge_conflicts),
            },
            plan_steps=plan_obj.steps,
            warnings=plan_obj.warnings,
            plan_record_id=plan_record_id,
        )

    @staticmethod
    def _step_to_dict(step: PlanStep) -> dict[str, object]:
        return {
            "id": step.id,
            "title": step.title,
            "description": step.description,
            "verification": step.verification,
            "status": step.status.value,
            "depends_on": list(step.depends_on),
            "source_rule": step.source_rule,
        }
