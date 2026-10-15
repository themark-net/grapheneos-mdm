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
FIXTURES = Path(__file__).resolve().parent / "fixtures"
# Run 38441669873 artifact true/device_policy.txt and false/device_policy.txt.
# API 35 ATD. No DevicePolicyEngine line. No key material.
REAL_TRUE_POLICY = (FIXTURES / "api35-atd-true-device_policy.txt").read_text(encoding="utf-8")
REAL_FALSE_POLICY = (FIXTURES / "api35-atd-false-device_policy.txt").read_text(encoding="utf-8")
# The failed run never captured a factory-true dump. This is the real true
# capture with the token swapped, not a DevicePolicyEngine fixture.
FACTORY_TRUE_POLICY = REAL_TRUE_POLICY.replace("no_add_user", "no_factory_reset")

_SECTION_LINE = r"(?m)^[ \t]*(?:Local Policies:|Global Policies:)[ \t]*$"


def _section_mention_only(text: str) -> str:
    """Keep the dump, but the section names are no longer their own lines."""
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.strip() in {"Local Policies:", "Global Policies:"}:
            lines.append("note: see Local Policies: and Global Policies: below\n")
        else:
            lines.append(line)
    return "".join(lines)


def _drop_section_headers(text: str) -> str:
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if line.strip() not in {"Local Policies:", "Global Policies:"}
    )

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

_POLICY_SIBLINGS = """\
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


_USER_FACTORY = """\
Users:
  UserInfo{0:Owner:c13} serialNo=0 isPrimary=true
    Restrictions:
      none
    Device policy global restrictions:
      no_factory_reset
    Effective restrictions:
      no_factory_reset
