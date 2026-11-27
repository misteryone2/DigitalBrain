"""Execution policy for DigitalBrain.

Default deny. Read-only tools can be allowlisted explicitly. Mutating tools are
blocked in M4 baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason}


class ExecutionPolicy:
    """Simple deterministic allowlist policy."""

    def __init__(self, allowed_tools: set[str] | None = None, *, allow_read_only: bool = True) -> None:
        self.allowed_tools = set(allowed_tools or [])
        self.allow_read_only = allow_read_only

    def evaluate(self, tool_name: str, *, read_only: bool, execution_gate: dict[str, Any] | None = None) -> PolicyDecision:
        if tool_name not in self.allowed_tools:
            return PolicyDecision(False, f"Tool '{tool_name}' is not in allowlist.")
        if not read_only:
            return PolicyDecision(False, f"Tool '{tool_name}' is not read-only; mutating tools are disabled.")
        if not self.allow_read_only:
            return PolicyDecision(False, "Read-only tools are disabled by policy.")
        if execution_gate and execution_gate.get("status") == "needs_review":
            # For M4 read-only tools, we still allow inspection but record reason; caller can tighten later.
            return PolicyDecision(True, "Allowed read-only tool; plan execution gate needs review.")
        return PolicyDecision(True, "Allowed by read-only allowlist policy.")
