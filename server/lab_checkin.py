#!/usr/bin/env python3
"""Thin lab mTLS check-in + private catalog server for grapheneos-mdm.

POST /v1/checkin       - requires client certificate; returns desired-state JSON.
GET  /v1/catalog/<apk> - serves APK bytes from --catalog-dir (mTLS required).
GET  /healthz          - liveness.

Optional --db sqlite records each device's last inventory and serves a
per-device desired-state override when one has been set (see fleet_store.py).

Usage:
  ./gen-lab-certs.sh
  python3 lab_checkin.py --certs ./lab-certs --port 8443 \\
      --desired desired-state.example.json --catalog-dir ./catalog

Environment:
  MDM_LAB_CERTS   directory with server.pem, server-key.pem, ca.pem
  MDM_DESIRED     path to desired-state JSON file
  MDM_CATALOG     directory of signed APKs for /v1/catalog/
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import sys
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

_SERVER_DIR = Path(__file__).resolve().parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from fleet_store import FleetStore  # noqa: E402


SCHEMA_VERSION = 1
CHECKIN_PATHS = {"/v1/checkin", "/checkin"}
CATALOG_PREFIX = "/v1/catalog/"


def default_desired() -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "requiredPackages": [
            {
                "packageName": "net.themark.grapheneosmdm",
                "versionName": "0.1.0-alpha",
            }
        ],
        "policyFlags": {
            "disallowAddUser": True,
            "disallowFactoryReset": False,
            "cameraDisabled": False,
        },
        "commands": [{"type": "noop", "id": "lab-boot"}],
    }


class CheckInHandler(BaseHTTPRequestHandler):
    server_version = "GrapheneOsMdmLab/0.3"
    desired: dict[str, Any] = default_desired()
    issue_tokens: bool = True
    catalog_dir: Path | None = None
    fleet: FleetStore | None = None

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _client_subject(self) -> str:
        cert = getattr(self.connection, "getpeercert", lambda: None)()
        if not cert:
            return "unknown"
        for rdn in cert.get("subject", ()):
            for key, value in rdn:
                if key == "commonName":
                    return value
        return str(cert.get("serialNumber", "peer"))

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            self._json(200, {"status": "ok"})
            return
        if path.startswith(CATALOG_PREFIX):
            self._serve_catalog(path[len(CATALOG_PREFIX) :])
            return
        self._json(404, {"status": "error", "message": "not found"})

    def _serve_catalog(self, name: str) -> None:
        # Prevent path traversal; catalog is a flat signed-APK drop.
        safe = Path(unquote(name)).name
        if not safe or safe != name.replace("\\", "/").split("/")[-1]:
            self._json(400, {"status": "error", "message": "invalid catalog name"})
            return
        if self.catalog_dir is None or not self.catalog_dir.is_dir():
            self._json(404, {"status": "error", "message": "catalog not configured"})
            return
        target = (self.catalog_dir / safe).resolve()
        try:
            target.relative_to(self.catalog_dir.resolve())
        except ValueError:
            self._json(400, {"status": "error", "message": "invalid catalog path"})
            return
        if not target.is_file():
            self._json(404, {"status": "error", "message": "apk not found"})
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.android.package-archive")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Catalog-Name", safe)
        self.end_headers()
        self.wfile.write(data)
        self.log_message("catalog serve %s (%d bytes) client=%s", safe, len(data), self._client_subject())

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path not in CHECKIN_PATHS:
            self._json(404, {"status": "error", "message": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"status": "error", "message": "invalid JSON"})
            return

        inventory = body.get("inventory") or {}
        if not isinstance(inventory, dict):
            inventory = {}
        device_id = inventory.get("deviceId") or "unknown"
        subject = self._client_subject()
        desired = self.desired
        if self.fleet is not None:
            self.fleet.record_checkin(device_id, subject, inventory)
            desired = self.fleet.desired_for(device_id, self.desired)
        self.log_message(
            "check-in deviceId=%s packages=%s client=%s",
            device_id,
            len(inventory.get("installedPackages") or []),
            subject,
        )

        response: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "status": "ok",
            "desiredState": desired,
            "message": f"lab check-in accepted for {device_id}",
            "attestationChallenge": base64.b64encode(os.urandom(32)).decode("ascii"),
        }
        if self.issue_tokens:
            exp = datetime.now(timezone.utc) + timedelta(hours=1)
            response["shortLivedToken"] = {
                "token": f"lab-{uuid.uuid4().hex}",
                "expiresAt": exp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        self._json(200, response)

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def build_ssl_context(certs: Path) -> ssl.SSLContext:
    server_cert = certs / "server.pem"
    server_key = certs / "server-key.pem"
    ca = certs / "ca.pem"
    for p in (server_cert, server_key, ca):
        if not p.is_file():
            raise SystemExit(f"missing cert file: {p}")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_cert_chain(certfile=str(server_cert), keyfile=str(server_key))
    ctx.load_verify_locations(cafile=str(ca))
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--certs",
        default=None,
        help="dir with server.pem, server-key.pem, ca.pem",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--desired", default=None, help="desired-state JSON path")
    parser.add_argument("--catalog-dir", default=None, help="directory of APKs for /v1/catalog/")
    parser.add_argument(
        "--db",
        default=None,
        help="sqlite path; record inventory and apply per-device desired-state overrides",
    )
    parser.add_argument("--no-tokens", action="store_true")
    args = parser.parse_args(argv)

    certs = Path(args.certs or __import__("os").environ.get("MDM_LAB_CERTS", "lab-certs"))
    desired_path = Path(
        args.desired
        or __import__("os").environ.get("MDM_DESIRED", "desired-state.example.json")
    )
    catalog = Path(
        args.catalog_dir
        or __import__("os").environ.get("MDM_CATALOG", "catalog")
    )
    if desired_path.is_file():
        CheckInHandler.desired = json.loads(desired_path.read_text(encoding="utf-8"))
    CheckInHandler.issue_tokens = not args.no_tokens
    CheckInHandler.catalog_dir = catalog if catalog.is_dir() else None
    db_path = args.db or __import__("os").environ.get("MDM_DB")
    CheckInHandler.fleet = FleetStore(db_path) if db_path else None

    httpd = ThreadingHTTPServer((args.host, args.port), CheckInHandler)
    httpd.socket = build_ssl_context(certs).wrap_socket(httpd.socket, server_side=True)
    print(
        f"lab check-in listening https://{args.host}:{args.port}/v1/checkin "
        f"(mTLS required, certs={certs}, catalog={CheckInHandler.catalog_dir}, "
        f"db={CheckInHandler.fleet.path if CheckInHandler.fleet else None})",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("shutting down", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
