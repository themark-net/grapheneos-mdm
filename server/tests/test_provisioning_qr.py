#!/usr/bin/env python3
"""Provisioning QR checksum and payload shape."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from provisioning_qr import provisioning_payload, signature_checksum  # noqa: E402


class ProvisioningQrTest(unittest.TestCase):
    def test_checksum_is_unpadded_urlsafe_sha256(self) -> None:
        # SHA-256 of bytes 0..63. Standard base64 of that digest is
        # /eq5rPNxA2K9JljNyaKej5x1f8+YEWA6jER80dkVEQg=
        self.assertEqual(
            signature_checksum(bytes(range(64))),
            "_eq5rPNxA2K9JljNyaKej5x1f8-YEWA6jER80dkVEQg",
        )

    def test_payload_names_this_agent_and_server(self) -> None:
        payload = provisioning_payload(
            apk_url="https://mdm.example/dpc.apk",
            checksum="abc",
            server_base_url="https://mdm.example:8443/",
            wifi_ssid="lab",
            wifi_password="secret",
        )
        self.assertEqual(
            payload["android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME"],
            "net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver",
        )
        self.assertTrue(payload["android.app.extra.PROVISIONING_LEAVE_ALL_SYSTEM_APPS_ENABLED"])
        extras = payload["android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE"]
        self.assertEqual(extras["serverBaseUrl"], "https://mdm.example:8443")
        self.assertEqual(payload["android.app.extra.PROVISIONING_WIFI_SSID"], "lab")

    def test_rejects_cleartext_urls(self) -> None:
        with self.assertRaises(ValueError):
            provisioning_payload(
                apk_url="http://mdm.example/dpc.apk",
                checksum="abc",
                server_base_url="https://mdm.example",
            )


if __name__ == "__main__":
    unittest.main()
