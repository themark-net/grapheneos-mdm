#!/usr/bin/env python3
"""Inventory, groups, and desired state for the lab check-in server.

Desired state for a device is its override, else its group's desired state,
else the JSON file `lab_checkin.py` loaded.

  python3 fleet_store.py --db fleet.sqlite list
  python3 fleet_store.py --db fleet.sqlite show DEVICE_ID
  python3 fleet_store.py --db fleet.sqlite set-desired DEVICE_ID desired.json
  python3 fleet_store.py --db fleet.sqlite clear-desired DEVICE_ID
  python3 fleet_store.py --db fleet.sqlite set-group DEVICE_ID GROUP
  python3 fleet_store.py --db fleet.sqlite set-group-desired GROUP desired.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from attestation import assess_attestation


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
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS groups (
              name TEXT PRIMARY KEY,
              desired_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS device_groups (
              device_id TEXT PRIMARY KEY,
              group_name TEXT NOT NULL
            )
            """
        )
        self._ensure_column("devices", "attestation_status", "TEXT")
        self._ensure_column("devices", "verified_boot_state", "TEXT")
        self._ensure_column("devices", "pending_challenge", "TEXT")
        self._conn.commit()

    def _ensure_column(self, table: str, name: str, decl: str) -> None:
        cols = {row[1] for row in self._conn.execute(f"PRAGMA table_info({table})")}
        if name not in cols:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

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
        device_id = device_id or "unknown"
        with self._lock:
            override = self._conn.execute(
                "SELECT desired_json FROM desired_overrides WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            if override is not None:
                loaded = json.loads(override["desired_json"])
                if isinstance(loaded, dict):
                    return loaded
            membership = self._conn.execute(
                "SELECT group_name FROM device_groups WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            if membership is not None:
                group = self._conn.execute(
                    "SELECT desired_json FROM groups WHERE name = ?",
                    (membership["group_name"],),
                ).fetchone()
                if group is not None:
                    loaded = json.loads(group["desired_json"])
                    if isinstance(loaded, dict):
                        return loaded
        return default

    def set_group(self, device_id: str, group_name: str) -> None:
        if not device_id or not group_name:
            raise ValueError("device id and group name are required")
        with self._lock:
            group = self._conn.execute(
                "SELECT 1 FROM groups WHERE name = ?",
                (group_name,),
            ).fetchone()
            if group is None:
                raise ValueError(f"unknown group {group_name}")
            self._conn.execute(
                """
                INSERT INTO device_groups (device_id, group_name) VALUES (?, ?)
                ON CONFLICT(device_id) DO UPDATE SET group_name = excluded.group_name
                """,
                (device_id, group_name),
            )
            self._conn.commit()

    def clear_group(self, device_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM device_groups WHERE device_id = ?",
                (device_id,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def set_group_desired(self, group_name: str, desired: dict[str, Any]) -> None:
        if not group_name:
            raise ValueError("group name is required")
        payload = _desired_payload(desired)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO groups (name, desired_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                  desired_json = excluded.desired_json,
                  updated_at = excluded.updated_at
                """,
                (group_name, payload, utcnow()),
            )
            self._conn.commit()

    def clear_group_desired(self, group_name: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM groups WHERE name = ?", (group_name,))
            self._conn.execute(
                "DELETE FROM device_groups WHERE group_name = ?",
                (group_name,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def list_groups(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT g.name, g.updated_at, COUNT(d.device_id) AS device_count
                FROM groups g
                LEFT JOIN device_groups d ON d.group_name = g.name
                GROUP BY g.name
                ORDER BY g.name
                """
            ).fetchall()
        return [
            {"name": row["name"], "updatedAt": row["updated_at"], "deviceCount": row["device_count"]}
            for row in rows
        ]

    def set_desired(self, device_id: str, desired: dict[str, Any]) -> None:
        if not device_id:
            raise ValueError("device id is required")
        payload = _desired_payload(desired)
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
                       d.attestation_status, d.verified_boot_state,
                       o.desired_json IS NOT NULL AS has_override,
                       g.group_name
                FROM devices d
                LEFT JOIN desired_overrides o ON o.device_id = d.device_id
                LEFT JOIN device_groups g ON g.device_id = d.device_id
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
                    "group": row["group_name"],
                    "attestationStatus": row["attestation_status"],
                    "verifiedBootState": row["verified_boot_state"],
                }
            )
        return listed

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT d.device_id, d.client_cn, d.last_checkin_at, d.inventory_json,
                       d.attestation_status, d.verified_boot_state,
                       o.desired_json, g.group_name
                FROM devices d
                LEFT JOIN desired_overrides o ON o.device_id = d.device_id
                LEFT JOIN device_groups g ON g.device_id = d.device_id
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
            "group": row["group_name"],
            "attestationStatus": row["attestation_status"],
            "verifiedBootState": row["verified_boot_state"],
        }

    def pending_challenge(self, device_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT pending_challenge FROM devices WHERE device_id = ?",
                (device_id or "unknown",),
            ).fetchone()
        if row is None:
            return None
        return row["pending_challenge"]

    def observe_attestation(self, device_id: str, inventory: dict[str, Any]) -> dict[str, str | None]:
        """Check the inventory attestation against the challenge issued last time."""
        result = assess_attestation(inventory, self.pending_challenge(device_id))
        with self._lock:
            self._conn.execute(
                """
                UPDATE devices
                SET attestation_status = ?, verified_boot_state = ?
                WHERE device_id = ?
                """,
                (result["status"], result.get("verifiedBootState"), device_id or "unknown"),
            )
            self._conn.commit()
        return result

    def issue_challenge(self, device_id: str) -> str:
        """Store a new nonce for the next check-in and return it base64-encoded."""
        challenge = base64.b64encode(os.urandom(32)).decode("ascii")
        device_id = device_id or "unknown"
        with self._lock:
            self._conn.execute(
                """
                UPDATE devices SET pending_challenge = ? WHERE device_id = ?
                """,
                (challenge, device_id),
            )
            self._conn.commit()
        return challenge


def _desired_payload(desired: dict[str, Any]) -> str:
    if not isinstance(desired, dict) or desired.get("schemaVersion") != 1:
        raise ValueError("desired state must be an object with schemaVersion 1")
    if "requiredPackages" not in desired or "policyFlags" not in desired:
        raise ValueError("desired state must include requiredPackages and policyFlags")
    return json.dumps(desired, separators=(",", ":"), sort_keys=True)


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
    clear_cmd = sub.add_parser("clear-desired", help="fall back to group or default")
    clear_cmd.add_argument("device_id")
    set_group = sub.add_parser("set-group", help="put a device in a group")
    set_group.add_argument("device_id")
    set_group.add_argument("group_name")
    clear_group = sub.add_parser("clear-group", help="remove a device from its group")
    clear_group.add_argument("device_id")
    set_gd = sub.add_parser("set-group-desired", help="desired state shared by a group")
    set_gd.add_argument("group_name")
    set_gd.add_argument("path")
    clear_gd = sub.add_parser("clear-group-desired", help="delete a group and its memberships")
    clear_gd.add_argument("group_name")
    sub.add_parser("list-groups", help="groups and how many devices are in each")

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
        if args.cmd == "set-group":
            store.set_group(args.device_id, args.group_name)
            return 0
        if args.cmd == "clear-group":
            if not store.clear_group(args.device_id):
                print(f"no group for {args.device_id}", file=sys.stderr)
                return 1
            return 0
        if args.cmd == "set-group-desired":
            desired = json.loads(Path(args.path).read_text(encoding="utf-8"))
            store.set_group_desired(args.group_name, desired)
            return 0
        if args.cmd == "clear-group-desired":
            if not store.clear_group_desired(args.group_name):
                print(f"unknown group {args.group_name}", file=sys.stderr)
                return 1
            return 0
        if args.cmd == "list-groups":
            json.dump(store.list_groups(), sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        store.close()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
