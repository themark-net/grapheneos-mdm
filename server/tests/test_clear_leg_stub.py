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
SCRIPT = ROOT / "scripts" / "emulator-policy-restriction.sh"
LIB = ROOT / "scripts" / "lib" / "clear-leg.sh"

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
            for key in (
                "DISALLOW_ADD_USER",
                "DISALLOW_FACTORY_RESET",
                "SERIAL",
                "ANDROID_SERIAL",
                "API_LEVEL",
                "CLEAR_LEG_STUB",
            ):
                env.pop(key, None)
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
            "FAIL: step clear: after-false device_policy dump lacks a DevicePolicyEngine section",
            proc.stderr,
        )
        self.assertNotIn("PASS:", proc.stdout)
        self.assertNotIn("PASS:", proc.stderr)

    def test_recognised_cleared_dump_is_accepted(self) -> None:
        proc = self._run(_CLEARED_POLICY, _CLEARED_USER)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PASS: clear leg accepted no_factory_reset", proc.stdout)
        self.assertIn("restriction no_factory_reset is not applied", proc.stdout)

    def test_dump_timeout_fails_the_clear_leg(self) -> None:
        timed = _CLEARED_POLICY + "*** SERVICE 'device_policy' DUMP TIMEOUT (10000ms) EXPIRED\n"
        proc = self._run(timed, _CLEARED_USER)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL: step clear: dumpsys contains *** SERVICE ... DUMP TIMEOUT", proc.stderr)
        self.assertNotIn("PASS:", proc.stdout)
        self.assertNotIn("PASS:", proc.stderr)
        self.assertNotIn("is not applied", proc.stdout)

    def test_missing_userinfo_fails_the_clear_leg(self) -> None:
        user = _CLEARED_USER.replace("UserInfo{0:Owner:c13} ", "Owner ")
        self.assertNotIn("UserInfo{", user)
        proc = self._run(_CLEARED_POLICY, user)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL: step clear: after-false dumpsys user lacks UserInfo{", proc.stderr)
        self.assertNotIn("PASS:", proc.stdout)

    def test_missing_restriction_header_fails_the_clear_leg(self) -> None:
        user = "Users:\n  UserInfo{0:Owner:c13} serialNo=0\n    Restrictions:\n      none\n"
        proc = self._run(_CLEARED_POLICY, user)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn(
            "FAIL: step clear: after-false dumpsys user lacks a restriction header",
            proc.stderr,
        )
        self.assertNotIn("PASS:", proc.stdout)

    def test_stub_refuses_when_serial_is_configured(self) -> None:
        accepted = self._run(_CLEARED_POLICY, _CLEARED_USER)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        for key, value in (("SERIAL", "emulator-5554"), ("ANDROID_SERIAL", "emulator-5554")):
            proc = self._run(_CLEARED_POLICY, _CLEARED_USER, {key: value})
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("FAIL: CLEAR_LEG_STUB refused because adb/SERIAL is configured", proc.stderr)
            self.assertNotIn("PASS:", proc.stdout)
            self.assertNotIn("set-device-owner", proc.stdout)
            self.assertNotIn("set-device-owner", proc.stderr)

    def test_api33_device_owner_marker_is_not_enough_on_api35(self) -> None:
        policy = "Device Owner:\n  admin=net.themark.grapheneosmdm\n"
        legacy = self._run(policy, _CLEARED_USER, {"API_LEVEL": "33"})
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        self.assertIn("PASS: clear leg accepted no_factory_reset", legacy.stdout)
        strict = self._run(policy, _CLEARED_USER, {"API_LEVEL": "35"})
        self.assertEqual(strict.returncode, 1, strict.stderr)
        self.assertIn(
            "FAIL: step clear: after-false device_policy dump lacks a DevicePolicyEngine section",
            strict.stderr,
        )
        self.assertNotIn("PASS:", strict.stdout)

    def test_restriction_step_names_a_dump_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = root / "device_policy.txt"
            user = root / "dumpsys_user.txt"
            policy.write_text(
                _CLEARED_POLICY + "*** SERVICE 'device_policy' DUMP TIMEOUT (10000ms) EXPIRED\n",
                encoding="utf-8",
            )
            user.write_text(_CLEARED_USER, encoding="utf-8")
            proc = subprocess.run(
                [
                    "bash",
                    "-c",
                    'set -euo pipefail; source "$1"; require_api_dumpsys restriction "$2" "$3" 35; echo UNEXPECTED',
                    "bash",
                    str(LIB),
                    str(policy),
                    str(user),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAIL: step restriction: dumpsys contains *** SERVICE ... DUMP TIMEOUT", proc.stderr)
        self.assertNotIn("UNEXPECTED", proc.stdout)

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
