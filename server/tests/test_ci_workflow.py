#!/usr/bin/env python3
"""CI path filters, Node 24 pins, and one-shot ASSERT lines.

A rename that leaves the old script name in a workflow is an orphan filter:
the emulator job would not run for the new file. A Node 20 pin is the
deprecation this phase removes. Re-printing the summary duplicates every
ASSERT line. No emulator.
"""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
