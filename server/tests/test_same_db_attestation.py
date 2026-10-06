#!/usr/bin/env python3
"""Second observation on one sqlite: forbidden statuses fail, chain_invalid is a record.

Uses FleetStore.observe_attestation and the lab check-in log line. No emulator.
A bug that accepts challenge_mismatch, or that reads the first check-in, fails here.
"""

from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from fleet_store import FleetStore  # noqa: E402
from same_db_attestation import format_checkin_log  # noqa: E402

CLI = [sys.executable, str(SERVER_DIR / "same_db_attestation.py")]


def _tlv(tag: int, content: bytes) -> bytes:
    if len(content) >= 128:
        raise AssertionError("test DER must stay short")
    return bytes([tag, len(content)]) + content


def _seq(*parts: bytes) -> bytes:
    return _tlv(0x30, b"".join(parts))


def _leaf_with_challenge(challenge: bytes, boot: int = 0) -> bytes:
    root = _seq(_tlv(0x04, b"\x11"), _tlv(0x01, b"\xff"), _tlv(0x02, bytes([boot])))
    wrapped = bytes([0xBF, 0x85, 0x40, len(root)]) + root
    description = _seq(
        _tlv(0x02, b"\x04"),
        _tlv(0x0A, b"\x01"),
        _tlv(0x02, b"\x01"),
        _tlv(0x0A, b"\x01"),
        _tlv(0x04, challenge),
        wrapped,
    )
    oid = bytes.fromhex("060a2b06010401d679020111")
    return _seq(oid + _tlv(0x04, description))


def _keymint(challenge: bytes, boot: int = 0) -> dict:
    payload = base64.b64encode(_leaf_with_challenge(challenge, boot=boot)).decode("ascii")
    return {"format": "keymint", "payloadB64": payload}


