#!/usr/bin/env python3
"""Integration test: gen certs → mTLS check-in → desired-state."""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
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
        # Import server module
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

        cls.httpd = mod.ThreadingHTTPServer(("127.0.0.1", 0), mod.CheckInHandler)
        ctx = mod.build_ssl_context(cls.certs)
        cls.httpd.socket = ctx.wrap_socket(cls.httpd.socket, server_side=True)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
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
        self.assertIn("shortLivedToken", parsed)
        conn.close()

    def test_rejects_without_client_cert(self) -> None:
        ctx = ssl.create_default_context(cafile=str(self.certs / "ca.pem"))
        # no client cert
        conn = HTTPSConnection("127.0.0.1", self.port, context=ctx)
        with self.assertRaises(Exception):
            conn.request("POST", "/v1/checkin", body=b"{}", headers={"Content-Type": "application/json"})
            conn.getresponse()
        conn.close()


if __name__ == "__main__":
    unittest.main()
