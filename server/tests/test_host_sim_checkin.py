#!/usr/bin/env python3
"""Operate-or-FAIL: lab_checkin.py --db --simulate posts one host inventory.

Runs the fixture against a temporary sqlite. Does not reimplement the insert.
The fleet store must list the row as simulated, and the localhost fleet page
must label it simulated. Issue #35.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
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

EMPTY = (
    "No phone has checked in yet. The list fills after a mutual-TLS check-in "
    "against this database."
)
SIM_LABEL = '<span class="pill warn">simulated</span>'


class HostSimCheckinTest(unittest.TestCase):
    def test_fixture_row_is_visible_and_simulated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "fleet.sqlite"
            env = os.environ.copy()
            env.pop("MDM_DB", None)
            env.pop("MDM_LAB_CERTS", None)

            before = FleetStore(db)
            try:
                self.assertEqual(before.list_devices(), [])
            finally:
                before.close()

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SERVER_DIR / "lab_checkin.py"),
                    "--db",
                    str(db),
                    "--simulate",
                ],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertIn("deviceId=host-sim", proc.stdout)
            self.assertNotIn("listening", proc.stdout)
            self.assertNotIn("missing cert", proc.stderr)

            store = FleetStore(db)
            try:
                devices = store.list_devices()
                self.assertEqual([row["deviceId"] for row in devices], ["host-sim"])
                row = devices[0]
                self.assertTrue(row["simulated"])
                self.assertEqual(row["osVersion"], "host-fixture")
                self.assertEqual(row["packageCount"], 1)
                self.assertIsNone(row["attestationStatus"])
                detail = store.get_device("host-sim")
                self.assertIsNotNone(detail)
                assert detail is not None
                self.assertTrue(detail["simulated"])
                self.assertIsNone(detail["desiredOverride"])
                self.assertIsNone(detail["attestationStatus"])
                self.assertEqual(detail["inventory"]["model"], "host-sim")
                self.assertNotIn("wiped", json.dumps(detail).lower())
            finally:
                store.close()

            ui = FleetStore(db)
            httpd = serve(
                ui,
                "127.0.0.1",
                0,
                {"schemaVersion": 1, "requiredPackages": [], "policyFlags": {}},
            )
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{httpd.server_address[1]}"
            try:
                with urllib.request.urlopen(base + "/api/devices") as response:
                    payload = json.load(response)
                listed = payload["devices"]
                self.assertEqual([item["deviceId"] for item in listed], ["host-sim"])
                self.assertTrue(listed[0]["simulated"])
                with urllib.request.urlopen(base + "/api/devices/host-sim") as response:
                    one = json.load(response)
                self.assertTrue(one["simulated"])
                self.assertIsNone(one["wipeRecover"])
                self.assertNotIn("wiped", json.dumps(one).lower())
                with urllib.request.urlopen(base + "/") as response:
                    page = response.read().decode("utf-8")
            finally:
                httpd.shutdown()
                httpd.server_close()
                ui.close()

            self.assertIn(EMPTY, page)
            self.assertRegex(
                page,
                re.compile(
                    r"device\.simulated[\s\S]{0,160}" + re.escape(SIM_LABEL),
                ),
            )
            self.assertRegex(
                page,
                re.compile(
                    r"device\.simulated[\s\S]{0,200}not a mutual-TLS check-in",
                ),
            )
            self.assertIn("Simulated host inventory. Not a mutual-TLS check-in.", page)
            self.assertIn("No phone sent this inventory.", page)
            self.assertIn("Certificate ", page)
            self.assertIn("last check-in ", page)
            self.assertNotIn("wiped", page.lower())

    def test_simulate_without_db_exits_before_tls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.pop("MDM_DB", None)
            env["MDM_LAB_CERTS"] = str(Path(tmp) / "no-certs")
            proc = subprocess.run(
                [sys.executable, str(SERVER_DIR / "lab_checkin.py"), "--simulate"],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
            self.assertIn("needs --db", proc.stderr)
            self.assertNotIn("missing cert", proc.stderr)
            self.assertNotIn("listening", proc.stdout)
            self.assertEqual(list(Path(tmp).glob("*.sqlite")), [])


if __name__ == "__main__":
    unittest.main()
