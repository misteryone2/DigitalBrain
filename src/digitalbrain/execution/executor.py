"""Tool executor with policy and audit integration."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from digitalbrain.core.audit import AuditLog
from digitalbrain.execution import winjob
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
        sandbox_mode: str = "host",
        container_image: str = "python:3.12-slim",
        container_seccomp: str | None = None,
        container_apparmor: str | None = None,
        require_image_digest: bool = False,
        host_job_limits: bool = True,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.tools = tools or default_tools(self.workspace_root)
        self.policy = policy or ExecutionPolicy(allowed_tools=set(self.tools.keys()))
        self.audit = audit_log
        self.isolated = isolated
        self.sandbox_mode = sandbox_mode
        self.container_image = container_image
        self.container_seccomp = container_seccomp
        self.container_apparmor = container_apparmor
        self.require_image_digest = require_image_digest
        self.host_job_limits = host_job_limits

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
        sandbox_mode = "unknown"
        if spec is not None and self.isolated and spec.name in set(default_tools(self.workspace_root).keys()):
            try:
                sandbox_mode = self._resolve_sandbox_mode()
            except Exception:
                sandbox_mode = "unavailable"
        elif spec is not None:
            sandbox_mode = "in_process"
        self._audit(
            "tool.requested",
            "requested",
            {
                "tool": tool_name,
                "arguments": args,
                "execution_gate": execution_gate,
                "approved": bool((approval or {}).get("approved", False)),
                "risk_class": getattr(spec, "risk_class", None),
                "sandbox_mode": sandbox_mode,
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
            sandbox_mode=sandbox_mode,
        )
        if not decision.allowed:
            self._audit("tool.denied", "denied", {"tool": tool_name, "reason": decision.reason, "arguments": args})
            return ToolExecutionResult(tool_name, False, False, None, decision.reason, decision.reason)

        self._audit("tool.allowed", "allowed", {"tool": tool_name, "reason": decision.reason, "risk_class": spec.risk_class, "sandbox_mode": sandbox_mode})

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
            output = self._run_tool(spec, args, sandbox_mode=sandbox_mode)
        except TimeoutError as exc:
            self._finalize_approval(approval, tool_name=tool_name, risk_class=spec.risk_class, ok=False, reserved=reserved, error=str(exc))
            self._audit("tool.failed", "failed", {"tool": tool_name, "error": str(exc), "timeout_s": spec.timeout_s, "sandbox_mode": sandbox_mode})
            return ToolExecutionResult(tool_name, True, False, None, str(exc), decision.reason)
        except Exception as exc:  # noqa: BLE001 - boundary for tool failures
            self._finalize_approval(approval, tool_name=tool_name, risk_class=spec.risk_class, ok=False, reserved=reserved, error=str(exc))
            self._audit("tool.failed", "failed", {"tool": tool_name, "error": str(exc), "sandbox_mode": sandbox_mode})
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
                "sandbox_mode": sandbox_mode,
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
            raise ValueError("Mutating execution requires durable plan approval context (plan_db_path/plan_id/approved_at).")
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

    def _run_tool(self, spec: ToolSpec, args: dict[str, Any], *, sandbox_mode: str | None = None) -> dict[str, Any]:
        # Default: isolated subprocess for registry tools. Tests/custom in-memory handlers fall back to in-process.
        from digitalbrain.execution.tools import default_tools

        default_names = set(default_tools(self.workspace_root).keys())
        if self.isolated and spec.name in default_names:
            mode = sandbox_mode or self._resolve_sandbox_mode()
            if mode == "container":
                return self._run_in_container(spec, args)
            return self._run_in_host_process(spec, args)

        # Fallback in-process timeout
        return self._run_in_process_with_timeout(spec, args)

    def _resolve_sandbox_mode(self) -> str:
        mode = (self.sandbox_mode or "auto").lower()
        if mode == "host":
            return "host"
        if mode in {"container", "required"}:
            if not self._docker_available():
                raise RuntimeError(f"Sandbox mode '{mode}' requested but Docker is unavailable.")
            return "container"
        if mode == "auto":
            return "container" if self._docker_available() else "host"
        raise ValueError(f"Unsupported sandbox mode: {self.sandbox_mode}")

    @staticmethod
    def _docker_available() -> bool:
        exe = shutil.which("docker")
        if not exe:
            return False
        try:
            proc = subprocess.run([exe, "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True, timeout=3, check=False)
        except Exception:
            return False
        return proc.returncode == 0

    def _run_in_host_process(self, spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
        payload = {"workspace": str(self.workspace_root), "tool_name": spec.name, "arguments": args}
        src_path = str(Path(__file__).resolve().parents[2])
        env = {
            "PYTHONPATH": src_path,
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
        }
        max_output_bytes = int(spec.limits.get("max_output_bytes", 262144))
        max_memory_bytes = int(spec.limits.get("max_memory_bytes", 256 * 1024 * 1024))
        max_processes = int(spec.limits.get("max_processes", 16))
        job = None
        with tempfile.TemporaryFile(mode="w+b") as stdout_f, tempfile.TemporaryFile(mode="w+b") as stderr_f:
            cmd = [sys.executable, "-I", "-m", "digitalbrain.execution.worker"]
            creationflags = 0
            start_new_session = False
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            else:
                start_new_session = True
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=stdout_f,
                stderr=stderr_f,
                text=False,
                cwd=str(self.workspace_root),
                env=env,
                creationflags=creationflags,
                start_new_session=start_new_session,
            )
            if os.name == "nt" and self.host_job_limits:
                job = winjob.create_job(name=f"digitalbrain-tool-{spec.name}-{uuid.uuid4().hex[:8]}", max_memory_bytes=max_memory_bytes, max_processes=max_processes)
                if job is not None:
                    # _handle is available on Windows subprocess.Popen
                    handle = int(getattr(proc, "_handle", 0) or 0)
                    if handle:
                        winjob.assign_process(job, handle)
            try:
                proc.communicate(input=json.dumps(payload).encode("utf-8"), timeout=max(0.1, float(spec.timeout_s)))
            except subprocess.TimeoutExpired as exc:
                self._kill_process_tree(proc)
                raise TimeoutError(f"Tool '{spec.name}' timed out after {spec.timeout_s}s.") from exc
            finally:
                winjob.close_job(job)

            stdout_f.seek(0)
            stderr_f.seek(0)
            stdout_bytes = stdout_f.read(max_output_bytes + 1)
            stderr_bytes = stderr_f.read(65536)

        return self._parse_worker_output(spec, stdout_bytes, stderr_bytes, proc.returncode, max_output_bytes)

    def _run_in_container(self, spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
        payload = {"workspace": "/workspace", "tool_name": spec.name, "arguments": args}
        max_output_bytes = int(spec.limits.get("max_output_bytes", 262144))
        docker = shutil.which("docker")
        if not docker:
            raise RuntimeError("Docker is unavailable.")
        self._validate_container_image(self.container_image)

        src_path = Path(__file__).resolve().parents[2]
        cmd = [
            docker, "run", "--rm", "-i",
            "--network", "none",
            "--read-only",
            "--cpus", "1.0",
            "--memory", "512m",
            "--pids-limit", "128",
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", f"{self.workspace_root}:/workspace:rw",
            "-v", f"{src_path}:/opt/digitalbrain-src:ro",
            "-w", "/workspace",
            "-e", "PYTHONPATH=/opt/digitalbrain-src",
            self.container_image,
            "python", "-I", "-m", "digitalbrain.execution.worker",
        ]
        container_name = f"db-tool-{uuid.uuid4().hex[:12]}"
        cmd[3:3] = ["--name", container_name]
        security_opts = ["no-new-privileges"]
        if self.container_seccomp:
            security_opts.append(f"seccomp={self.container_seccomp}")
        if self.container_apparmor:
            security_opts.append(f"apparmor={self.container_apparmor}")
        # replace default security-opt no-new-privileges with configured set
        new_cmd: list[str] = []
        skip_next = False
        for i, part in enumerate(cmd):
            if skip_next:
                skip_next = False
                continue
            if part == "--security-opt":
                skip_next = True
                continue
            new_cmd.append(part)
        insert_at = new_cmd.index("--cap-drop")
        sec_args: list[str] = []
        for opt in security_opts:
            sec_args.extend(["--security-opt", opt])
        cmd = new_cmd[:insert_at] + sec_args + new_cmd[insert_at:]

        manifest = {
            "mode": "container",
            "image": self.container_image,
            "network": "none",
            "read_only": True,
            "cpus": "1.0",
            "memory": "512m",
            "pids_limit": 128,
            "no_new_privileges": True,
            "cap_drop": ["ALL"],
            "tmpfs": "/tmp:rw,noexec,nosuid,size=64m",
            "seccomp": self.container_seccomp,
            "apparmor": self.container_apparmor,
            "workspace_mount": f"{self.workspace_root}:/workspace:rw",
            "src_mount": f"{src_path}:/opt/digitalbrain-src:ro",
        }
        self._audit("tool.sandbox_manifest", "configured", {"tool": spec.name, **manifest})

        with tempfile.TemporaryFile(mode="w+b") as stdout_f, tempfile.TemporaryFile(mode="w+b") as stderr_f:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=stdout_f, stderr=stderr_f, text=False)
            try:
                proc.communicate(input=json.dumps(payload).encode("utf-8"), timeout=max(0.1, float(spec.timeout_s)))
            except subprocess.TimeoutExpired as exc:
                subprocess.run([docker, "kill", container_name], capture_output=True, text=True, check=False)
                try:
                    proc.communicate(timeout=2)
                except Exception:
                    pass
                raise TimeoutError(f"Tool '{spec.name}' timed out after {spec.timeout_s}s.") from exc

            stdout_f.seek(0)
            stderr_f.seek(0)
            stdout_bytes = stdout_f.read(max_output_bytes + 1)
            stderr_bytes = stderr_f.read(65536)

        return self._parse_worker_output(spec, stdout_bytes, stderr_bytes, proc.returncode, max_output_bytes)

    def _validate_container_image(self, image: str) -> None:
        img = (image or "").strip()
        if not img:
            raise ValueError("Container image must not be empty.")
        if self.require_image_digest and "@sha256:" not in img:
            raise ValueError("Container image must be pinned by digest when require_image_digest is enabled.")

    @staticmethod
    def _parse_worker_output(spec: ToolSpec, stdout_bytes: bytes, stderr_bytes: bytes, returncode: int, max_output_bytes: int) -> dict[str, Any]:
        if len(stdout_bytes) > max_output_bytes:
            raise RuntimeError(f"Tool '{spec.name}' output exceeded {max_output_bytes} bytes.")
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        if not stdout:
            raise RuntimeError(f"Tool worker produced no output. rc={returncode} stderr={stderr[:500]}")
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
    def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, text=True, check=False)
            else:
                os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass

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
