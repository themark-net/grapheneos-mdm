#!/usr/bin/env python3
"""Apply an Ansible inventory onto the lab fleet store.

`group_vars/<group>.json` is the desired-state document for that group
(same schema as desired-state.example.json). JSON is valid Ansible group_vars.

`hosts.ini` lists device ids under `[group]`. A device in two groups is an
error: the store keeps one group per device. `:vars` and `:children` sections
are ignored.

  python3 ansible_sync.py --db fleet.sqlite \
      --inventory ../ansible/inventory/hosts.ini \
      --group-vars ../ansible/group_vars
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SERVER_DIR = Path(__file__).resolve().parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from fleet_store import FleetStore  # noqa: E402


def parse_inventory(text: str) -> dict[str, list[str]]:
    """Group name to device ids, in file order. Skips vars and children sections."""
    groups: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if ":" in name:
                current = None
                continue
            current = name
            groups.setdefault(current, [])
            continue
        if current is None:
            continue
        device_id = line.split()[0]
        if device_id and device_id not in groups[current]:
            groups[current].append(device_id)
    return groups


def assignments(groups: dict[str, list[str]]) -> dict[str, str]:
    """Device id to its single group. Raises if a device is listed twice."""
    owner: dict[str, str] = {}
    for group, devices in groups.items():
        for device_id in devices:
            previous = owner.get(device_id)
            if previous is not None and previous != group:
                raise ValueError(f"{device_id} is in both {previous} and {group}")
            owner[device_id] = group
    return owner


def load_group_desired(path: Path) -> dict[str, Any]:
    desired = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(desired, dict) or desired.get("schemaVersion") != 1:
        raise ValueError(f"{path} must be a desired-state object with schemaVersion 1")
    if "requiredPackages" not in desired or "policyFlags" not in desired:
        raise ValueError(f"{path} must include requiredPackages and policyFlags")
    return desired


def sync(store: FleetStore, inventory_path: Path, group_vars: Path) -> dict[str, str]:
    groups = parse_inventory(inventory_path.read_text(encoding="utf-8"))
    owner = assignments(groups)
    for group in groups:
        path = group_vars / f"{group}.json"
        if not path.is_file():
            raise ValueError(f"missing {path}")
        store.set_group_desired(group, load_group_desired(path))
    for device_id, group in owner.items():
        store.set_group(device_id, group)
    return owner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--group-vars", required=True, type=Path)
    args = parser.parse_args(argv)
    store = FleetStore(args.db)
    try:
        owner = sync(store, args.inventory, args.group_vars)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        store.close()
    json.dump(owner, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
