"""Tests for image attestation verification."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from digitalbrain.execution import ToolExecutor
from digitalbrain.execution.attestation import verify_attestation_file
from digitalbrain.execution.sandbox_policy import SandboxPolicyConfig, sign_policy


class AttestationTests(unittest.TestCase):
    def test_attestation_file_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "att.json"
            payload = {"image_digest": "sha256:abc", "provenance": "test"}
            sig = sign_policy(payload, "s")
            p.write_text(json.dumps({**payload, "signature": sig}), encoding="utf-8")
            res = verify_attestation_file(p, image="python@sha256:abc", secret="s")
            self.assertTrue(res.ok)

    def test_executor_requires_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("x", encoding="utf-8")
            policy = SandboxPolicyConfig(require_attestation=True, attestation_path=str(Path(tmp) / "missing.json"))
            ex = ToolExecutor(workspace_root=root, sandbox_mode="container", container_image="python@sha256:abc", sandbox_policy=policy)
            with mock.patch("digitalbrain.execution.executor.ToolExecutor._docker_available", return_value=True):
                res = ex.execute("list_dir", {"path": "."})
            self.assertFalse(res.ok)
            self.assertIn("attestation", (res.error or "").lower())


if __name__ == "__main__":
    unittest.main()
