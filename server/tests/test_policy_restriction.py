#!/usr/bin/env python3
"""dumpsys parsing for an applied user restriction.

A substring search for no_add_user treats no_add_user=false as applied and
fails the explicit-false case. A search for the shared prefix no_add treats
no_add_managed_profile as no_add_user and fails the sibling case.
No emulator. The CLI is the same one the operate script runs.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(SERVER_DIR / "policy_restriction.py")]

# Android 15 `dumpsys user`: headers at four spaces, keys at six.
# Only keys whose bundle value is true are printed, one per line.
_USER_EFFECTIVE = """\
Users:
  UserInfo{0:Owner:c13} serialNo=0 isPrimary=true
    Type: android.os.usertype.full.SYSTEM
    Flags: 13 (ADMIN|FULL|INITIALIZED)
    State: RUNNING_UNLOCKED
    Has profile owner: false
    Restrictions:
      none
    Device policy local restrictions:
      none
    Device policy global restrictions:
      none
    Effective restrictions:
      no_config_wifi
      no_add_user
    Ignore errors preparing storage: false
"""

_POLICY_OTHER = """\
DevicePolicyEngine:
  Local policies:
    User 0:
      UserRestrictionPolicyKey { mRestriction= no_config_wifi }
        Per-admin Policy:
          net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
            BooleanPolicyValue { mValue= true }
        Resolved Policy (MostRestrictive):
          BooleanPolicyValue { mValue= true }
"""

_USER_SIBLINGS = """\
Users:
  UserInfo{0:Owner:c13} serialNo=0 isPrimary=true
    Type: android.os.usertype.full.SYSTEM
    Has profile owner: false
    Restrictions:
      none
    Device policy local restrictions:
      no_add_managed_profile
      no_add_clone_profile
    Device policy global restrictions:
      none
    Effective restrictions:
      no_add_managed_profile
      no_add_clone_profile
      no_add_private_profile
"""

_POLICY_ENGINE_ADD_USER = """\
DevicePolicyEngine:
  Enabled admins:
    User 0:
      AdminInfo { package=net.themark.grapheneosmdm class=.receiver.DeviceAdminReceiver }
  Local policies:
    User 0:
      UserRestrictionPolicyKey { mRestriction= no_add_managed_profile }
        Per-admin Policy:
          net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
            BooleanPolicyValue { mValue= true }
        Resolved Policy (MostRestrictive):
          BooleanPolicyValue { mValue= true }
      UserRestrictionPolicyKey { mRestriction= no_add_user }
        Per-admin Policy:
          net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
            BooleanPolicyValue { mValue= true }
        Resolved Policy (MostRestrictive):
          BooleanPolicyValue { mValue= true }
      UserRestrictionPolicyKey { mRestriction= no_config_wifi }
        Per-admin Policy:
          net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
            BooleanPolicyValue { mValue= false }
        Resolved Policy (MostRestrictive):
          BooleanPolicyValue { mValue= false }
"""

_POLICY_SIBLINGS = """\
DevicePolicyEngine:
  Local policies:
    User 0:
      UserRestrictionPolicyKey { mRestriction= no_add_managed_profile }
        Per-admin Policy:
          net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
            BooleanPolicyValue { mValue= true }
        Resolved Policy (MostRestrictive):
          BooleanPolicyValue { mValue= true }
      UserRestrictionPolicyKey { mRestriction= no_add_clone_profile }
        Per-admin Policy:
          net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
            BooleanPolicyValue { mValue= true }
        Resolved Policy (MostRestrictive):
          BooleanPolicyValue { mValue= true }
  Legacy user restrictions:
    Bundle[{no_add_managed_profile=true, no_add_clone_profile=true, no_add_private_profile=true}]
"""

_USER_EXPLICIT_FALSE = """\
Users:
  UserInfo{0:Owner:c13} serialNo=0 isPrimary=true
    Has profile owner: false
    Restrictions:
      none
    Device policy global restrictions:
      none
    Device policy local restrictions:
      none
    Effective restrictions:
      no_config_wifi
      no_add_user=false