"""

_USER_FACTORY_FALSE = """\
Users:
  UserInfo{0:Owner:c13} serialNo=0 isPrimary=true
    Restrictions:
      none
    Device policy global restrictions:
      none
    Effective restrictions:
      no_config_wifi
      no_factory_reset=false
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
    def _run(
        self,
        device_policy: str,
        user_dump: str,
        restriction: str = "no_add_user",
        api_level: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy_path = root / "device_policy.txt"
            user_path = root / "dumpsys_user.txt"
            policy_path.write_text(device_policy, encoding="utf-8")
            user_path.write_text(user_dump, encoding="utf-8")
            cmd = [
                *CLI,
                "--restriction",
                restriction,
                "--device-policy",
                str(policy_path),
                "--user",
                str(user_path),
            ]
            if api_level is not None:
                cmd.extend(["--api-level", str(api_level)])
            return subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )

    def _assert_not_applied(
        self,
        proc: subprocess.CompletedProcess[str],
        restriction: str = "no_add_user",
    ) -> None:
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertIn(f"restriction {restriction} is not applied", proc.stderr)

    def test_user_effective_block_is_applied(self) -> None:
        proc = self._run(REAL_FALSE_POLICY, _USER_EFFECTIVE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(
            any(line.strip() == "no_add_user" for line in proc.stdout.splitlines()),
            proc.stdout,
        )

    def test_device_policy_key_line_is_applied(self) -> None:
        proc = self._run(REAL_TRUE_POLICY, _USER_SIBLINGS)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("UserRestrictionPolicyKey", proc.stdout)
        self.assertIn("userRestriction_no_add_user", proc.stdout)
        self.assertIn("mValue= true", proc.stdout)

    def test_sibling_profile_restrictions_are_not_add_user(self) -> None:
        proc = self._run(_POLICY_SIBLINGS, _USER_SIBLINGS)
        self._assert_not_applied(proc)

    def test_explicit_false_is_not_applied(self) -> None:
        proc = self._run(_POLICY_EXPLICIT_FALSE, _USER_EXPLICIT_FALSE)
        self._assert_not_applied(proc)

    def test_empty_dumps_are_not_applied(self) -> None:
        proc = self._run("", "")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("dumpsys input is empty or unrecognised", proc.stderr)
        self.assertNotIn("is not applied", proc.stderr)

    def test_cutoff_dumpsys_without_a_marker_exits_2(self) -> None:
        proc = self._run(
            "DUMP OF SERVICE device_policy:\n",
            "DUMP OF SERVICE user:\n",
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("dumpsys input is empty or unrecognised", proc.stderr)
        self.assertNotIn("is not applied", proc.stderr)

    def test_whitespace_only_dumpsys_exits_2(self) -> None:
        proc = self._run(" \n\t", "\n")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("is not applied", proc.stderr)

    def test_cutoff_policy_with_user_header_is_still_exit_1(self) -> None:
        # The parser can see a user header and correctly say the token is
        # absent. The clear leg must still reject this: the device_policy
        # file has no anchored Local Policies or Global Policies line.
        # See test_clear_leg_stub.
        user = "Users:\n  UserInfo{0:Owner:c13} serialNo=0\n    Restrictions:\n      none\n"
        proc = self._run("DUMP OF SERVICE device_policy:\n", user)
        self._assert_not_applied(proc)


    def test_android15_prefixed_policy_key_is_applied(self) -> None:
        proc = self._run(REAL_TRUE_POLICY, _USER_NONE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("userRestriction_no_add_user", proc.stdout)

    def test_android15_resolved_null_is_not_applied(self) -> None:
        proc = self._run(REAL_FALSE_POLICY, _USER_NONE)
        self._assert_not_applied(proc)

    def test_android15_factory_reset_key_is_applied(self) -> None:
        self.assertNotIn("no_add_user", FACTORY_TRUE_POLICY)
        proc = self._run(FACTORY_TRUE_POLICY, _USER_FACTORY, "no_factory_reset")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("userRestriction_no_factory_reset", proc.stdout)
        self.assertTrue(
            any(line.strip() == "no_factory_reset" for line in proc.stdout.splitlines()),
            proc.stdout,
        )

    def test_factory_reset_explicit_false_names_the_clear_message(self) -> None:
        proc = self._run(REAL_FALSE_POLICY, _USER_FACTORY_FALSE, "no_factory_reset")
        self._assert_not_applied(proc, "no_factory_reset")

    def test_factory_reset_dump_is_not_add_user(self) -> None:
        proc = self._run(FACTORY_TRUE_POLICY, _USER_FACTORY, "no_add_user")
        self._assert_not_applied(proc, "no_add_user")

    def test_add_user_dump_is_not_factory_reset(self) -> None:
        proc = self._run(REAL_TRUE_POLICY, _USER_EFFECTIVE, "no_factory_reset")
        self._assert_not_applied(proc, "no_factory_reset")

    def test_usage_error_exits_3_and_empty_dumpsys_stays_2(self) -> None:
        usage = subprocess.run(CLI, check=False, capture_output=True, text=True)
        self.assertEqual(usage.returncode, 3, usage.stderr)
        self.assertNotIn("empty or unrecognised", usage.stderr)
        self.assertNotIn("is not applied", usage.stderr)
        self.assertIn("usage:", usage.stderr.lower())
        empty = self._run("", "")
        self.assertEqual(empty.returncode, 2, empty.stderr)
        self.assertIn("dumpsys input is empty or unrecognised", empty.stderr)
        self.assertNotIn("usage:", empty.stderr.lower())

    def test_api35_dump_timeout_is_not_applied_or_cleared(self) -> None:
        applied = self._run(REAL_TRUE_POLICY, _USER_EFFECTIVE, api_level=35)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertIn("no_add_user", applied.stdout)
        timed_policy = (
            REAL_TRUE_POLICY
            + "\n*** SERVICE 'device_policy' DUMP TIMEOUT (10000ms) EXPIRED\n"
        )
        timed = self._run(timed_policy, _USER_EFFECTIVE, api_level=35)
        self.assertEqual(timed.returncode, 2, timed.stderr)
        self.assertIn("*** SERVICE ... DUMP TIMEOUT", timed.stderr)
        self.assertNotIn("is not applied", timed.stderr)
        self.assertEqual(timed.stdout, "")

    def test_api35_names_each_missing_marker(self) -> None:
        recognised = self._run(
            REAL_FALSE_POLICY, _USER_FACTORY_FALSE, "no_add_user", api_level=35
        )
        self._assert_not_applied(recognised, "no_add_user")

        no_section = _drop_section_headers(REAL_FALSE_POLICY)
        self.assertNotIn("Local Policies:", no_section)
        self.assertNotIn("Global Policies:", no_section)
        missing_section = self._run(
            no_section, _USER_FACTORY_FALSE, "no_add_user", api_level=35
        )
        self.assertEqual(missing_section.returncode, 2, missing_section.stderr)
        self.assertIn("missing Local Policies or Global Policies section", missing_section.stderr)
        self.assertNotIn("is not applied", missing_section.stderr)

        no_userinfo = _USER_FACTORY_FALSE.replace("UserInfo{0:Owner:c13} ", "Owner ")
        missing_user = self._run(
            REAL_FALSE_POLICY, no_userinfo, "no_add_user", api_level=35
        )
        self.assertEqual(missing_user.returncode, 2, missing_user.stderr)
        self.assertIn("missing UserInfo{", missing_user.stderr)
        self.assertNotIn("is not applied", missing_user.stderr)

        no_header = "\n".join(
            line
            for line in _USER_FACTORY_FALSE.splitlines()
            if not line.strip().endswith("restrictions:")
            and not line.strip().endswith("Restrictions:")
        )
        self.assertIn("UserInfo{", no_header)
        self.assertNotIn("Effective restrictions:", no_header)
        missing_header = self._run(
            REAL_FALSE_POLICY, no_header, "no_add_user", api_level=35
        )
        self.assertEqual(missing_header.returncode, 2, missing_header.stderr)
        self.assertIn("missing restriction header", missing_header.stderr)
        self.assertNotIn("is not applied", missing_header.stderr)

    def test_anchored_section_rejects_a_midline_mention(self) -> None:
        # A plain substring check would see the words on the note line and
        # accept this dump. The real true capture is applied, so loosening
        # the anchor turns this assertion red (exit 0 instead of exit 2).
        self.assertNotIn("DevicePolicyEngine", REAL_TRUE_POLICY)
        applied = self._run(REAL_TRUE_POLICY, _USER_NONE, api_level=35)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        loosened = _section_mention_only(REAL_TRUE_POLICY)
        self.assertIn("Local Policies:", loosened)
        self.assertIn("Global Policies:", loosened)
        self.assertNotRegex(loosened, _SECTION_LINE)
        proc = self._run(loosened, _USER_NONE, api_level=35)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("missing Local Policies or Global Policies section", proc.stderr)
        self.assertNotIn("is not applied", proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
