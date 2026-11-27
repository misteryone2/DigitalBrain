"""Execution policy for DigitalBrain.

Default deny. Read-only tools can be allowlisted explicitly. Mutating tools are
blocked unless explicitly enabled by policy and approved with a ready execution gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
        tool_risk_class: str | None = None,
        sandbox_mode: str | None = None,
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
        if sandbox_mode != "container":
            return PolicyDecision(False, f"Tool '{tool_name}' is mutating; container sandbox required (mode={sandbox_mode or 'unknown'}).")
        if gate_status != "ready":
            return PolicyDecision(False, f"Tool '{tool_name}' is mutating; execution gate is {gate_status}.")
        if not approved:
            return PolicyDecision(False, f"Tool '{tool_name}' is mutating; explicit approval required.")

        approved_tool = (approval or {}).get("tool_name")
        if approved_tool and approved_tool != tool_name:
            return PolicyDecision(False, f"Approval is scoped to tool '{approved_tool}', not '{tool_name}'.")

        approved_risk = (approval or {}).get("risk_class")
        if approved_risk and tool_risk_class and approved_risk != tool_risk_class:
            return PolicyDecision(
                False,
                f"Approval risk class '{approved_risk}' does not match tool risk '{tool_risk_class}'.",
            )
        expires_at = (approval or {}).get("expires_at")
        if expires_at:
            try:
                exp = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) >= exp:
                    return PolicyDecision(False, "Execution approval has expired.")
            except ValueError:
                return PolicyDecision(False, "Execution approval has invalid expires_at.")
        if (approval or {}).get("reserved_at") and not (approval or {}).get("finalized_at"):
            return PolicyDecision(False, "Execution approval is already reserved.")
        if (approval or {}).get("consumed_at"):
            return PolicyDecision(False, "Execution approval has already been consumed.")
        return PolicyDecision(True, "Allowed mutating tool by explicit approval and ready gate.")
