"""Tests for deterministic sandbox policy validation CLI."""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

class ValidatePolicyCLITests(unittest.TestCase):
    def test_validate_sandbox_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'policy.json'
            p.write_text(json.dumps({"mode":"required","require_image_digest":True}), encoding='utf-8')
            cmd = [sys.executable, '-m', 'digitalbrain', '--validate-sandbox-policy', str(p)]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn('ok: true', proc.stdout.lower())

if __name__ == '__main__':
    unittest.main()