"""

_POLICY_EXPLICIT_FALSE = """\
DevicePolicyEngine:
  Local policies:
    User 0:
      UserRestrictionPolicyKey { mRestriction= no_config_wifi }
        Per-admin Policy:
          net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
            BooleanPolicyValue { mValue= true }
        Resolved Policy (MostRestrictive):
          BooleanPolicyValue { mValue= true }
      UserRestrictionPolicyKey { mRestriction= no_add_user }
        Per-admin Policy:
          net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
            BooleanPolicyValue { mValue= false }
        Resolved Policy (MostRestrictive):
          BooleanPolicyValue { mValue= false }
      UserRestrictionPolicyKey { mRestriction= no_install_unknown_sources }
        Per-admin Policy:
          net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
            BooleanPolicyValue { mValue= true }
        Resolved Policy (MostRestrictive):
          BooleanPolicyValue { mValue= true }
  Legacy user restrictions:
    Bundle[{no_add_user=false, no_config_wifi=true}]
"""


# Captured verbatim (trimmed) from AOSP ATD Android 15 (mdm36) on 2026-10-09,
# after a check-in with policyFlags.disallowAddUser=true. The key carries a
# "userRestriction_" prefix, so a word-boundary-only token match misses it.
_POLICY_ANDROID15_GLOBAL_TRUE = """\
  Local Policies: 
    User 0:
      UserRestrictionPolicyKey userRestriction_no_add_user
        Per-admin Policy:
          null
        Resolved Policy (MostRestrictive):
          null
      
  
  Global Policies: 
    UserRestrictionPolicyKey userRestriction_no_add_user
      Per-admin Policy:
        EnforcingAdmin { mPackageName= net.themark.grapheneosmdm, mAuthorities= [enterprise], mUserId= 0 }
          BooleanPolicyValue { mValue= true }
      Resolved Policy (MostRestrictive):
        BooleanPolicyValue { mValue= true }
    
  
  Default admin policy size limit: -1
"""

# Same shape, but the resolved value is null: per-admin true is not applied.
_POLICY_ANDROID15_RESOLVED_NULL = """\
  Global Policies: 
    UserRestrictionPolicyKey userRestriction_no_add_user
      Per-admin Policy:
        EnforcingAdmin { mPackageName= net.themark.grapheneosmdm, mUserId= 0 }
          BooleanPolicyValue { mValue= true }
      Resolved Policy (MostRestrictive):
        null
    
"""

_USER_NONE = """\
Users:
  UserInfo{0:Owner:c13} serialNo=0 isPrimary=true
    Restrictions:
      none
    Device policy restrictions:
      none
    Effective restrictions:
      no_add_private_profile
      no_add_managed_profile
      no_add_clone_profile
"""


class PolicyRestrictionTest(unittest.TestCase):
    def _run(self, device_policy: str, user_dump: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy_path = root / "device_policy.txt"
            user_path = root / "dumpsys_user.txt"
            policy_path.write_text(device_policy, encoding="utf-8")
            user_path.write_text(user_dump, encoding="utf-8")
            return subprocess.run(
                [
                    *CLI,
                    "--restriction",
                    "no_add_user",
                    "--device-policy",
                    str(policy_path),
                    "--user",
                    str(user_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_user_effective_block_is_applied(self) -> None:
        proc = self._run(_POLICY_OTHER, _USER_EFFECTIVE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(
            any(line.strip() == "no_add_user" for line in proc.stdout.splitlines()),
            proc.stdout,
        )

    def test_device_policy_engine_line_is_applied(self) -> None:
        proc = self._run(_POLICY_ENGINE_ADD_USER, _USER_SIBLINGS)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("UserRestrictionPolicyKey", proc.stdout)
        self.assertRegex(proc.stdout, r"(?<![A-Za-z0-9_])no_add_user(?![A-Za-z0-9_])")
        self.assertIn("mValue= true", proc.stdout)

    def test_sibling_profile_restrictions_are_not_add_user(self) -> None:
        proc = self._run(_POLICY_SIBLINGS, _USER_SIBLINGS)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout, "")

    def test_explicit_false_is_not_applied(self) -> None:
        proc = self._run(_POLICY_EXPLICIT_FALSE, _USER_EXPLICIT_FALSE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout, "")

    def test_empty_dumps_are_not_applied(self) -> None:
        proc = self._run("", "")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout, "")


    def test_android15_prefixed_policy_key_is_applied(self) -> None:
        proc = self._run(_POLICY_ANDROID15_GLOBAL_TRUE, _USER_NONE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("userRestriction_no_add_user", proc.stdout)

    def test_android15_resolved_null_is_not_applied(self) -> None:
        proc = self._run(_POLICY_ANDROID15_RESOLVED_NULL, _USER_NONE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout, "")

if __name__ == "__main__":
    unittest.main()
