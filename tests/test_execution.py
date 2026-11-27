import json
import tempfile
import unittest
from pathlib import Path

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
            ex = ToolExecutor(workspace_root=root, policy=policy, tools=all_tools)

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

            ok = ex.execute(
                "write_file",
                {"path": "x.txt", "content": "hi", "overwrite": True},
                execution_gate={"status": "ready"},
                approval={"approved": True, "tool_name": "write_file"},
            )
            self.assertTrue(ok.ok)
            self.assertEqual((root / "x.txt").read_text(encoding="utf-8"), "hi")

    def test_tool_timeout_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from digitalbrain.execution.tools import ToolSpec
            ex = ToolExecutor(
                workspace_root=tmp,
                tools={
                    "slow": ToolSpec(
                        name="slow",
                        description="slow",
                        read_only=True,
                        risk_class="none",
                        timeout_s=0.01,
                        handler=lambda: __import__("time").sleep(0.1) or {"ok": True},
                    )
                },
            )
            res = ex.execute("slow", {})
            self.assertFalse(res.ok)
            self.assertIn("timed out", (res.error or "").lower())


if __name__ == "__main__":
    unittest.main()
