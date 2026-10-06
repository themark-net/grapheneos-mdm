#!/usr/bin/env python3
"""Judge the second check-in on one lab sqlite.

The first inventory cannot match a challenge this database has not issued.
The second inventory is the record. Exit non-zero when that observation is
missing, or when its attestationStatus is challenge_mismatch, none, missing,
parse_error, or unsupported.

chain_invalid, boot_unverified, and ok are records. ok is the only status
that means verified boot passed, and only when verifiedBootState is Verified.
This module does not call an image GrapheneOS.

  python3 same_db_attestation.py --db fleet.sqlite --lab-log lab.log
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from fleet_store import FleetStore

FORBIDDEN_ATTESTATION = frozenset(
    {"challenge_mismatch", "none", "missing", "parse_error", "unsupported"}
)

# Same text lab_checkin.CheckInHandler writes. The address prefix is added
# by BaseHTTPRequestHandler-style logging and is not part of this string.
_CHECKIN_RE = re.compile(
    r"check-in deviceId=(?P<device>\S+) packages=\S+ "
    r"client=(?P<client>\S+) attestation=(?P<status>\S+)"
)


class SecondObservationError(Exception):
    """The second check-in is missing or is not an acceptable record."""


def format_checkin_log(
    device_id: str,
    package_count: int,
    client: str,
    attestation_status: str,
) -> str:
    """One check-in log line, without the client-address prefix."""
    return (
        f"check-in deviceId={device_id} packages={package_count} "
        f"client={client} attestation={attestation_status}"
    )


def checkin_observations(log_text: str) -> list[tuple[str, str]]:
    """Return (deviceId, attestationStatus) in log order."""
    found: list[tuple[str, str]] = []
    for line in log_text.splitlines():
        if "check-in deviceId=" not in line:
            continue
        match = _CHECKIN_RE.search(line)
        if match is None:
            raise SecondObservationError(f"unparsed check-in line: {line}")
        found.append((match.group("device"), match.group("status")))
    return found


def judge_second_observation(db_path: Path | str, log_text: str) -> dict[str, str | None]:
    """Read the second lab line and the sqlite row it must match.

    Exactly two check-in lines are required. A later check-in overwrites the
    sqlite row, so a third line is not the second observation.
    """
    observed = checkin_observations(log_text)
    if len(observed) < 2:
        raise SecondObservationError(
            f"second observation missing: {len(observed)} check-in line(s)"
        )
    if len(observed) != 2:
        raise SecondObservationError(
            "expected 2 check-in lines so the sqlite row is the second "
            f"observation, found {len(observed)}"
        )
    device_id, logged_status = observed[1]
    store = FleetStore(db_path)
    try:
        row = store.get_device(device_id)
    finally:
        store.close()
    if row is None:
        raise SecondObservationError(
            f"second observation missing: no sqlite row for {device_id}"
        )
    status = row.get("attestationStatus")
    boot = row.get("verifiedBootState")
    if not isinstance(status, str) or not status:
        raise SecondObservationError(
            f"second observation missing attestationStatus for {device_id}"
        )
    if status != logged_status:
        raise SecondObservationError(
            f"sqlite attestationStatus {status} is not the second lab "
            f"observation {logged_status}"
        )
    if status in FORBIDDEN_ATTESTATION:
        boot_text = "null" if boot is None else boot
        raise SecondObservationError(
            f"second attestationStatus {status} verifiedBootState {boot_text}"
        )
    return {"attestationStatus": status, "verifiedBootState": boot}


def format_result(status: str, boot: str | None) -> str:
    """Print the record. Claim verified boot only for status ok and Verified."""
    boot_text = "null" if boot is None else boot
    lines = [
        f"attestationStatus {status}",
        f"verifiedBootState {boot_text}",
        (
            "PASS: second check-in "
            f"attestationStatus={status} verifiedBootState={boot_text}"
        ),
    ]
    if status == "ok" and boot == "Verified":
        lines.append("verified boot passed")
    elif status != "ok":
        lines.append(
            "NOTE: attestationStatus is the server record. verified boot is not passed."
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="lab sqlite from this run")
    parser.add_argument("--lab-log", required=True, help="lab_checkin stderr log")
    args = parser.parse_args(argv)
    log_path = Path(args.lab_log)
    if not log_path.is_file():
        print(f"FAIL: lab log missing: {log_path}", file=sys.stderr)
        return 1
    try:
        result = judge_second_observation(args.db, log_path.read_text(encoding="utf-8"))
    except SecondObservationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(
        format_result(str(result["attestationStatus"]), result.get("verifiedBootState"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
