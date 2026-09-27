#!/usr/bin/env python3
"""Write an Android Device Owner provisioning QR for this agent.

The checksum is the URL-safe base64 (no padding) SHA-256 of the APK signing
certificate, which is what ManagedProvisioning checks before install.

Stock GrapheneOS SetupWizard does not open a scanner. This file is the payload
a wizard uses once it does. See docs/ENROLLMENT.md.

  python3 provisioning_qr.py --apk app-debug.apk \\
      --apk-url https://mdm.example/dpc.apk \\
      --server-url https://mdm.example:8443 \\
      --out provisioning.json --png provisioning.png
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

COMPONENT = "net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver"
EXTRAS_KEY = "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE"
SERVER_URL_KEY = "serverBaseUrl"


def signature_checksum(cert_der: bytes) -> str:
    digest = hashlib.sha256(cert_der).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def provisioning_payload(
    *,
    apk_url: str,
    checksum: str,
    server_base_url: str,
    wifi_ssid: str | None = None,
    wifi_password: str | None = None,
    wifi_security: str = "WPA",
    component: str = COMPONENT,
) -> dict:
    if not apk_url.startswith("https://"):
        raise ValueError("apk URL must be https")
    if not server_base_url.startswith("https://"):
        raise ValueError("server URL must be https")
    payload: dict = {
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": component,
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": apk_url,
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM": checksum,
        "android.app.extra.PROVISIONING_LEAVE_ALL_SYSTEM_APPS_ENABLED": True,
        EXTRAS_KEY: {SERVER_URL_KEY: server_base_url.rstrip("/")},
    }
    if wifi_ssid:
        payload["android.app.extra.PROVISIONING_WIFI_SSID"] = wifi_ssid
        payload["android.app.extra.PROVISIONING_WIFI_SECURITY_TYPE"] = wifi_security
        if wifi_password:
            payload["android.app.extra.PROVISIONING_WIFI_PASSWORD"] = wifi_password
    return payload


def signing_cert_der(apk: Path) -> bytes:
    with zipfile.ZipFile(apk) as zf:
        names = [
            name
            for name in zf.namelist()
            if name.startswith("META-INF/") and name.upper().endswith((".RSA", ".EC", ".DSA"))
        ]
        if not names:
            raise ValueError(f"{apk} has no META-INF signature block (v1 signature missing)")
        pkcs7 = zf.read(names[0])
    with tempfile.TemporaryDirectory() as tmp:
        der_path = Path(tmp) / "sig.pkcs7"
        pem_path = Path(tmp) / "cert.pem"
        cert_der = Path(tmp) / "cert.der"
        der_path.write_bytes(pkcs7)
        subprocess.check_call(
            [
                "openssl",
                "pkcs7",
                "-inform",
                "DER",
                "-print_certs",
                "-in",
                str(der_path),
                "-out",
                str(pem_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            ["openssl", "x509", "-in", str(pem_path), "-outform", "DER", "-out", str(cert_der)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return cert_der.read_bytes()


def write_png(payload: dict, path: Path) -> bool:
    try:
        subprocess.run(
            ["qrencode", "-o", str(path), "-l", "M"],
            input=json.dumps(payload, separators=(",", ":")),
            text=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return path.is_file()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", required=True, type=Path, help="signed APK the wizard will download")
    parser.add_argument("--apk-url", required=True, help="https URL of that exact APK")
    parser.add_argument("--server-url", required=True, help="https base URL saved into the agent")
    parser.add_argument("--wifi-ssid", default=None)
    parser.add_argument("--wifi-password", default=None)
    parser.add_argument("--wifi-security", default="WPA")
    parser.add_argument("--out", type=Path, default=Path("provisioning.json"))
    parser.add_argument("--png", type=Path, default=None, help="optional PNG path")
    args = parser.parse_args(argv)
    cert = signing_cert_der(args.apk)
    payload = provisioning_payload(
        apk_url=args.apk_url,
        checksum=signature_checksum(cert),
        server_base_url=args.server_url,
        wifi_ssid=args.wifi_ssid,
        wifi_password=args.wifi_password,
        wifi_security=args.wifi_security,
    )
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    png = args.png
    if png is not None:
        if write_png(payload, png):
            print(png)
        else:
            print("qrencode not available; JSON written without a PNG", flush=True)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
