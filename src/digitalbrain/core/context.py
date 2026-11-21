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
    knowledge_conflicts: tuple[dict[str, Any], ...] = ()
    selected_facts: tuple[dict[str, Any], ...] = ()
    context_notes: tuple[str, ...] = ()


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

        knowledge_conflicts: list[dict[str, Any]] = []
        selected_facts: list[dict[str, Any]] = []
        context_notes: list[str] = []
        if self._knowledge is not None:
            query = normalized.split()[0]
            for fact in self._knowledge.list_facts(search=query, limit=limit):
                relevant_facts.append(
                    {
                        "id": fact.id,
                        "subject": fact.subject,
                        "predicate": fact.predicate,
                        "object": fact.object,
                        "fact": fact.fact,
                        "source": fact.source,
                        "confidence": fact.confidence,
                        "created_at": fact.created_at,
                    }
                )
            for conflict in self._knowledge.find_conflicts(limit=limit):
                if any(query.lower() in str(v).lower() for v in conflict.values()):
                    knowledge_conflicts.append(conflict)

            # Deterministic policy: prefer highest confidence, then newest, then id.
            grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for fact in relevant_facts:
                grouped.setdefault((fact["subject"], fact["predicate"]), []).append(fact)
            for key, facts in grouped.items():
                ranked = sorted(
                    facts,
                    key=lambda f: (-float(f["confidence"]), f.get("created_at", ""), f["id"]),
                    reverse=False,
                )
                # reverse=False with -confidence gives high confidence first; created_at asc means old first, so negate by using reverse sort separately
                ranked = sorted(
                    facts,
                    key=lambda f: (float(f["confidence"]), f.get("created_at", ""), f["id"]),
                    reverse=True,
                )
                chosen = dict(ranked[0])
                chosen["selection_reason"] = "highest_confidence_then_newest_then_id"
                selected_facts.append(chosen)
                if len({f["object"] for f in facts}) > 1:
                    context_notes.append(
                        f"Conflict for {key[0]} {key[1]}: selected '{chosen['object']}' by deterministic policy; review required."
                    )

        if knowledge_conflicts:
            context_notes.append(
                f"{len(knowledge_conflicts)} relevant knowledge conflict(s) detected."
            )

        return ContextSnapshot(
            goal=normalized,
            recent_goals=tuple(recent_goals),
            relevant_memories=tuple(relevant_memories),
            relevant_facts=tuple(relevant_facts),
            knowledge_conflicts=tuple(knowledge_conflicts),
            selected_facts=tuple(selected_facts),
            context_notes=tuple(dict.fromkeys(context_notes)),
        )