class SameDbAttestationTest(unittest.TestCase):
    def _run_without_challenge(self, second: dict) -> subprocess.CompletedProcess[str]:
        """Two observes and no issue_challenge, so a format=none second stays none."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "fleet.sqlite"
            log_path = root / "lab.log"
            store = FleetStore(db)
            try:
                first = {
                    "deviceId": "dev-1",
                    "installedPackages": [],
                    "attestation": {"format": "none"},
                }
                store.record_checkin("dev-1", "lab-device-01", first)
                first_obs = store.observe_attestation("dev-1", first)
                store.record_checkin("dev-1", "lab-device-01", second)
                second_obs = store.observe_attestation("dev-1", second)
            finally:
                store.close()
            lines = [
                format_checkin_log("dev-1", 0, "lab-device-01", first_obs["status"] or ""),
                format_checkin_log("dev-1", 0, "lab-device-01", second_obs["status"] or ""),
            ]
            log_path.write_text(
                "".join(f"127.0.0.1 - {line}\n" for line in lines),
                encoding="utf-8",
            )
            return subprocess.run(
                [*CLI, "--db", str(db), "--lab-log", str(log_path)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_chain_invalid_is_a_record_and_does_not_claim_verified_boot(self) -> None:
        # Build the second inventory inside _run? The challenge is created there.
        # Drive it locally so the leaf contains the issued nonce.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "fleet.sqlite"
            log_path = root / "lab.log"
            store = FleetStore(db)
            try:
                first = {
                    "deviceId": "dev-1",
                    "installedPackages": [],
                    "attestation": {"format": "none"},
                }
                store.record_checkin("dev-1", "lab-device-01", first)
                first_obs = store.observe_attestation("dev-1", first)
                challenge = store.issue_challenge("dev-1")
                raw = base64.b64decode(challenge)
                # boot Verified in the leaf, but the chain does not trust the root.
                second = {
                    "deviceId": "dev-1",
                    "installedPackages": [],
                    "attestation": _keymint(raw, boot=0),
                }
                store.record_checkin("dev-1", "lab-device-01", second)
                second_obs = store.observe_attestation("dev-1", second)
            finally:
                store.close()
            self.assertEqual(first_obs["status"], "none")
            self.assertEqual(second_obs["status"], "chain_invalid")
            self.assertEqual(second_obs["verifiedBootState"], "Verified")
            log_path.write_text(
                "127.0.0.1 - "
                + format_checkin_log("dev-1", 0, "lab-device-01", "none")
                + "\n127.0.0.1 - "
                + format_checkin_log("dev-1", 0, "lab-device-01", "chain_invalid")
                + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [*CLI, "--db", str(db), "--lab-log", str(log_path)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("attestationStatus chain_invalid", proc.stdout)
        self.assertIn("verifiedBootState Verified", proc.stdout)
        self.assertIn("attestationStatus=chain_invalid", proc.stdout)
        self.assertNotIn("verified boot passed", proc.stdout)
        self.assertNotIn("GrapheneOS", proc.stdout)
        self.assertNotIn("GrapheneOS", proc.stderr)

    def test_forbidden_second_statuses_exit_nonzero(self) -> None:
        cases = {
            "challenge_mismatch": lambda challenge: {
                "deviceId": "dev-1",
                "installedPackages": [],
                "attestation": _keymint(b"other-challenge!!"),
            },
            "missing": lambda challenge: {
                "deviceId": "dev-1",
                "installedPackages": [],
                "attestation": {"format": "none"},
            },
            "parse_error": lambda challenge: {
                "deviceId": "dev-1",
                "installedPackages": [],
                "attestation": {"format": "keymint", "payloadB64": "YQ=="},
            },
            "unsupported": lambda challenge: {
                "deviceId": "dev-1",
                "installedPackages": [],
                "attestation": {"format": "safetyNet", "payloadB64": "YQ=="},
            },
        }
        for status, build in cases.items():
            with self.subTest(status=status):
                proc = self._second_from_challenge(build)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertIn(status, proc.stderr)
                self.assertNotIn("PASS:", proc.stdout)

    def test_none_on_the_second_observation_exits_nonzero(self) -> None:
        # No issued challenge, so assess scores format=none as none, not missing.
        proc = self._run_without_challenge(
            {
                "deviceId": "dev-1",
                "installedPackages": [],
                "attestation": {"format": "none"},
            },
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("attestationStatus none", proc.stderr)

    def test_one_log_line_is_not_a_second_observation(self) -> None:
        # Sqlite holds the second (chain_invalid) row. The log only has the first
        # line. Reading the row without counting would accept it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "fleet.sqlite"
            log_path = root / "lab.log"
            store = FleetStore(db)
            try:
                first = {
                    "deviceId": "dev-1",
                    "installedPackages": [],
                    "attestation": {"format": "none"},
                }
                store.record_checkin("dev-1", "lab-device-01", first)
                store.observe_attestation("dev-1", first)
                challenge = store.issue_challenge("dev-1")
                second = {
                    "deviceId": "dev-1",
                    "installedPackages": [],
                    "attestation": _keymint(base64.b64decode(challenge), boot=0),
                }
                store.record_checkin("dev-1", "lab-device-01", second)
                second_obs = store.observe_attestation("dev-1", second)
            finally:
                store.close()
            self.assertEqual(second_obs["status"], "chain_invalid")
            log_path.write_text(
                "127.0.0.1 - "
                + format_checkin_log("dev-1", 0, "lab-device-01", "none")
                + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [*CLI, "--db", str(db), "--lab-log", str(log_path)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("second observation missing", proc.stderr)
        self.assertNotIn("PASS:", proc.stdout)

    def test_a_third_line_is_not_the_second_observation(self) -> None:
        proc = self._second_from_challenge(
            lambda challenge: {
                "deviceId": "dev-1",
                "installedPackages": [],
                "attestation": _keymint(base64.b64decode(challenge), boot=0),
            },
            third=lambda challenge: {
                "deviceId": "dev-1",
                "installedPackages": [],
                "attestation": _keymint(b"other-challenge!!"),
            },
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("found 3", proc.stderr)

    def test_sqlite_status_must_match_the_second_log_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "fleet.sqlite"
            log_path = root / "lab.log"
            store = FleetStore(db)
            try:
                first = {
                    "deviceId": "dev-1",
                    "installedPackages": [],
                    "attestation": {"format": "none"},
                }
                store.record_checkin("dev-1", "lab-device-01", first)
                store.observe_attestation("dev-1", first)
                challenge = store.issue_challenge("dev-1")
                second = {
                    "deviceId": "dev-1",
                    "installedPackages": [],
                    "attestation": _keymint(base64.b64decode(challenge), boot=0),
                }
                store.record_checkin("dev-1", "lab-device-01", second)
                store.observe_attestation("dev-1", second)
            finally:
                store.close()
            log_path.write_text(
                "127.0.0.1 - "
                + format_checkin_log("dev-1", 0, "lab-device-01", "none")
                + "\n127.0.0.1 - "
                + format_checkin_log("dev-1", 0, "lab-device-01", "challenge_mismatch")
                + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [*CLI, "--db", str(db), "--lab-log", str(log_path)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not the second lab observation", proc.stderr)

    def _second_from_challenge(self, build, third=None) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "fleet.sqlite"
            log_path = root / "lab.log"
            store = FleetStore(db)
            try:
                first = {
                    "deviceId": "dev-1",
                    "installedPackages": [],
                    "attestation": {"format": "none"},
                }
                store.record_checkin("dev-1", "lab-device-01", first)
                first_obs = store.observe_attestation("dev-1", first)
                challenge = store.issue_challenge("dev-1")
                second = build(challenge)
                store.record_checkin("dev-1", "lab-device-01", second)
                second_obs = store.observe_attestation("dev-1", second)
                third_obs = None
                if third is not None:
                    extra = third(challenge)
                    store.record_checkin("dev-1", "lab-device-01", extra)
                    third_obs = store.observe_attestation("dev-1", extra)
            finally:
                store.close()
            lines = [
                format_checkin_log("dev-1", 0, "lab-device-01", first_obs["status"] or ""),
                format_checkin_log("dev-1", 0, "lab-device-01", second_obs["status"] or ""),
            ]
            if third_obs is not None:
                lines.append(
                    format_checkin_log("dev-1", 0, "lab-device-01", third_obs["status"] or "")
                )
            log_path.write_text(
                "".join(f"127.0.0.1 - {line}\n" for line in lines),
                encoding="utf-8",
            )
            return subprocess.run(
                [*CLI, "--db", str(db), "--lab-log", str(log_path)],
                capture_output=True,
                text=True,
                check=False,
            )


if __name__ == "__main__":
    unittest.main()
