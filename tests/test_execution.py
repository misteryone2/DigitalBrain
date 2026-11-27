import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from digitalbrain.core.audit import AuditLog
from digitalbrain.execution import ExecutionPolicy, ToolExecutor
from digitalbrain.execution.tools import default_tools


class TestExecution(unittest.TestCase):
    def test_list_dir_read_file_grep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("hello world\nalpha\n", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.txt").write_text("world\nbeta\n", encoding="utf-8")
            ex = ToolExecutor(workspace_root=root)

            listed = ex.execute("list_dir", {"path": "."})
            self.assertTrue(listed.ok)
            names = {e["name"] for e in listed.output["entries"]}
            self.assertIn("a.txt", names)
            self.assertIn("sub", names)

            read = ex.execute("read_file", {"path": "a.txt"})
            self.assertTrue(read.ok)
            self.assertIn("hello world", read.output["content"])

            grep = ex.execute("grep", {"pattern": "world", "path": "."})
            self.assertTrue(grep.ok)
            self.assertEqual(grep.output["count"], 2)

    def test_path_boundary_blocks_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            root.mkdir()
            outside = Path(tmp) / "secret.txt"
            outside.write_text("secret", encoding="utf-8")
            ex = ToolExecutor(workspace_root=root)
            res = ex.execute("read_file", {"path": str(outside)})
            self.assertFalse(res.ok)
            self.assertIn("outside allowed workspace", res.error or "")

    def test_policy_denies_unknown_and_non_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ex = ToolExecutor(workspace_root=tmp, policy=ExecutionPolicy(allowed_tools={"list_dir"}))
            denied = ex.execute("read_file", {"path": "."})
            self.assertFalse(denied.ok)
            self.assertFalse(denied.allowed)
            unknown = ex.execute("nope", {})
            self.assertFalse(unknown.allowed)

    def test_audit_events_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "f.txt").write_text("x", encoding="utf-8")
            audit_db = root / "audit.db"
            with AuditLog(audit_db) as audit:
                ex = ToolExecutor(workspace_root=root, audit_log=audit)
                ex.execute("read_file", {"path": "f.txt"})
                ex.execute("unknown", {})
                events = audit.list_events(limit=20)
            types = [e.event_type for e in events]
            self.assertIn("tool.requested", types)
            self.assertIn("tool.allowed", types)
            self.assertIn("tool.executed", types)
            self.assertIn("tool.denied", types)

    def test_needs_review_gate_allows_readonly_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "f.txt").write_text("ok", encoding="utf-8")
            ex = ToolExecutor(workspace_root=root)
            res = ex.execute("read_file", {"path": "f.txt"}, execution_gate={"status": "needs_review"})
            self.assertTrue(res.ok)
            self.assertIn("needs review", res.policy_reason.lower())

    def test_mutating_tool_denied_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ex = ToolExecutor(workspace_root=tmp)
            res = ex.execute("write_file", {"path": "x.txt", "content": "hi"})
            self.assertFalse(res.ok)
            self.assertFalse(res.allowed)
            self.assertIn("mutating", res.policy_reason.lower())

    def test_mutating_tool_requires_ready_gate_and_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            all_tools = default_tools(root)
            policy = ExecutionPolicy(allowed_tools=set(all_tools.keys()), allow_mutating=True)
            ex = ToolExecutor(workspace_root=root, policy=policy, tools=all_tools, sandbox_mode="host")

            denied_gate = ex.execute(
                "write_file",
                {"path": "x.txt", "content": "hi", "overwrite": True},
                execution_gate={"status": "needs_review"},
                approval={"approved": True},
            )
            self.assertFalse(denied_gate.ok)
            self.assertIn("gate", denied_gate.policy_reason.lower())

            denied_approval = ex.execute(
                "write_file",
                {"path": "x.txt", "content": "hi", "overwrite": True},
                execution_gate={"status": "ready"},
                approval={"approved": False},
            )
            self.assertFalse(denied_approval.ok)
            self.assertIn("approval", denied_approval.policy_reason.lower())

            denied_scope = ex.execute(
                "write_file",
                {"path": "x.txt", "content": "hi", "overwrite": True},
                execution_gate={"status": "ready"},
                approval={"approved": True, "tool_name": "other_tool"},
            )
            self.assertFalse(denied_scope.ok)
            self.assertIn("scoped", denied_scope.policy_reason.lower())

            # Mutating tools require container sandbox
            denied_sandbox = ex.execute(
                "write_file",
                {"path": "x.txt", "content": "hi", "overwrite": True},
                execution_gate={"status": "ready"},
                approval={"approved": True, "tool_name": "write_file", "risk_class": "low"},
            )
            self.assertFalse(denied_sandbox.allowed)
            self.assertIn("container sandbox required", denied_sandbox.policy_reason.lower())

    def test_mutating_tool_denied_on_risk_mismatch_or_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            all_tools = default_tools(root)
            policy = ExecutionPolicy(allowed_tools=set(all_tools.keys()), allow_mutating=True)
            ex = ToolExecutor(workspace_root=root, policy=policy, tools=all_tools, sandbox_mode="container")
            with mock.patch("digitalbrain.execution.executor.ToolExecutor._docker_available", return_value=True):
                denied_risk = ex.execute(
                    "write_file",
                    {"path": "x.txt", "content": "hi", "overwrite": True},
                    execution_gate={"status": "ready"},
                    approval={"approved": True, "tool_name": "write_file", "risk_class": "high"},
                )
                self.assertFalse(denied_risk.ok)
                self.assertIn("risk class", denied_risk.policy_reason.lower())

                denied_consumed = ex.execute(
                    "write_file",
                    {"path": "y.txt", "content": "hi", "overwrite": True},
                    execution_gate={"status": "ready"},
                    approval={"approved": True, "tool_name": "write_file", "risk_class": "low", "consumed_at": "2026-01-01T00:00:00Z"},
                )
                self.assertFalse(denied_consumed.ok)
                self.assertIn("consumed", denied_consumed.policy_reason.lower())

                denied_expired = ex.execute(
                    "write_file",
                    {"path": "z.txt", "content": "hi", "overwrite": True},
                    execution_gate={"status": "ready"},
                    approval={"approved": True, "tool_name": "write_file", "risk_class": "low", "expires_at": "2000-01-01T00:00:00+00:00"},
                )
                self.assertFalse(denied_expired.ok)
                self.assertIn("expired", denied_expired.policy_reason.lower())

    def test_mutating_tool_reserves_and_finalizes_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_db = root / "plans.db"
            from digitalbrain.planning import SQLitePlanStore

            with SQLitePlanStore(plan_db) as store:
                plan = store.save_plan(
                    goal="Write",
                    status="accepted",
                    steps=[{"id": "step-1", "title": "Write", "status": "pending"}],
                    source="test",
                    metadata={"execution_gate": {"status": "ready", "executable": True, "reasons": []}},
                )
                approved = store.approve_execution(plan.id, reason="ok", tool_name="write_file", risk_class="low")
                approval = dict(approved.metadata["execution_approval"])
                approval["plan_db_path"] = str(plan_db)

            all_tools = default_tools(root)
            policy = ExecutionPolicy(allowed_tools=set(all_tools.keys()), allow_mutating=True)
            ex = ToolExecutor(workspace_root=root, policy=policy, tools=all_tools, isolated=True, sandbox_mode="container")
            fake_proc = mock.Mock()
            fake_proc.returncode = 0
            fake_proc.communicate.return_value = None

            def fake_popen(cmd, **kwargs):
                # Simulate container worker success and perform local write to reflect side effect in this unit test.
                Path(root / "x.txt").write_text("hi", encoding="utf-8")
                stdout_f = kwargs["stdout"]
                stdout_f.write(b'{"ok": true, "output": {"path":"x.txt","chars":2}}')
                stdout_f.flush()
                return fake_proc

            with mock.patch("digitalbrain.execution.executor.shutil.which", return_value="/usr/bin/docker"), \
                 mock.patch("digitalbrain.execution.executor.subprocess.run", return_value=mock.Mock(returncode=0)), \
                 mock.patch("digitalbrain.execution.executor.subprocess.Popen", side_effect=fake_popen):
                ok = ex.execute(
                    "write_file",
                    {"path": "x.txt", "content": "hi", "overwrite": True},
                    execution_gate={"status": "ready"},
                    approval=approval,
                )
                self.assertTrue(ok.ok)
                with SQLitePlanStore(plan_db) as store:
                    rec = store.get(plan.id)
                    assert rec is not None
                    self.assertEqual(rec.metadata["execution_approval"]["execution_state"], "executed")

                # Single-use: second execution denied
                ok2 = ex.execute(
                    "write_file",
                    {"path": "y.txt", "content": "hi", "overwrite": True},
                    execution_gate={"status": "ready"},
                    approval=approval,
                )
                self.assertFalse(ok2.ok)

    def test_mkdir_mutating_tool_with_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_db = root / "plans.db"
            from digitalbrain.planning import SQLitePlanStore
            with SQLitePlanStore(plan_db) as store:
                plan = store.save_plan(
                    goal="Mkdir",
                    status="accepted",
                    steps=[{"id": "step-1", "title": "Mkdir", "status": "pending"}],
                    source="test",
                    metadata={"execution_gate": {"status": "ready", "executable": True, "reasons": []}},
                )
                approved = store.approve_execution(plan.id, reason="ok", tool_name="mkdir", risk_class="low")
                approval = dict(approved.metadata["execution_approval"])
                approval["plan_db_path"] = str(plan_db)

            all_tools = default_tools(root)
            policy = ExecutionPolicy(allowed_tools=set(all_tools.keys()), allow_mutating=True)
            ex = ToolExecutor(workspace_root=root, policy=policy, tools=all_tools, isolated=True, sandbox_mode="container")
            fake_proc = mock.Mock()
            fake_proc.returncode = 0
            fake_proc.communicate.return_value = None

            def fake_popen(cmd, **kwargs):
                (root / "newdir").mkdir(exist_ok=True)
                stdout_f = kwargs["stdout"]
                stdout_f.write(b'{"ok": true, "output": {"path":"newdir","created":true}}')
                stdout_f.flush()
                return fake_proc

            with mock.patch("digitalbrain.execution.executor.shutil.which", return_value="/usr/bin/docker"), \
                 mock.patch("digitalbrain.execution.executor.subprocess.run", return_value=mock.Mock(returncode=0)), \
                 mock.patch("digitalbrain.execution.executor.subprocess.Popen", side_effect=fake_popen):
                res = ex.execute("mkdir", {"path": "newdir"}, execution_gate={"status": "ready"}, approval=approval)
            self.assertTrue(res.ok)
            self.assertTrue((root / "newdir").is_dir())

    def test_tool_timeout_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from digitalbrain.execution.tools import ToolSpec
            ex = ToolExecutor(
                workspace_root=tmp,
                isolated=False,  # custom handler; timeout via in-process fallback
                tools={
                    "slow": ToolSpec(
                        name="slow",
                        description="slow",
                        read_only=True,
                        risk_class="none",
                        timeout_s=0.01,
                        handler=lambda: __import__("time").sleep(0.2) or {"ok": True},
                    )
                },
            )
            res = ex.execute("slow", {})
            self.assertFalse(res.ok)
            self.assertIn("timed out", (res.error or "").lower())

    def test_container_mode_builds_docker_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("ok", encoding="utf-8")
            ex = ToolExecutor(workspace_root=root, sandbox_mode="container")
            fake_proc = mock.Mock()
            fake_proc.returncode = 0
            fake_proc.communicate.return_value = None

            def fake_popen(cmd, **kwargs):
                # simulate worker writing stdout file
                stdout_f = kwargs["stdout"]
                stdout_f.write(b'{"ok": true, "output": {"content":"ok"}}')
                stdout_f.flush()
                return fake_proc

            with mock.patch("digitalbrain.execution.executor.shutil.which", return_value="/usr/bin/docker"), \
                 mock.patch("digitalbrain.execution.executor.subprocess.run", return_value=mock.Mock(returncode=0)), \
                 mock.patch("digitalbrain.execution.executor.subprocess.Popen", side_effect=fake_popen) as popen:
                res = ex.execute("read_file", {"path": "a.txt"})
            self.assertTrue(res.ok)
            cmd = popen.call_args.args[0]
            self.assertIn("--network", cmd)
            self.assertIn("none", cmd)
            self.assertIn("--read-only", cmd)

    def test_container_mode_unavailable_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ex = ToolExecutor(workspace_root=tmp, sandbox_mode="container")
            with mock.patch("digitalbrain.execution.executor.shutil.which", return_value=None):
                res = ex.execute("list_dir", {"path": "."})
            self.assertFalse(res.ok)
            self.assertIn("docker", (res.error or "").lower())

    def test_required_mode_requires_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ex = ToolExecutor(workspace_root=tmp, sandbox_mode="required")
            with mock.patch("digitalbrain.execution.executor.shutil.which", return_value=None):
                res = ex.execute("list_dir", {"path": "."})
            self.assertFalse(res.ok)
            self.assertIn("docker", (res.error or "").lower())

    def test_container_image_digest_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ex = ToolExecutor(workspace_root=tmp, sandbox_mode="container", container_image="python:3.12-slim", require_image_digest=True)
            with mock.patch("digitalbrain.execution.executor.ToolExecutor._docker_available", return_value=True):
                res = ex.execute("list_dir", {"path": "."})
            self.assertFalse(res.ok)
            self.assertIn("digest", (res.error or "").lower())

    def test_container_manifest_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("ok", encoding="utf-8")
            audit_db = root / "audit.db"
            with AuditLog(audit_db) as audit:
                ex = ToolExecutor(workspace_root=root, sandbox_mode="container", audit_log=audit, container_seccomp="default.json")
                fake_proc = mock.Mock()
                fake_proc.returncode = 0
                fake_proc.communicate.return_value = None

                def fake_popen(cmd, **kwargs):
                    stdout_f = kwargs["stdout"]
                    stdout_f.write(b'{"ok": true, "output": {"content":"ok"}}')
                    stdout_f.flush()
                    return fake_proc

                with mock.patch("digitalbrain.execution.executor.shutil.which", return_value="/usr/bin/docker"), \
                     mock.patch("digitalbrain.execution.executor.subprocess.run", return_value=mock.Mock(returncode=0)), \
                     mock.patch("digitalbrain.execution.executor.subprocess.Popen", side_effect=fake_popen):
                    res = ex.execute("read_file", {"path": "a.txt"})
                self.assertTrue(res.ok)
                events = audit.list_events(limit=50)
            manifest = [e for e in events if e.event_type == "tool.sandbox_manifest"]
            self.assertTrue(manifest)
            self.assertEqual(manifest[0].details.get("seccomp"), "default.json")


if __name__ == "__main__":
    unittest.main()
