#!/usr/bin/env python3
"""Operator UI API against a temporary fleet database."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from fleet_store import FleetStore  # noqa: E402
from ui_server import serve  # noqa: E402


class UIServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FleetStore(Path(self.tmp.name) / "fleet.sqlite")
        self.httpd = serve(
            self.store,
            "127.0.0.1",
            0,
            {"schemaVersion": 1, "requiredPackages": [], "policyFlags": {}},
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.store.close()
        self.tmp.cleanup()

    def test_page_lists_and_edits_a_device(self) -> None:
        page = urllib.request.urlopen(self.base + "/").read().decode("utf-8")
        self.assertIn("GrapheneOS MDM", page)
        self.store.record_checkin(
            "pixel-7",
            "pixel-7",
            {"deviceId": "pixel-7", "osVersion": "16", "installedPackages": []},
        )
        devices = self._json("/api/devices")["devices"]
        self.assertEqual(devices[0]["deviceId"], "pixel-7")
        self._json(
            "/api/groups/pixels",
            method="PUT",
            body={"schemaVersion": 1, "requiredPackages": [], "policyFlags": {"cameraDisabled": True}},
        )
        self._json("/api/devices/pixel-7/group", method="POST", body={"group": "pixels"})
        detail = self._json("/api/devices/pixel-7")
        self.assertEqual(detail["desiredSource"], "group")
        self.assertTrue(detail["resolvedDesired"]["policyFlags"]["cameraDisabled"])
        self._json("/api/groups/pixels", method="DELETE")
        cleared = self._json("/api/devices/pixel-7")
        self.assertEqual(cleared["desiredSource"], "default")

    def _json(self, path: str, method: str = "GET", body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            return json.load(response)


if __name__ == "__main__":
    unittest.main()
