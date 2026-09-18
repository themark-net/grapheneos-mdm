#!/usr/bin/env python3
"""Validate example payloads against protocol JSON Schema (draft 2020-12)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class SchemaSmokeTest(unittest.TestCase):
    def test_schema_files_parse(self) -> None:
        for name in (
            "inventory-report.schema.json",
            "desired-state.schema.json",
            "checkin-request.schema.json",
            "checkin-response.schema.json",
        ):
            schema = _load(name)
            self.assertEqual(schema.get("type"), "object")
            self.assertIn("properties", schema)

    def test_inventory_example_shape(self) -> None:
        inv = {
            "schemaVersion": 1,
            "deviceId": "abc",
            "osVersion": "16",
            "securityPatch": "2026-09-01",
            "installedPackages": [
                {"packageName": "net.themark.grapheneosmdm", "versionName": "0.1.0-alpha", "versionCode": 1}
            ],
            "attestation": {"format": "none"},
        }
        schema = _load("inventory-report.schema.json")
        for key in schema["required"]:
            self.assertIn(key, inv)

    def test_desired_example_matches_server_fixture(self) -> None:
        desired = json.loads(
            (ROOT.parent / "server" / "desired-state.example.json").read_text(encoding="utf-8")
        )
        schema = _load("desired-state.schema.json")
        for key in schema["required"]:
            self.assertIn(key, desired)
        pkg = desired["requiredPackages"][0]
        self.assertIn("apkUrl", pkg)
        self.assertRegex(pkg["sha256"], r"^[A-Fa-f0-9]{64}$")
        item_props = schema["properties"]["requiredPackages"]["items"]["properties"]
        self.assertIn("sha256", item_props)
        self.assertIn("signingCertSha256", item_props)


if __name__ == "__main__":
    unittest.main()
