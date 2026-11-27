"""Tests for centralized sandbox policy."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from digitalbrain.execution import ToolExecutor
from digitalbrain.execution.sandbox_policy import SandboxPolicyConfig, sign_policy


class SandboxPolicyTests(unittest.TestCase):
    def test_allowed_digest_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("x", encoding="utf-8")
            policy = SandboxPolicyConfig(require_image_digest=True, allowed_image_digests=("python@sha256:abc",))
            ex = ToolExecutor(workspace_root=root, sandbox_mode="container", container_image="python:3.12-slim", sandbox_policy=policy)
            with mock.patch("digitalbrain.execution.executor.ToolExecutor._docker_available", return_value=True):
                res = ex.execute("list_dir", {"path": "."})
            self.assertFalse(res.ok)
            self.assertIn("allowlist", (res.error or "").lower())

    def test_required_seccomp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = SandboxPolicyConfig(require_seccomp=True)
            ex = ToolExecutor(workspace_root=root, sandbox_mode="container", container_image="python@sha256:abc", sandbox_policy=policy)
            with mock.patch("digitalbrain.execution.executor.ToolExecutor._docker_available", return_value=True):
                res = ex.execute("list_dir", {"path": "."})
            self.assertFalse(res.ok)
            self.assertIn("seccomp", (res.error or "").lower())

    def test_signed_policy_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "policy.json"
            payload = {
                "mode": "required",
                "require_image_digest": True,
                "container_image": "python@sha256:abc",
                "allowed_image_digests": ["python@sha256:abc"],
                "enforce_central_policy": True,
            }
            sig = sign_policy(payload, "secret")
            p.write_text(json.dumps({**payload, "signature": sig}), encoding="utf-8")
            old = os.environ.copy()
            try:
                os.environ["DIGITALBRAIN_SANDBOX_POLICY_FILE"] = str(p)
                os.environ["DIGITALBRAIN_SANDBOX_POLICY_SECRET"] = "secret"
                cfg = SandboxPolicyConfig.from_env_and_file()
                self.assertEqual(cfg.mode, "required")
                self.assertTrue(cfg.require_image_digest)
            finally:
                os.environ.clear()
                os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
