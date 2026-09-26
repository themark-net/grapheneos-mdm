#!/usr/bin/env python3
"""Attestation challenge check and certificate chain trust."""

from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from attestation import (  # noqa: E402
    assess_attestation,
    chain_trusts_roots,
    inspect_leaf,
    split_der_certs,
)


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


class AttestationTest(unittest.TestCase):
    def test_reads_challenge_and_boot_state(self) -> None:
        challenge = b"abcdefghijklmnop"
        got_challenge, boot = inspect_leaf(_leaf_with_challenge(challenge, boot=0))
        self.assertEqual(got_challenge, challenge)
        self.assertEqual(boot, "Verified")

    def test_status_without_a_real_chain(self) -> None:
        challenge = b"abcdefghijklmnop"
        payload = base64.b64encode(_leaf_with_challenge(challenge)).decode("ascii")
        inventory = {"attestation": {"format": "keymint", "payloadB64": payload}}
        expected = base64.b64encode(challenge).decode("ascii")
        mismatch = assess_attestation(inventory, base64.b64encode(b"other-challenge!!").decode())
        self.assertEqual(mismatch["status"], "challenge_mismatch")
        self.assertEqual(mismatch["verifiedBootState"], "Verified")
        invalid = assess_attestation(inventory, expected)
        self.assertEqual(invalid["status"], "chain_invalid")
        missing = assess_attestation({"attestation": {"format": "none"}}, expected)
        self.assertEqual(missing["status"], "missing")
        first = assess_attestation({"attestation": {"format": "none"}}, None)
        self.assertEqual(first["status"], "none")

    def test_openssl_trusts_only_the_given_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ca_key = root / "ca.key"
            ca_pem = root / "ca.pem"
            leaf_key = root / "leaf.key"
            leaf_csr = root / "leaf.csr"
            leaf_pem = root / "leaf.pem"
            other_pem = root / "other.pem"
            subprocess.check_call(
                [
                    "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", str(ca_key), "-out", str(ca_pem), "-days", "1",
                    "-subj", "/CN=TestAttestRoot",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.check_call(
                [
                    "openssl", "req", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", str(leaf_key), "-out", str(leaf_csr),
                    "-subj", "/CN=leaf",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.check_call(
                [
                    "openssl", "x509", "-req", "-in", str(leaf_csr),
                    "-CA", str(ca_pem), "-CAkey", str(ca_key), "-CAcreateserial",
                    "-out", str(leaf_pem), "-days", "1",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.check_call(
                [
                    "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", str(root / "other.key"), "-out", str(other_pem),
                    "-days", "1", "-subj", "/CN=OtherRoot",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            leaf_der = subprocess.check_output(
                ["openssl", "x509", "-in", str(leaf_pem), "-outform", "DER"]
            )
            certs = split_der_certs(leaf_der)
            self.assertTrue(chain_trusts_roots(certs, ca_pem))
            self.assertFalse(chain_trusts_roots(certs, other_pem))


if __name__ == "__main__":
    unittest.main()
