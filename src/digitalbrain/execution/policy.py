"""Execution policy for DigitalBrain.

Default deny. Read-only tools can be allowlisted explicitly. Mutating tools are
blocked unless explicitly enabled by policy and approved with a ready execution gate.
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
    """Deterministic allowlist policy.

    M4 baseline: read-only allowlisted tools only. Mutating tools remain denied by
    default even if allowlisted, unless allow_mutating=True and an explicit approval
    is present with a ready execution gate.
    """

    def __init__(
        self,
        allowed_tools: set[str] | None = None,
        *,
        allow_read_only: bool = True,
        allow_mutating: bool = False,
    ) -> None:
        self.allowed_tools = set(allowed_tools or [])
        self.allow_read_only = allow_read_only
        self.allow_mutating = allow_mutating

    def evaluate(
        self,
        tool_name: str,
        *,
        read_only: bool,
        execution_gate: dict[str, Any] | None = None,
        approval: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        if tool_name not in self.allowed_tools:
            return PolicyDecision(False, f"Tool '{tool_name}' is not in allowlist.")

        gate_status = str((execution_gate or {}).get("status", "unknown"))
        approved = bool((approval or {}).get("approved", False))

        if read_only:
            if not self.allow_read_only:
                return PolicyDecision(False, "Read-only tools are disabled by policy.")
            if gate_status == "needs_review":
                return PolicyDecision(True, "Allowed read-only tool; plan execution gate needs review.")
            return PolicyDecision(True, "Allowed by read-only allowlist policy.")

        if not self.allow_mutating:
            return PolicyDecision(False, f"Tool '{tool_name}' is mutating; mutating tools are disabled.")
        if gate_status != "ready":
            return PolicyDecision(False, f"Tool '{tool_name}' is mutating; execution gate is {gate_status}.")
        if not approved:
            return PolicyDecision(False, f"Tool '{tool_name}' is mutating; explicit approval required.")

        approved_tool = (approval or {}).get("tool_name")
        if approved_tool and approved_tool != tool_name:
            return PolicyDecision(False, f"Approval is scoped to tool '{approved_tool}', not '{tool_name}'.")
        return PolicyDecision(True, "Allowed mutating tool by explicit approval and ready gate.")
