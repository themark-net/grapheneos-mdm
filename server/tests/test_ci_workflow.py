#!/usr/bin/env python3
"""CI path filters, Node 24 pins, and one-shot ASSERT lines.

A rename that leaves the old script name in a workflow is an orphan filter:
the emulator job would not run for the new file. A Node 20 pin is the
deprecation this phase removes. Re-printing the summary duplicates every
ASSERT line. No emulator.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
# Split so this file does not contain the retired filename as one string.
OLD_SCRIPT = "emulator-policy-disallow-" + "add-user.sh"
NEW_SCRIPT = "scripts/emulator-policy-restriction.sh"

# Pins that still declare runs.using: node20.
_NODE20 = (
    "actions/checkout@v4",
    "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
    "actions/setup-java@v4",
    "actions/setup-java@cf277c60eb25467037889841efdb72551f06f6c3",
    "actions/setup-python@v5",
    "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/upload-artifact@v4",
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    "gradle/actions/setup-gradle@v4",
    "gradle/actions/setup-gradle@ed408507eac070d1f99cc633dbcf757c94c7933a",
)

# Current node24 releases. The emulator-runner pin was already node24.
_NODE24 = (
    "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
    "actions/setup-java@de7274f081f381c8f8158605e0321c36c376e2e6 # v6.0.1",
    "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0",
    "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2",
    "gradle/actions/setup-gradle@3f5f9adaf7d9fecd50b5935e54106014257a94e6 # v6.4.0",
    "android-actions/setup-android@be39fa834029ff78f1a44aa3bb0819b8fc2bd8fd # v4.0.4",
    "reactivecircus/android-emulator-runner@a421e43855164a8197daf9d8d40fe71c6996bb0d # v2.38.0",
)


class CiWorkflowTest(unittest.TestCase):
    def test_operate_script_name_has_no_orphan_reference(self) -> None:
        self.assertTrue((ROOT / NEW_SCRIPT).is_file())
        self.assertFalse((ROOT / "scripts" / OLD_SCRIPT).exists())
        leftovers = []
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or ".project-map" in path.parts:
                continue
            if path.suffix not in {".yml", ".yaml", ".sh", ".py", ".md", ".kts"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if OLD_SCRIPT in text:
                leftovers.append(str(path.relative_to(ROOT)))
        self.assertEqual(leftovers, [])
        workflow = (WORKFLOWS / "emulator-policy.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count(f"- {NEW_SCRIPT}"), 2)
        self.assertEqual(workflow.count("- scripts/lib/**"), 2)
        wrapper = (ROOT / "scripts" / "ci-emulator-policy.sh").read_text(encoding="utf-8")
        self.assertIn(NEW_SCRIPT, wrapper)

    def test_workflows_pin_node24_actions(self) -> None:
        blobs = [
            (WORKFLOWS / "ci.yml").read_text(encoding="utf-8"),
            (WORKFLOWS / "emulator-policy.yml").read_text(encoding="utf-8"),
        ]
        combined = "\n".join(blobs)
        for pin in _NODE20:
            self.assertNotIn(pin, combined, pin)
        for pin in _NODE24:
            self.assertIn(pin, combined, pin)

    def test_assert_lines_are_not_printed_twice(self) -> None:
        wrapper = (ROOT / "scripts" / "ci-emulator-policy.sh").read_text(encoding="utf-8")
        self.assertNotIn('cat "$SUMMARY"', wrapper)
        self.assertIn('note "ASSERT OK:', wrapper)
        self.assertIn('echo "summary file: $SUMMARY"', wrapper)

    def test_wrapper_runs_every_leg_when_a_negative_leg_exits_1(self) -> None:
        # assert_post_run used to finish with set -e. The wrapper starts
        # with errexit off. Leaving it on aborts at factory-absent (exit 1)
        # inside `bash | tee`, so the later legs, the cert guard, and RESULT
        # never run. This stub has no emulator. LOGDIR is not /tmp/mdm-ci.
        policy = ROOT / "server" / "tests" / "fixtures" / "api35-atd-true-device_policy.txt"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logdir = root / "logs"
            certs = root / "certs"
            bindir = root / "bin"
            logdir.mkdir()
            bindir.mkdir()
            user = root / "dumpsys_user.txt"
            user.write_text(
                "Users:\n"
                "  UserInfo{0:Owner:c13} serialNo=0 isPrimary=true\n"
                "    Effective restrictions:\n"
                "      no_add_user\n"
                "      no_factory_reset\n"
                "    Device policy global restrictions:\n"
                "      no_add_user\n"
                "      no_factory_reset\n",
                encoding="utf-8",
            )
            adb = bindir / "adb"
            adb.write_text(
                "#!/bin/bash\n"
                "set -u\n"
                'if [ "${1:-}" = "-s" ]; then shift 2; fi\n'
                'cmd="${1:-}"; shift || true\n'
                'case "$cmd" in\n'
                "  logcat) exit 0 ;;\n"
                "  shell) ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n"
                'sub="${1:-}"; shift || true\n'
                'case "$sub" in\n'
                "  dumpsys)\n"
                '    if [ "${1:-}" = "device_policy" ]; then cat "$FIXTURE_POLICY"; else cat "$FIXTURE_USER"; fi\n'
                "    ;;\n"
                "  dpm) printf '%s\\n' 'Device owner: net.themark.grapheneosmdm' ;;\n"
                "  getprop)\n"
                '    if [ "${1:-}" = "ro.build.version.sdk" ]; then printf \'%s\\n\' 35; else printf \'%s\\n\' generic; fi\n'
                "    ;;\n"
                "esac\n"
                "exit 0\n",
                encoding="utf-8",
            )
            stub = root / "operate.sh"
            stub.write_text(
                "#!/bin/bash\n"
                'name="$(basename "$OUT")"\n'
                'case "$name" in\n'
                "  absent)\n"
                "    printf '%s\\n' 'FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=absent)'\n"
                "    exit 1 ;;\n"
                "  false)\n"
                "    printf '%s\\n' 'FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=false)'\n"
                "    exit 1 ;;\n"
                "  true-then-false)\n"
                "    printf '%s\\n' 'PASS: no_add_user applied via disallowAddUser=true, then cleared by disallowAddUser=false with no owner reset'\n"
                "    exit 0 ;;\n"
                "  true)\n"
                "    printf '%s\\n' 'PASS: no_add_user applied via policyFlags.disallowAddUser=true'\n"
                "    exit 0 ;;\n"
                "  factory-absent)\n"
                "    printf '%s\\n' 'FAIL: restriction no_factory_reset not applied (DISALLOW_FACTORY_RESET=absent)'\n"
                "    exit 1 ;;\n"
                "  factory-false)\n"
                "    printf '%s\\n' 'FAIL: restriction no_factory_reset not applied (DISALLOW_FACTORY_RESET=false)'\n"
                "    exit 1 ;;\n"
                "  factory-true-then-false)\n"
                "    printf '%s\\n' 'PASS: no_factory_reset applied via disallowFactoryReset=true, then cleared by disallowFactoryReset=false with no owner reset'\n"
                "    exit 0 ;;\n"
                "  factory-true)\n"
                "    printf '%s\\n' 'PASS: no_factory_reset applied via policyFlags.disallowFactoryReset=true'\n"
                "    exit 0 ;;\n"
                "  *)\n"
                "    printf '%s\\n' \"FAIL: unexpected leg $name\"\n"
                "    exit 99 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            adb.chmod(adb.stat().st_mode | stat.S_IEXEC)
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
            env = os.environ.copy()
            env.pop("GITHUB_STEP_SUMMARY", None)
            env.update(
                {
                    "PATH": str(bindir) + os.pathsep + env.get("PATH", ""),
                    "LOGDIR": str(logdir),
                    "CERTS_ROOT": str(certs),
                    "OPERATE_SCRIPT": str(stub),
                    "FIXTURE_POLICY": str(policy),
                    "FIXTURE_USER": str(user),
                    "SERIAL": "emulator-5554",
                }
            )
            proc = subprocess.run(
                ["bash", str(ROOT / "scripts" / "ci-emulator-policy.sh")],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
        out = proc.stdout
        self.assertEqual(proc.returncode, 0, out + proc.stderr)
        for needle in (
            "::group::leg absent",
            "::group::leg false",
            "::group::leg true-then-false",
            "::group::leg true",
            "== post-run state (post-run, no_add_user) ==",
            "::group::leg factory-absent",
            "::group::leg factory-false",
            "::group::leg factory-true-then-false",
            "::group::leg factory-true",
            "== post-run state (post-run-factory-reset, no_factory_reset) ==",
            "ASSERT OK: no cert or key file under",
            "ASSERT OK: no fleet.sqlite* under",
            "RESULT: PASS (AOSP ATD emulator, not GrapheneOS; attestation not asserted)",
        ):
            self.assertIn(needle, out, needle)
        self.assertNotIn("RESULT: FAIL", out)


if __name__ == "__main__":
    unittest.main()
