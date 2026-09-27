#!/usr/bin/env python3
"""Operator UI against a temporary fleet database.

Wipe must not persist unless the confirm header matches the device id or
group name. Status copy stays queued / still-present / missing — never wiped.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from fleet_store import FleetStore  # noqa: E402
from ui_server import (  # noqa: E402
    UNKNOWN_DEVICE,
    WIPE_QUEUED,
    WIPE_STILL,
    contains_wipe,
    main,
    merge_wipe_command,
    serve,
    wipe_recover,
)

BASE_DESIRED = {
    "schemaVersion": 1,
    "requiredPackages": [{"packageName": "net.example.keep"}],
    "policyFlags": {"cameraDisabled": True},
}


class WipeHelperTest(unittest.TestCase):
    def test_contains_wipe_is_only_a_wipe_command(self) -> None:
        self.assertFalse(contains_wipe(None))
        self.assertFalse(contains_wipe({"commands": "wipe"}))
        self.assertFalse(contains_wipe({"policyFlags": {"wipe": True}}))
        self.assertFalse(contains_wipe({"commands": [{"type": "lock", "id": "l"}]}))
        self.assertFalse(contains_wipe({"commands": [{"type": "wipe-now"}]}))
        self.assertTrue(contains_wipe({"commands": [{"type": "noop"}, {"type": "wipe", "id": "w"}]}))

    def test_merge_keeps_other_keys_and_one_wipe(self) -> None:
        merged = merge_wipe_command(BASE_DESIRED, "wipe-1")
        self.assertEqual(merged["requiredPackages"], BASE_DESIRED["requiredPackages"])
        self.assertTrue(merged["policyFlags"]["cameraDisabled"])
        self.assertEqual(merged["commands"], [{"type": "wipe", "id": "wipe-1"}])
        self.assertNotIn("commands", BASE_DESIRED)
        again = merge_wipe_command(
            {**merged, "commands": [{"type": "lock", "id": "l"}, {"type": "wipe", "id": "wipe-1"}]},
            "wipe-2",
        )
        wipes = [item for item in again["commands"] if item["type"] == "wipe"]
        self.assertEqual(wipes, [{"type": "wipe", "id": "wipe-1"}])
        self.assertEqual(again["commands"][0]["type"], "lock")

    def test_recover_copy_never_says_wiped(self) -> None:
        self.assertIsNone(wipe_recover(False, "2099-01-01T00:00:00Z", "2020-01-01T00:00:00Z", True))
        self.assertEqual(
            wipe_recover(True, "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", True),
            WIPE_QUEUED,
        )
        self.assertEqual(wipe_recover(True, "2099-01-01T00:00:00Z", None, True), WIPE_QUEUED)
        still = wipe_recover(True, "2026-03-01T00:00:00Z", "2026-02-01T00:00:00Z", True)
        self.assertEqual(still, WIPE_STILL)
        self.assertNotIn("wiped", still.lower())


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
        self.httpd.server_close()
        self.store.close()
        self.tmp.cleanup()

    def test_page_lists_and_edits_a_device(self) -> None:
        page = self._page()
        self.assertIn("GrapheneOS MDM", page)
        self._checkin("pixel-7")
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
        self._json(
            "/api/groups/pixels",
            method="DELETE",
            headers={"X-Confirm-Delete": "pixels"},
        )
        cleared = self._json("/api/devices/pixel-7")
        self.assertEqual(cleared["desiredSource"], "default")

    def test_wipe_json_does_not_persist_without_exact_confirm(self) -> None:
        self._checkin("pixel-7")
        self._json("/api/devices/pixel-7/desired", method="POST", body=BASE_DESIRED)
        wipe_body = {
            **BASE_DESIRED,
            "commands": [{"type": "wipe", "id": "from-json"}],
        }
        status, payload = self._raw(
            "/api/devices/pixel-7/desired",
            method="POST",
            body=wipe_body,
        )
        self.assertEqual(status, 400)
        self.assertIn("does not match", payload["error"])
        status, payload = self._raw(
            "/api/devices/pixel-7/desired",
            method="POST",
            body=wipe_body,
            headers={"X-Confirm-Wipe": "pixel-8"},
        )
        self.assertEqual(status, 400)
        unchanged = self._json("/api/devices/pixel-7")
        self.assertNotIn("commands", unchanged["desiredOverride"])
        self.assertTrue(unchanged["desiredOverride"]["policyFlags"]["cameraDisabled"])
        self.assertIsNone(unchanged["wipeRecover"])
        saved = self._json(
            "/api/devices/pixel-7/desired",
            method="POST",
            body=wipe_body,
            headers={"X-Confirm-Wipe": "pixel-7"},
        )
        self.assertEqual(saved["wipeRecover"], WIPE_QUEUED)
        self.assertEqual(saved["desiredOverride"]["commands"][0]["id"], "from-json")
        self.assertEqual(saved["desiredOverride"]["requiredPackages"][0]["packageName"], "net.example.keep")

    def test_lock_command_does_not_need_wipe_confirm(self) -> None:
        self._checkin("pixel-7")
        saved = self._json(
            "/api/devices/pixel-7/desired",
            method="POST",
            body={**BASE_DESIRED, "commands": [{"type": "lock", "id": "lock-1"}]},
        )
        self.assertEqual(saved["desiredOverride"]["commands"][0]["type"], "lock")
        self.assertIsNone(saved["wipeRecover"])

    def test_dedicated_wipe_merges_and_stays_queued(self) -> None:
        self._checkin("pixel-7")
        self._json("/api/devices/pixel-7/desired", method="POST", body=BASE_DESIRED)
        status, _payload = self._raw("/api/devices/pixel-7/wipe", method="POST", body={})
        self.assertEqual(status, 400)
        self.assertNotIn("commands", self._json("/api/devices/pixel-7")["desiredOverride"])
        queued = self._json(
            "/api/devices/pixel-7/wipe",
            method="POST",
            body={},
            headers={"X-Confirm-Wipe": "pixel-7"},
        )
        self.assertEqual(queued["wipeRecover"], WIPE_QUEUED)
        self.assertNotIn("wiped", queued["wipeRecover"].lower())
        override = queued["desiredOverride"]
        self.assertTrue(override["policyFlags"]["cameraDisabled"])
        self.assertEqual(override["requiredPackages"][0]["packageName"], "net.example.keep")
        self.assertEqual([item["type"] for item in override["commands"]], ["wipe"])
        self.assertTrue(override["commands"][0]["id"].startswith("wipe-"))
        self.assertIn("pixel-7", [item["deviceId"] for item in self._json("/api/devices")["devices"]])

    def test_later_checkin_is_still_present_not_wiped(self) -> None:
        self._checkin("pixel-7")
        self._json(
            "/api/devices/pixel-7/wipe",
            method="POST",
            body={},
            headers={"X-Confirm-Wipe": "pixel-7"},
        )
        with self.store._lock:
            self.store._conn.execute(
                "UPDATE devices SET last_checkin_at = ? WHERE device_id = ?",
                ("2099-01-01T00:00:00Z", "pixel-7"),
            )
            self.store._conn.commit()
        later = self._json("/api/devices/pixel-7")
        self.assertEqual(later["wipeRecover"], WIPE_STILL)
        self.assertNotIn("wiped", later["wipeRecover"].lower())

    def test_group_wipe_requires_name_and_lists_members(self) -> None:
        self._checkin("pixel-7")
        self._checkin("pixel-8")
        self._json(
            "/api/groups/pixels",
            method="PUT",
            body={"schemaVersion": 1, "requiredPackages": [], "policyFlags": {"cameraDisabled": True}},
        )
        self._json("/api/devices/pixel-7/group", method="POST", body={"group": "pixels"})
        self._json("/api/devices/pixel-8/group", method="POST", body={"group": "pixels"})
        listed = self._json("/api/groups/pixels")
        self.assertEqual(listed["deviceIds"], ["pixel-7", "pixel-8"])
        wipe_body = {
            "schemaVersion": 1,
            "requiredPackages": [],
            "policyFlags": {"cameraDisabled": True},
            "commands": [{"type": "wipe", "id": "group-wipe"}],
        }
        status, _payload = self._raw("/api/groups/pixels", method="PUT", body=wipe_body)
        self.assertEqual(status, 400)
        self.assertNotIn("commands", self._json("/api/groups/pixels")["desired"])
        saved = self._json(
            "/api/groups/pixels",
            method="PUT",
            body=wipe_body,
            headers={"X-Confirm-Wipe": "pixels"},
        )
        self.assertEqual(saved["deviceIds"], ["pixel-7", "pixel-8"])
        self.assertTrue(contains_wipe(saved["desired"]))
        detail = self._json("/api/devices/pixel-7")
        self.assertEqual(detail["desiredSource"], "group")
        self.assertEqual(detail["wipeRecover"], WIPE_QUEUED)
        self.assertTrue(detail["resolvedDesired"]["policyFlags"]["cameraDisabled"])

    def test_delete_group_requires_typed_name(self) -> None:
        self._json(
            "/api/groups/pixels",
            method="PUT",
            body={"schemaVersion": 1, "requiredPackages": [], "policyFlags": {}},
        )
        status, payload = self._raw("/api/groups/pixels", method="DELETE")
        self.assertEqual(status, 400)
        self.assertIn("group name", payload["error"])
        self.assertEqual(self._json("/api/groups/pixels")["name"], "pixels")
        status, _payload = self._raw(
            "/api/groups/pixels",
            method="DELETE",
            headers={"X-Confirm-Delete": "lab"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(self._json("/api/groups/pixels")["name"], "pixels")
        self._json("/api/groups/pixels", method="DELETE", headers={"X-Confirm-Delete": "pixels"})
        status, _payload = self._raw("/api/groups/pixels")
        self.assertEqual(status, 404)

    def test_unknown_device_and_invalid_json_leave_the_store(self) -> None:
        self._checkin("pixel-7")
        self._json("/api/devices/pixel-7/desired", method="POST", body=BASE_DESIRED)
        status, payload = self._raw("/api/devices/missing-phone")
        self.assertEqual(status, 404)
        self.assertIn("unknown", payload["error"])
        status, payload = self._raw(
            "/api/devices/pixel-7/desired",
            method="POST",
            data=b"not-json",
        )
        self.assertEqual(status, 400)
        self.assertIn("invalid JSON", payload["error"])
        status, _payload = self._raw(
            "/api/devices/pixel-7/desired",
            method="POST",
            body={"schemaVersion": 1},
        )
        self.assertEqual(status, 400)
        kept = self._json("/api/devices/pixel-7")
        self.assertEqual(kept["desiredOverride"]["requiredPackages"][0]["packageName"], "net.example.keep")
        page = self._page()
        self.assertIn(UNKNOWN_DEVICE, page)

    def test_empty_database_has_empty_state_and_wipe_gate_copy(self) -> None:
        page = self._page()
        self.assertIn(
            "No phone has checked in yet. The list fills after a mutual-TLS check-in against this database.",
            page,
        )
        self.assertIn("Wipe device…", page)
        self.assertIn(WIPE_QUEUED, page)
        self.assertIn("X-Confirm-Wipe", page)
        self.assertIn("No devices assigned now — wipe runs when a device in this group checks in.", page)
        self.assertNotIn("Device wiped", page)
        self.assertNotIn("sample-pixel", page)
        self.assertNotIn("A wipe command in this JSON runs", page)
        self.assertEqual(self._json("/api/devices")["devices"], [])

    def test_refuses_non_loopback_host(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main(["--host", "0.0.0.0", "--db", str(Path(self.tmp.name) / "unused.sqlite")])
        self.assertIn("localhost", str(raised.exception))

    def _checkin(self, device_id: str) -> None:
        self.store.record_checkin(
            device_id,
            device_id,
            {"deviceId": device_id, "osVersion": "16", "installedPackages": []},
        )

    def _page(self) -> str:
        with urllib.request.urlopen(self.base + "/") as response:
            return response.read().decode("utf-8")

    def _json(
        self,
        path: str,
        method: str = "GET",
        body: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        status, payload = self._raw(path, method=method, body=body, headers=headers)
        if status >= 400:
            raise AssertionError(f"{method} {path} -> {status} {payload}")
        return payload

    def _raw(
        self,
        path: str,
        method: str = "GET",
        body: dict | None = None,
        data: bytes | None = None,
        headers: dict | None = None,
    ) -> tuple[int, dict]:
        if data is None and body is not None:
            data = json.dumps(body).encode("utf-8")
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"error": raw}
            return exc.code, payload


if __name__ == "__main__":
    unittest.main()
