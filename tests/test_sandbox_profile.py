"""Tests for hardened sandbox profile defaults."""
import os, tempfile, unittest
from pathlib import Path
from digitalbrain.execution.sandbox_policy import SandboxPolicyConfig

class HardenedProfileTests(unittest.TestCase):
    def test_hardened_profile_defaults(self):
        old = os.environ.copy()
        try:
            os.environ['DIGITALBRAIN_SANDBOX_PROFILE'] = 'hardened'
            for k in ['DIGITALBRAIN_SANDBOX_MODE','DIGITALBRAIN_REQUIRE_IMAGE_DIGEST','DIGITALBRAIN_REQUIRE_SECCOMP','DIGITALBRAIN_REQUIRE_APPARMOR','DIGITALBRAIN_SANDBOX_POLICY_REQUIRED']:
                os.environ.pop(k, None)
            cfg = SandboxPolicyConfig.from_env()
            self.assertEqual(cfg.mode, 'required')
            self.assertTrue(cfg.require_image_digest)
            self.assertTrue(cfg.require_seccomp)
            self.assertTrue(cfg.require_apparmor)
            self.assertTrue(cfg.enforce_central_policy)
        finally:
            os.environ.clear(); os.environ.update(old)

if __name__ == '__main__':
    unittest.main()
