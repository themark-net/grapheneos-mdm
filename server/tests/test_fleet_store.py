#!/usr/bin/env python3
"""Fleet store: inventory upsert and per-device desired-state override."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from fleet_store import FleetStore  # noqa: E402


DESIRED = {
    "schemaVersion": 1,
    "requiredPackages": [{"packageName": "net.example.override"}],
    "policyFlags": {"cameraDisabled": True},
}


class FleetStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "fleet.sqlite"
        self.store = FleetStore(self.db)

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_checkin_then_list_and_override(self) -> None:
        inventory = {
            "deviceId": "pixel-a",
            "osVersion": "16",
            "securityPatch": "2026-09-01",
            "installedPackages": [{"packageName": "net.themark.grapheneosmdm"}],
        }
        self.store.record_checkin("pixel-a", "pixel-a.lab", inventory)
        self.store.record_checkin("pixel-a", "pixel-a.lab", inventory)

        listed = self.store.list_devices()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["deviceId"], "pixel-a")
        self.assertEqual(listed[0]["packageCount"], 1)
        self.assertFalse(listed[0]["hasOverride"])

        default = {"schemaVersion": 1, "requiredPackages": [], "policyFlags": {}}
        self.assertIs(self.store.desired_for("pixel-a", default), default)

        self.store.set_desired("pixel-a", DESIRED)
        loaded = self.store.desired_for("pixel-a", default)
        self.assertEqual(loaded["requiredPackages"][0]["packageName"], "net.example.override")
        self.assertIs(self.store.desired_for("pixel-b", default), default)

        self.assertTrue(self.store.clear_desired("pixel-a"))
        self.assertFalse(self.store.clear_desired("pixel-a"))
        self.assertIs(self.store.desired_for("pixel-a", default), default)

    def test_group_desired_is_between_override_and_default(self) -> None:
        default = {
            "schemaVersion": 1,
            "requiredPackages": [{"packageName": "default"}],
            "policyFlags": {},
        }
        group = {
            "schemaVersion": 1,
            "requiredPackages": [{"packageName": "from-group"}],
            "policyFlags": {},
        }
        device = {
            "schemaVersion": 1,
            "requiredPackages": [{"packageName": "from-device"}],
            "policyFlags": {},
        }
        self.store.set_group_desired("pixels", group)
        self.store.set_group("pixel-a", "pixels")
        self.assertEqual(
            self.store.desired_for("pixel-a", default)["requiredPackages"][0]["packageName"],
            "from-group",
        )
        self.assertEqual(
            self.store.desired_for("pixel-b", default)["requiredPackages"][0]["packageName"],
            "default",
        )
        self.store.set_desired("pixel-a", device)
        self.assertEqual(
            self.store.desired_for("pixel-a", default)["requiredPackages"][0]["packageName"],
            "from-device",
        )
        self.store.clear_desired("pixel-a")
        self.assertEqual(
            self.store.desired_for("pixel-a", default)["requiredPackages"][0]["packageName"],
            "from-group",
        )

    def test_missing_attestation_after_a_challenge(self) -> None:
        inventory = {"deviceId": "pixel-a", "attestation": {"format": "none"}}
        self.store.record_checkin("pixel-a", "cn", inventory)
        self.assertEqual(self.store.observe_attestation("pixel-a", inventory)["status"], "none")
        self.store.issue_challenge("pixel-a")
        self.assertEqual(self.store.observe_attestation("pixel-a", inventory)["status"], "missing")

    def test_set_desired_rejects_bad_shape(self) -> None:
        with self.assertRaises(ValueError):
            self.store.set_desired("pixel-a", {"schemaVersion": 2})

    def test_cli_roundtrip_after_checkin(self) -> None:
        self.store.record_checkin(
            "pixel-a",
            "cn",
            {"deviceId": "pixel-a", "osVersion": "16", "installedPackages": []},
        )
        self.store.close()
        desired_path = Path(self.tmp.name) / "desired.json"
        desired_path.write_text(json.dumps(DESIRED), encoding="utf-8")
        script = str(SERVER_DIR / "fleet_store.py")
        subprocess.check_call(
            [sys.executable, script, "--db", str(self.db), "set-desired", "pixel-a", str(desired_path)]
        )
        show = json.loads(
            subprocess.check_output(
                [sys.executable, script, "--db", str(self.db), "show", "pixel-a"],
                text=True,
            )
        )
        self.assertEqual(show["desiredOverride"]["requiredPackages"][0]["packageName"], "net.example.override")
        self.assertEqual(show["inventory"]["deviceId"], "pixel-a")
        missing = subprocess.run(
            [sys.executable, script, "--db", str(self.db), "show", "missing"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(missing.returncode, 1)


if __name__ == "__main__":
    unittest.main()
