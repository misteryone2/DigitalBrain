"""Tool executor with policy and audit integration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import Any

from digitalbrain.core.audit import AuditLog
from digitalbrain.execution.policy import ExecutionPolicy
from digitalbrain.execution.tools import ToolSpec, default_tools


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    tool: str
    allowed: bool
    ok: bool
    output: dict[str, Any] | None
    error: str | None
    policy_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "allowed": self.allowed,
            "ok": self.ok,
            "output": self.output,
            "error": self.error,
            "policy_reason": self.policy_reason,
        }


class ToolExecutor:
    """Execute allowlisted read-only tools with audit events."""

    def __init__(
        self,
        *,
        workspace_root: str | Path,
        policy: ExecutionPolicy | None = None,
        audit_log: AuditLog | None = None,
        tools: dict[str, ToolSpec] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.tools = tools or default_tools(self.workspace_root)
        self.policy = policy or ExecutionPolicy(allowed_tools={n for n, t in self.tools.items() if t.read_only})
        self.audit = audit_log

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "read_only": t.read_only,
                "risk_class": t.risk_class,
                "timeout_s": t.timeout_s,
                "limits": dict(t.limits),
            }
            for t in self.tools.values()
        ]

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        execution_gate: dict[str, Any] | None = None,
        approval: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        args = dict(arguments or {})
        spec = self.tools.get(tool_name)
        self._audit(
            "tool.requested",
            "requested",
            {
                "tool": tool_name,
                "arguments": args,
                "execution_gate": execution_gate,
                "approved": bool((approval or {}).get("approved", False)),
                "risk_class": getattr(spec, "risk_class", None),
            },
        )
        if spec is None:
            self._audit("tool.denied", "denied", {"tool": tool_name, "reason": "unknown tool"})
            return ToolExecutionResult(tool_name, False, False, None, "Unknown tool.", "Unknown tool.")

        decision = self.policy.evaluate(
            tool_name,
            read_only=spec.read_only,
            execution_gate=execution_gate,
            approval=approval,
        )
        if not decision.allowed:
            self._audit("tool.denied", "denied", {"tool": tool_name, "reason": decision.reason, "arguments": args})
            return ToolExecutionResult(tool_name, False, False, None, decision.reason, decision.reason)

        self._audit("tool.allowed", "allowed", {"tool": tool_name, "reason": decision.reason, "risk_class": spec.risk_class})
        try:
            output = self._run_with_timeout(spec, args)
        except TimeoutError as exc:
            self._audit("tool.failed", "failed", {"tool": tool_name, "error": str(exc), "timeout_s": spec.timeout_s})
            return ToolExecutionResult(tool_name, True, False, None, str(exc), decision.reason)
        except Exception as exc:  # noqa: BLE001 - boundary for tool failures
            self._audit("tool.failed", "failed", {"tool": tool_name, "error": str(exc)})
            return ToolExecutionResult(tool_name, True, False, None, str(exc), decision.reason)

        self._audit("tool.executed", "ok", {"tool": tool_name, "output_keys": sorted(output.keys()), "risk_class": spec.risk_class})
        return ToolExecutionResult(tool_name, True, True, output, None, decision.reason)

    @staticmethod
    def _run_with_timeout(spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
        q: Queue[tuple[bool, Any]] = Queue(maxsize=1)

        def target() -> None:
            try:
                q.put((True, spec.handler(**args)))
            except Exception as exc:  # noqa: BLE001
                q.put((False, exc))

        thread = Thread(target=target, daemon=True, name=f"tool-{spec.name}")
        thread.start()
        thread.join(timeout=max(0.1, float(spec.timeout_s)))
        if thread.is_alive():
            raise TimeoutError(f"Tool '{spec.name}' timed out after {spec.timeout_s}s.")
        try:
            ok, payload = q.get_nowait()
        except Empty as exc:  # pragma: no cover
            raise RuntimeError(f"Tool '{spec.name}' finished without result.") from exc
        if ok:
            if not isinstance(payload, dict):
                raise TypeError("Tool handler must return a dict.")
            return payload
        raise payload

    def _audit(self, event_type: str, outcome: str, details: dict[str, Any]) -> None:
        if self.audit is not None:
            self.audit.record(event_type, actor="ToolExecutor", outcome=outcome, details=details)
