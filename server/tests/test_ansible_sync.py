#!/usr/bin/env python3
"""Ansible inventory sync onto fleet groups."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from ansible_sync import assignments, parse_inventory, sync  # noqa: E402
from fleet_store import FleetStore  # noqa: E402


class AnsibleSyncTest(unittest.TestCase):
    def test_parse_skips_vars_and_comments(self) -> None:
        groups = parse_inventory(
            """
            [pixels]
            pixel-7
            pixel-8 ansible_connection=local
            # spare
            [pixels:vars]
            foo=bar
            [pixels:children]
            other
            [lab]
            pixel-lab
            """
        )
        self.assertEqual(groups["pixels"], ["pixel-7", "pixel-8"])
        self.assertEqual(groups["lab"], ["pixel-lab"])
        self.assertNotIn("other", groups.get("pixels", []))

    def test_two_groups_for_one_device_fail(self) -> None:
        with self.assertRaises(ValueError) as caught:
            assignments({"pixels": ["pixel-7"], "lab": ["pixel-7"]})
        self.assertIn("pixel-7", str(caught.exception))

    def test_sync_writes_group_desired_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "hosts.ini").write_text("[pixels]\npixel-7\n", encoding="utf-8")
            group_vars = root / "group_vars"
            group_vars.mkdir()
            desired = {
                "schemaVersion": 1,
                "requiredPackages": [{"packageName": "net.example.pixels"}],
                "policyFlags": {},
            }
            (group_vars / "pixels.json").write_text(json.dumps(desired), encoding="utf-8")
            store = FleetStore(root / "fleet.sqlite")
            try:
                owner = sync(store, root / "hosts.ini", group_vars)
                self.assertEqual(owner, {"pixel-7": "pixels"})
                got = store.desired_for(
                    "pixel-7",
                    {"schemaVersion": 1, "requiredPackages": [], "policyFlags": {}},
                )
                self.assertEqual(got["requiredPackages"][0]["packageName"], "net.example.pixels")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
