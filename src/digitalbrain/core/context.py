"""Context assembly for DigitalBrain.

Builds a small, inspectable context snapshot from memory and knowledge stores.
This is a deterministic baseline - no autonomous reasoning or external AI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from digitalbrain.knowledge import SQLiteKnowledgeStore
from digitalbrain.memory import MemoryType, SQLiteMemoryStore


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    goal: str
    recent_goals: tuple[str, ...]
    relevant_memories: tuple[dict[str, Any], ...]
    relevant_facts: tuple[dict[str, Any], ...]


class ContextAssembler:
    """Assemble context from available stores."""

    def __init__(
        self,
        memory: SQLiteMemoryStore | None = None,
        knowledge: SQLiteKnowledgeStore | None = None,
    ) -> None:
        self._memory = memory
        self._knowledge = knowledge

    def assemble(self, goal: str, *, limit: int = 5) -> ContextSnapshot:
        normalized = goal.strip()
        if not normalized:
            raise ValueError("Goal must not be empty.")
        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")

        recent_goals: list[str] = []
        relevant_memories: list[dict[str, Any]] = []
        relevant_facts: list[dict[str, Any]] = []

        if self._memory is not None:
            goals = self._memory.list_records(memory_type=MemoryType.GOAL, limit=limit)
            recent_goals = [r.content for r in goals if r.content != normalized][:limit]
            for record in self._memory.list_records(search=normalized.split()[0], limit=limit):
                relevant_memories.append(
                    {
                        "id": record.id,
                        "type": record.memory_type,
                        "content": record.content,
                        "source": record.source,
                        "confidence": record.confidence,
                    }
                )

        if self._knowledge is not None:
            query = normalized.split()[0]
            for fact in self._knowledge.list_facts(search=query, limit=limit):
                relevant_facts.append(
                    {
                        "id": fact.id,
                        "fact": fact.fact,
                        "source": fact.source,
                        "confidence": fact.confidence,
                    }
                )

        return ContextSnapshot(
            goal=normalized,
            recent_goals=tuple(recent_goals),
            relevant_memories=tuple(relevant_memories),
            relevant_facts=tuple(relevant_facts),
        )
