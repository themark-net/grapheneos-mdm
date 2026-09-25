#!/usr/bin/env python3
"""Integration test: gen certs -> mTLS check-in + catalog -> desired-state."""

from __future__ import annotations

import json
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from http.client import HTTPSConnection
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]


class LabCheckInTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.certs = Path(cls.tmp.name) / "certs"
        subprocess.check_call(
            ["bash", str(SERVER_DIR / "gen-lab-certs.sh"), str(cls.certs)],
            cwd=str(SERVER_DIR),
        )
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "lab_checkin", SERVER_DIR / "lab_checkin.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.mod = mod

        desired = json.loads((SERVER_DIR / "desired-state.example.json").read_text())
        mod.CheckInHandler.desired = desired
        mod.CheckInHandler.issue_tokens = True
        mod.CheckInHandler.catalog_dir = SERVER_DIR / "catalog"
        cls.store = mod.FleetStore(Path(cls.tmp.name) / "fleet.sqlite")
        mod.CheckInHandler.fleet = cls.store

        cls.httpd = mod.ThreadingHTTPServer(("127.0.0.1", 0), mod.CheckInHandler)
        ctx = mod.build_ssl_context(cls.certs)
        cls.httpd.socket = ctx.wrap_socket(cls.httpd.socket, server_side=True)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.mod.CheckInHandler.fleet = None
        cls.store.close()
        cls.httpd.shutdown()
        cls.tmp.cleanup()

    def _ssl_ctx(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context(cafile=str(self.certs / "ca.pem"))
        ctx.load_cert_chain(
            certfile=str(self.certs / "client.pem"),
            keyfile=str(self.certs / "client-key.pem"),
        )
        return ctx

    def test_checkin_mtls(self) -> None:
        body = {
            "schemaVersion": 1,
            "inventory": {
                "schemaVersion": 1,
                "deviceId": "test-device",
                "osVersion": "16",
                "securityPatch": "2026-09-01",
                "installedPackages": [
                    {"packageName": "net.themark.grapheneosmdm", "versionName": "0.1.0-alpha"}
                ],
            },
            "agentVersion": "test",
        }
        data = json.dumps(body).encode()
        conn = HTTPSConnection("127.0.0.1", self.port, context=self._ssl_ctx())
        conn.request("POST", "/v1/checkin", body=data, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        raw = resp.read().decode()
        self.assertEqual(resp.status, 200, raw)
        parsed = json.loads(raw)
        self.assertEqual(parsed["status"], "ok")
        self.assertEqual(parsed["desiredState"]["schemaVersion"], 1)
        self.assertIn("requiredPackages", parsed["desiredState"])
        pkgs = parsed["desiredState"]["requiredPackages"]
        self.assertTrue(pkgs)
        self.assertIn("apkUrl", pkgs[0])
        self.assertIn("sha256", pkgs[0])
        self.assertIn("shortLivedToken", parsed)
        conn.close()

    def test_catalog_download_mtls(self) -> None:
        conn = HTTPSConnection("127.0.0.1", self.port, context=self._ssl_ctx())
        conn.request("GET", "/v1/catalog/grapheneosmdm.apk")
        resp = conn.getresponse()
        raw = resp.read()
        self.assertEqual(resp.status, 200, raw[:200])
        self.assertEqual(raw, b"lab-placeholder-apk\n")
        conn.close()

    def test_catalog_rejects_traversal(self) -> None:
        conn = HTTPSConnection("127.0.0.1", self.port, context=self._ssl_ctx())
        conn.request("GET", "/v1/catalog/../lab_checkin.py")
        resp = conn.getresponse()
        raw = resp.read()
        self.assertIn(resp.status, (400, 404), raw[:200])
        conn.close()

    def _checkin(self, device_id: str) -> dict:
        body = {
            "schemaVersion": 1,
            "inventory": {
                "schemaVersion": 1,
                "deviceId": device_id,
                "osVersion": "16",
                "securityPatch": "2026-09-01",
                "installedPackages": [],
            },
        }
        data = json.dumps(body).encode()
        conn = HTTPSConnection("127.0.0.1", self.port, context=self._ssl_ctx())
        conn.request("POST", "/v1/checkin", body=data, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        raw = resp.read().decode()
        self.assertEqual(resp.status, 200, raw)
        conn.close()
        return json.loads(raw)

    def test_per_device_desired_override(self) -> None:
        override = {
            "schemaVersion": 1,
            "requiredPackages": [{"packageName": "net.example.only-this-device"}],
            "policyFlags": {},
        }
        self.store.set_desired("device-override", override)
        default_resp = self._checkin("device-default")
        override_resp = self._checkin("device-override")
        default_pkgs = default_resp["desiredState"]["requiredPackages"]
        override_pkgs = override_resp["desiredState"]["requiredPackages"]
        self.assertEqual(default_pkgs[0]["packageName"], "net.themark.grapheneosmdm")
        self.assertEqual(override_pkgs[0]["packageName"], "net.example.only-this-device")
        stored = {row["deviceId"]: row for row in self.store.list_devices()}
        self.assertIn("device-default", stored)
        self.assertFalse(stored["device-default"]["hasOverride"])
        self.assertTrue(stored["device-override"]["hasOverride"])

    def test_rejects_without_client_cert(self) -> None:
        ctx = ssl.create_default_context(cafile=str(self.certs / "ca.pem"))
        conn = HTTPSConnection("127.0.0.1", self.port, context=ctx)
        with self.assertRaises(Exception):
            conn.request("POST", "/v1/checkin", body=b"{}", headers={"Content-Type": "application/json"})
            conn.getresponse()
        conn.close()


if __name__ == "__main__":
    unittest.main()
