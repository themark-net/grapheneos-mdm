#!/usr/bin/env python3
"""Per-device inventory and desired-state overrides for the lab check-in server.

The default desired state still comes from the JSON file `lab_checkin.py` loads.
This store records the last inventory from each check-in and, when set, replaces
that default for one device id.

  python3 fleet_store.py --db fleet.sqlite list
  python3 fleet_store.py --db fleet.sqlite show DEVICE_ID
  python3 fleet_store.py --db fleet.sqlite set-desired DEVICE_ID desired.json
  python3 fleet_store.py --db fleet.sqlite clear-desired DEVICE_ID
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FleetStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
              device_id TEXT PRIMARY KEY,
              client_cn TEXT NOT NULL,
              last_checkin_at TEXT NOT NULL,
              inventory_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS desired_overrides (
              device_id TEXT PRIMARY KEY,
              desired_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def record_checkin(self, device_id: str, client_cn: str, inventory: dict[str, Any]) -> None:
        device_id = device_id or "unknown"
        payload = json.dumps(inventory, separators=(",", ":"), sort_keys=True)
        now = utcnow()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO devices (device_id, client_cn, last_checkin_at, inventory_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                  client_cn = excluded.client_cn,
                  last_checkin_at = excluded.last_checkin_at,
                  inventory_json = excluded.inventory_json
                """,
                (device_id, client_cn or "unknown", now, payload),
            )
            self._conn.commit()

    def desired_for(self, device_id: str, default: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT desired_json FROM desired_overrides WHERE device_id = ?",
                (device_id or "unknown",),
            ).fetchone()
        if row is None:
            return default
        loaded = json.loads(row["desired_json"])
        if not isinstance(loaded, dict):
            return default
        return loaded

    def set_desired(self, device_id: str, desired: dict[str, Any]) -> None:
        if not device_id:
            raise ValueError("device id is required")
        if not isinstance(desired, dict) or desired.get("schemaVersion") != 1:
            raise ValueError("desired state must be an object with schemaVersion 1")
        if "requiredPackages" not in desired or "policyFlags" not in desired:
            raise ValueError("desired state must include requiredPackages and policyFlags")
        payload = json.dumps(desired, separators=(",", ":"), sort_keys=True)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO desired_overrides (device_id, desired_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                  desired_json = excluded.desired_json,
                  updated_at = excluded.updated_at
                """,
                (device_id, payload, utcnow()),
            )
            self._conn.commit()

    def clear_desired(self, device_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM desired_overrides WHERE device_id = ?",
                (device_id,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def list_devices(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT d.device_id, d.client_cn, d.last_checkin_at, d.inventory_json,
                       o.desired_json IS NOT NULL AS has_override
                FROM devices d
                LEFT JOIN desired_overrides o ON o.device_id = d.device_id
                ORDER BY d.last_checkin_at DESC, d.device_id ASC
                """
            ).fetchall()
        listed: list[dict[str, Any]] = []
        for row in rows:
            inventory = json.loads(row["inventory_json"])
            packages = inventory.get("installedPackages") if isinstance(inventory, dict) else []
            listed.append(
                {
                    "deviceId": row["device_id"],
                    "clientCn": row["client_cn"],
                    "lastCheckinAt": row["last_checkin_at"],
                    "osVersion": inventory.get("osVersion") if isinstance(inventory, dict) else None,
                    "securityPatch": inventory.get("securityPatch") if isinstance(inventory, dict) else None,
                    "packageCount": len(packages or []),
                    "hasOverride": bool(row["has_override"]),
                }
            )
        return listed

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT d.device_id, d.client_cn, d.last_checkin_at, d.inventory_json,
                       o.desired_json
                FROM devices d
                LEFT JOIN desired_overrides o ON o.device_id = d.device_id
                WHERE d.device_id = ?
                """,
                (device_id,),
            ).fetchone()
        if row is None:
            return None
        override = json.loads(row["desired_json"]) if row["desired_json"] else None
        return {
            "deviceId": row["device_id"],
            "clientCn": row["client_cn"],
            "lastCheckinAt": row["last_checkin_at"],
            "inventory": json.loads(row["inventory_json"]),
            "desiredOverride": override,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="sqlite path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="last check-in per device")
    show = sub.add_parser("show", help="inventory and override for one device")
    show.add_argument("device_id")
    set_cmd = sub.add_parser("set-desired", help="replace desired state for one device")
    set_cmd.add_argument("device_id")
    set_cmd.add_argument("path")
    clear_cmd = sub.add_parser("clear-desired", help="fall back to the server default")
    clear_cmd.add_argument("device_id")

    args = parser.parse_args(argv)
    store = FleetStore(args.db)
    try:
        if args.cmd == "list":
            devices = store.list_devices()
            json.dump(devices, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
        if args.cmd == "show":
            device = store.get_device(args.device_id)
            if device is None:
                print(f"unknown device {args.device_id}", file=sys.stderr)
                return 1
            json.dump(device, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
        if args.cmd == "set-desired":
            desired = json.loads(Path(args.path).read_text(encoding="utf-8"))
            store.set_desired(args.device_id, desired)
            return 0
        if args.cmd == "clear-desired":
            if not store.clear_desired(args.device_id):
                print(f"no override for {args.device_id}", file=sys.stderr)
                return 1
            return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        store.close()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
