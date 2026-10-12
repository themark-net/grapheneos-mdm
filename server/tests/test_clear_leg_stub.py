#!/usr/bin/env python3
"""Clear-leg gate with a fake dumpsys.

The operate script's true-then-false leg used to treat any "not applied"
exit as a clear. An empty or cut-off capture takes that path. These tests
point the script's clear-leg gate at that fake output and require FAIL.
No emulator.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "emulator-policy-disallow-add-user.sh"

# Recognised user header, but the device_policy file stops before the engine.
_CUTOFF_POLICY = "DUMP OF SERVICE device_policy:\n"
_CUTOFF_USER = """\
Users:
  UserInfo{0:Owner:c13} serialNo=0 isPrimary=true
    Restrictions:
      none
    Effective restrictions:
      no_config_wifi
"""

# A real clear: the engine section is present and the token is false.
_CLEARED_POLICY = """\
DevicePolicyEngine:
  Global Policies:
    UserRestrictionPolicyKey userRestriction_no_factory_reset
      Resolved Policy (MostRestrictive):
        BooleanPolicyValue { mValue= false }
"""
_CLEARED_USER = """\
Users:
  UserInfo{0:Owner:c13} serialNo=0 isPrimary=true
    Effective restrictions:
      no_config_wifi
"""


class ClearLegStubTest(unittest.TestCase):
    def _run(self, policy: str, user: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy_path = root / "device_policy.txt"
            user_path = root / "dumpsys_user.txt"
            policy_path.write_text(policy, encoding="utf-8")
            user_path.write_text(user, encoding="utf-8")
            env = os.environ.copy()
            env.pop("DISALLOW_ADD_USER", None)
            env.pop("DISALLOW_FACTORY_RESET", None)
            env.update(
                {
                    "CLEAR_LEG_STUB": "1",
                    "RESTRICTION": "disallowFactoryReset",
                    "DEVICE_POLICY_FILE": str(policy_path),
                    "USER_DUMP_FILE": str(user_path),
                    "OUT": str(root),
                }
            )
            if extra_env:
                env.update(extra_env)
            return subprocess.run(
                ["bash", str(SCRIPT)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

    def test_empty_dumpsys_fails_the_clear_leg(self) -> None:
        proc = self._run("", "")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL: step clear: after-false dumpsys is empty", proc.stderr)
        self.assertNotIn("PASS:", proc.stdout)
        self.assertNotIn("PASS:", proc.stderr)

    def test_cutoff_dumpsys_fails_the_clear_leg(self) -> None:
        proc = self._run(_CUTOFF_POLICY, _CUTOFF_USER)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn(
            "FAIL: step clear: after-false device_policy dump lacks DevicePolicyEngine, UserRestrictionPolicyKey, or Device Owner",
            proc.stderr,
        )
        self.assertNotIn("PASS:", proc.stdout)
        self.assertNotIn("PASS:", proc.stderr)

    def test_recognised_cleared_dump_is_accepted(self) -> None:
        proc = self._run(_CLEARED_POLICY, _CLEARED_USER)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PASS: clear leg accepted no_factory_reset", proc.stdout)
        self.assertIn("restriction no_factory_reset is not applied", proc.stdout)

    def test_other_mode_env_is_rejected(self) -> None:
        proc = self._run(
            _CLEARED_POLICY,
            _CLEARED_USER,
            {"DISALLOW_ADD_USER": "true", "DISALLOW_FACTORY_RESET": "true"},
        )
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("DISALLOW_ADD_USER must not be set when RESTRICTION=disallowFactoryReset", proc.stderr)
        self.assertNotIn("PASS:", proc.stdout)


if __name__ == "__main__":
    unittest.main()
