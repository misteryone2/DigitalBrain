"""Core contracts for DigitalBrain.

These protocols define stable boundaries between components. Implementations
can evolve, but callers should depend on these contracts where practical.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from digitalbrain.core.planner import Plan


@runtime_checkable
class MemoryStoreProtocol(Protocol):
    def add_record(self, content: str, *, memory_type: Any, source: str, confidence: float = 1.0, metadata: dict[str, Any] | None = None) -> Any: ...
    def get(self, record_id: str) -> Any: ...
    def list_records(self, **kwargs: Any) -> list[Any]: ...


@runtime_checkable
class KnowledgeStoreProtocol(Protocol):
    def add_fact(self, subject: str, predicate: str, obj: str, *, source: str, confidence: float = 1.0, metadata: dict[str, Any] | None = None) -> Any: ...
    def get(self, record_id: str) -> Any: ...
    def list_facts(self, **kwargs: Any) -> list[Any]: ...


@runtime_checkable
class ContextAssemblerProtocol(Protocol):
    def assemble(self, goal: str, *, limit: int = 5) -> Any: ...


@runtime_checkable
class PlannerProtocol(Protocol):
    def plan(self, goal: str, context: Any) -> Plan: ...
