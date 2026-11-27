"""Tool executor with policy and audit integration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
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
        isolated: bool = True,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.tools = tools or default_tools(self.workspace_root)
        self.policy = policy or ExecutionPolicy(allowed_tools={n for n, t in self.tools.items() if t.read_only})
        self.audit = audit_log
        self.isolated = isolated

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
        consume_approval: bool = True,
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
            tool_risk_class=spec.risk_class,
        )
        if not decision.allowed:
            self._audit("tool.denied", "denied", {"tool": tool_name, "reason": decision.reason, "arguments": args})
            return ToolExecutionResult(tool_name, False, False, None, decision.reason, decision.reason)

        self._audit("tool.allowed", "allowed", {"tool": tool_name, "reason": decision.reason, "risk_class": spec.risk_class})

        reserved = False
        if (not spec.read_only) and bool((approval or {}).get("approved", False)):
            try:
                reserved = self._reserve_approval(approval, tool_name=tool_name, risk_class=spec.risk_class)
                if reserved:
                    self._audit("plan.execution_approval_consumed", "reserved", {"plan_id": (approval or {}).get("plan_id"), "tool": tool_name})
            except Exception as exc:  # noqa: BLE001
                self._audit("tool.denied", "denied", {"tool": tool_name, "reason": f"approval reserve failed: {exc}"})
                return ToolExecutionResult(tool_name, False, False, None, str(exc), f"Approval reserve failed: {exc}")

        try:
            output = self._run_tool(spec, args)
        except TimeoutError as exc:
            self._finalize_approval(approval, tool_name=tool_name, risk_class=spec.risk_class, ok=False, reserved=reserved, error=str(exc))
            self._audit("tool.failed", "failed", {"tool": tool_name, "error": str(exc), "timeout_s": spec.timeout_s})
            return ToolExecutionResult(tool_name, True, False, None, str(exc), decision.reason)
        except Exception as exc:  # noqa: BLE001 - boundary for tool failures
            self._finalize_approval(approval, tool_name=tool_name, risk_class=spec.risk_class, ok=False, reserved=reserved, error=str(exc))
            self._audit("tool.failed", "failed", {"tool": tool_name, "error": str(exc)})
            return ToolExecutionResult(tool_name, True, False, None, str(exc), decision.reason)

        self._finalize_approval(approval, tool_name=tool_name, risk_class=spec.risk_class, ok=True, reserved=reserved, error=None)

        self._audit(
            "tool.executed",
            "ok",
            {
                "tool": tool_name,
                "output_keys": sorted(output.keys()),
                "risk_class": spec.risk_class,
                "approval_reserved": reserved,
                "approval_finalized": reserved,
            },
        )
        return ToolExecutionResult(tool_name, True, True, output, None, decision.reason)

    def _approval_store_path(self, approval: dict[str, Any] | None) -> Path | None:
        if not approval:
            return None
        plan_db = approval.get("plan_db_path")
        if plan_db:
            p = Path(str(plan_db))
            return p if p.exists() else None
        return None

    def _reserve_approval(self, approval: dict[str, Any] | None, *, tool_name: str, risk_class: str) -> bool:
        path = self._approval_store_path(approval)
        if not path or not approval:
            # No plan-db context: allow only non-mutating paths; mutating without durable approval is denied earlier.
            return False
        plan_id = approval.get("plan_id")
        approved_at = approval.get("approved_at")
        if not plan_id or not approved_at:
            raise ValueError("Approval missing plan_id/approved_at for mutating execution.")
        from digitalbrain.planning import SQLitePlanStore  # local import

        with SQLitePlanStore(path) as store:
            store.reserve_execution_approval(str(plan_id), approved_at=str(approved_at), tool_name=tool_name, risk_class=risk_class)
        return True

    def _finalize_approval(
        self,
        approval: dict[str, Any] | None,
        *,
        tool_name: str,
        risk_class: str,
        ok: bool,
        reserved: bool,
        error: str | None,
    ) -> None:
        if not reserved:
            return
        path = self._approval_store_path(approval)
        if not path or not approval:
            return
        plan_id = approval.get("plan_id")
        approved_at = approval.get("approved_at")
        if not plan_id or not approved_at:
            return
        from digitalbrain.planning import SQLitePlanStore  # local import

        try:
            with SQLitePlanStore(path) as store:
                store.finalize_execution_approval(
                    str(plan_id),
                    approved_at=str(approved_at),
                    tool_name=tool_name,
                    risk_class=risk_class,
                    ok=ok,
                    error=error,
                )
            self._audit(
                "plan.execution_approval_consumed",
                "executed" if ok else "failed",
                {"plan_id": plan_id, "tool": tool_name, "error": error},
            )
        except Exception as exc:  # noqa: BLE001
            self._audit(
                "plan.execution_approval_consumed",
                "finalize_failed",
                {"plan_id": plan_id, "tool": tool_name, "error": str(exc)},
            )

    def _run_tool(self, spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
        # Default: isolated subprocess for registry tools. Tests/custom in-memory handlers fall back to in-process.
        from digitalbrain.execution.tools import default_tools

        default_names = set(default_tools(self.workspace_root).keys())
        if self.isolated and spec.name in default_names:
            return self._run_in_subprocess(spec, args)

        # Fallback in-process timeout
        return self._run_in_process_with_timeout(spec, args)

    def _run_in_subprocess(self, spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
        payload = {"workspace": str(self.workspace_root), "tool_name": spec.name, "arguments": args}
        env = {"PYTHONPATH": str(Path(__file__).resolve().parents[2]), "PATH": os.environ.get("PATH", "")}
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "digitalbrain.execution.worker"],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=max(0.1, float(spec.timeout_s)),
                cwd=str(self.workspace_root),
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Tool '{spec.name}' timed out after {spec.timeout_s}s.") from exc

        stdout = (proc.stdout or "").strip()
        if not stdout:
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(f"Tool worker produced no output. rc={proc.returncode} stderr={stderr[:500]}")
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid tool worker output: {stdout[:500]}") from exc
        if not isinstance(data, dict):
            raise RuntimeError("Invalid tool worker output type.")
        if data.get("ok"):
            output = data.get("output")
            if not isinstance(output, dict):
                raise TypeError("Tool handler must return a dict.")
            return output
        raise RuntimeError(str(data.get("error") or "Tool failed."))

    @staticmethod
    def _run_in_process_with_timeout(spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
        from queue import Empty, Queue
        from threading import Thread

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
