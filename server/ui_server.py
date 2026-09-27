#!/usr/bin/env python3
"""Local operator page for the lab fleet database.

Binds to 127.0.0.1. Check-in stays on the mTLS port; this page does not
accept phone traffic.

  python3 ui_server.py --db fleet.sqlite --desired desired-state.example.json
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

_SERVER_DIR = Path(__file__).resolve().parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from fleet_store import FleetStore  # noqa: E402

PAGE = (_SERVER_DIR / "ui" / "index.html").read_text(encoding="utf-8")
EMPTY_DESIRED: dict[str, Any] = {"schemaVersion": 1, "requiredPackages": [], "policyFlags": {}}


class FleetUI(BaseHTTPRequestHandler):
    server_version = "GrapheneOsMdmUI/0.1"
    store: FleetStore
    default_desired: dict[str, Any] = EMPTY_DESIRED

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._bytes(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
            return
        if path == "/api/devices":
            self._json(200, {"devices": self.store.list_devices()})
            return
        if path == "/api/groups":
            self._json(200, {"groups": self.store.list_groups()})
            return
        device_id = _suffix(path, "/api/devices/")
        if device_id and "/" not in device_id:
            self._device(device_id)
            return
        group = _suffix(path, "/api/groups/")
        if group and "/" not in group:
            found = self.store.get_group(group)
            if found is None:
                self._json(404, {"error": "unknown group"})
                return
            self._json(200, found)
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        device_id = _suffix(path, "/api/devices/")
        if device_id and device_id.endswith("/group"):
            self._assign_group(device_id[: -len("/group")])
            return
        if device_id and device_id.endswith("/desired"):
            self._set_desired(device_id[: -len("/desired")])
            return
        self._json(404, {"error": "not found"})

    def do_PUT(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        group = _suffix(path, "/api/groups/")
        if not group or "/" in group:
            self._json(404, {"error": "not found"})
            return
        try:
            self.store.set_group_desired(group, self._read_json())
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        found = self.store.get_group(group)
        self._json(200, found or {"name": group})

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        device_id = _suffix(path, "/api/devices/")
        if device_id and device_id.endswith("/desired"):
            target = device_id[: -len("/desired")]
            self.store.clear_desired(target)
            self._device(target)
            return
        group = _suffix(path, "/api/groups/")
        if group and "/" not in group:
            if not self.store.clear_group_desired(group):
                self._json(404, {"error": "unknown group"})
                return
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[ui] " + (fmt % args) + "\n")

    def _device(self, device_id: str) -> None:
        found = self.store.get_device(device_id)
        if found is None:
            self._json(404, {"error": "unknown device"})
            return
        found["resolvedDesired"] = self.store.desired_for(device_id, self.default_desired)
        if found.get("desiredOverride") is not None:
            found["desiredSource"] = "device"
        elif found.get("group"):
            found["desiredSource"] = "group"
        else:
            found["desiredSource"] = "default"
        self._json(200, found)

    def _assign_group(self, device_id: str) -> None:
        if self.store.get_device(device_id) is None:
            self._json(404, {"error": "unknown device"})
            return
        try:
            body = self._read_json()
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        group = body.get("group") if isinstance(body, dict) else None
        try:
            if group:
                self.store.set_group(device_id, str(group))
            else:
                self.store.clear_group(device_id)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._device(device_id)

    def _set_desired(self, device_id: str) -> None:
        if self.store.get_device(device_id) is None:
            self._json(404, {"error": "unknown device"})
            return
        try:
            desired = self._read_json()
            self.store.set_desired(device_id, desired)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._device(device_id)

    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON") from exc

    def _json(self, code: int, payload: Any) -> None:
        self._bytes(code, "application/json", json.dumps(payload).encode("utf-8"))

    def _bytes(self, code: int, content_type: str, data: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def _suffix(path: str, prefix: str) -> str | None:
    if not path.startswith(prefix):
        return None
    return unquote(path[len(prefix) :])


def load_default(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return dict(EMPTY_DESIRED)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit(f"{path} is not a JSON object")
    return loaded


def serve(store: FleetStore, host: str, port: int, default_desired: dict[str, Any]) -> ThreadingHTTPServer:
    FleetUI.store = store
    FleetUI.default_desired = default_desired
    return ThreadingHTTPServer((host, port), FleetUI)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="fleet.sqlite")
    parser.add_argument("--desired", default="desired-state.example.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args(argv)
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("refusing to bind outside localhost")
    store = FleetStore(args.db)
    httpd = serve(store, args.host, args.port, load_default(Path(args.desired)))
    print(f"fleet UI http://{args.host}:{args.port}/  db={store.path}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("shutting down", flush=True)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
