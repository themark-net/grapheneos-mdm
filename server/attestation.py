#!/usr/bin/env python3
"""Check a keymint attestation payload against the challenge this server issued.

`payloadB64` is concatenated DER certificates, leaf first. The leaf carries
the Android key-attestation extension. The chain must sign up to a root in
`attestation-roots.pem`. Certificate expiry is not checked: factory
attestation keys that chain to the Google root stay trusted after notAfter.
"""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOTS_PEM = Path(__file__).with_name("attestation-roots.pem")
# 1.3.6.1.4.1.11129.2.1.17
_ATTESTATION_OID = bytes.fromhex("060a2b06010401d679020111")
_BOOT = {0: "Verified", 1: "SelfSigned", 2: "Unverified", 3: "Failed"}


def assess_attestation(
    inventory: dict[str, Any],
    expected_challenge_b64: str | None,
    roots_pem: Path = ROOTS_PEM,
) -> dict[str, str | None]:
    """Return status and verifiedBootState. Does not reject the check-in."""
    attestation = inventory.get("attestation") if isinstance(inventory, dict) else None
    if not isinstance(attestation, dict):
        attestation = {}
    fmt = attestation.get("format") or "none"
    if fmt == "none":
        status = "missing" if expected_challenge_b64 else "none"
        return {"status": status, "verifiedBootState": None}
    if fmt != "keymint":
        return {"status": "unsupported", "verifiedBootState": None}
    payload_b64 = attestation.get("payloadB64")
    if not isinstance(payload_b64, str) or not payload_b64:
        return {"status": "parse_error", "verifiedBootState": None}
    try:
        payload = base64.b64decode(payload_b64, validate=False)
        certs = split_der_certs(payload)
        challenge, boot = inspect_leaf(certs[0])
    except (ValueError, IndexError):
        return {"status": "parse_error", "verifiedBootState": None}
    expected = _decode_challenge(expected_challenge_b64)
    if expected is None or challenge != expected:
        return {"status": "challenge_mismatch", "verifiedBootState": boot}
    if not chain_trusts_roots(certs, roots_pem):
        return {"status": "chain_invalid", "verifiedBootState": boot}
    if boot != "Verified":
        return {"status": "boot_unverified", "verifiedBootState": boot}
    return {"status": "ok", "verifiedBootState": boot}


def split_der_certs(blob: bytes) -> list[bytes]:
    certs: list[bytes] = []
    i = 0
    while i < len(blob):
        if blob[i] != 0x30:
            raise ValueError("expected a certificate SEQUENCE")
        nxt = _end_of_tlv(blob, i)
        certs.append(blob[i:nxt])
        i = nxt
    if not certs:
        raise ValueError("empty certificate payload")
    return certs


def inspect_leaf(cert_der: bytes) -> tuple[bytes, str | None]:
    """Return (attestation challenge, verified boot state) from a leaf cert."""
    idx = cert_der.find(_ATTESTATION_OID)
    if idx < 0:
        raise ValueError("key attestation extension missing")
    i = idx + len(_ATTESTATION_OID)
    if i < len(cert_der) and cert_der[i] == 0x01:
        i = _end_of_tlv(cert_der, i)
    if i >= len(cert_der) or cert_der[i] != 0x04:
        raise ValueError("attestation extension value missing")
    value = _tlv_value(cert_der, i)
    return _parse_key_description(value)


def chain_trusts_roots(certs: list[bytes], roots_pem: Path) -> bool:
    if not certs or not roots_pem.is_file():
        return False
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        leaf = root / "leaf.pem"
        leaf.write_text(_der_to_pem(certs[0]), encoding="ascii")
        cmd = [
            "openssl",
            "verify",
            "-no_check_time",
            "-CAfile",
            str(roots_pem),
        ]
        if len(certs) > 1:
            untrusted = root / "untrusted.pem"
            untrusted.write_text(
                "".join(_der_to_pem(cert) for cert in certs[1:]),
                encoding="ascii",
            )
            cmd.extend(["-untrusted", str(untrusted)])
        cmd.append(str(leaf))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode == 0


def _decode_challenge(value: str | None) -> bytes | None:
    if not value:
        return None
    try:
        raw = base64.b64decode(value, validate=False)
    except ValueError:
        return None
    return raw or None


def _parse_key_description(der: bytes) -> tuple[bytes, str | None]:
    if not der or der[0] != 0x30:
        raise ValueError("KeyDescription is not a SEQUENCE")
    body = _tlv_value(der, 0)
    fields: list[tuple[int, bytes]] = []
    i = 0
    while i < len(body):
        tag = body[i]
        nxt = _end_of_tlv(body, i)
        fields.append((tag, _tlv_value(body, i)))
        i = nxt
    if len(fields) < 5 or fields[4][0] != 0x04:
        raise ValueError("attestation challenge missing")
    return fields[4][1], _boot_state(der)


def _boot_state(der: bytes) -> str | None:
    found = _find_context(der, 0, len(der), 704)
    if found is None:
        return None
    start, end = found
    if start < end and der[start] == 0x30:
        start, end = _value_span(der, start)
    # verifiedBootKey, deviceLocked, verifiedBootState
    i = start
    for _ in range(2):
        if i >= end:
            return None
        i = _end_of_tlv(der, i)
    if i >= end or der[i] != 0x02:
        return None
    raw = _tlv_value(der, i)
    if not raw or len(raw) > 4:
        return None
    code = int.from_bytes(raw, "big")
    return _BOOT.get(code)


def _find_context(der: bytes, start: int, end: int, number: int) -> tuple[int, int] | None:
    i = start
    while i < end:
        tag, header = _read_tag(der, i)
        klass, constructed, num = tag
        length, len_len = _read_len(der, i + header)
        value = i + header + len_len
        nxt = value + length
        if nxt > end:
            raise ValueError("truncated DER")
        if klass == 2 and num == number:
            return value, nxt
        if constructed:
            found = _find_context(der, value, nxt, number)
            if found is not None:
                return found
        i = nxt
    return None


def _value_span(der: bytes, i: int) -> tuple[int, int]:
    _tag, header = _read_tag(der, i)
    length, len_len = _read_len(der, i + header)
    value = i + header + len_len
    return value, value + length


def _tlv_value(der: bytes, i: int) -> bytes:
    start, end = _value_span(der, i)
    return der[start:end]


def _end_of_tlv(der: bytes, i: int) -> int:
    _tag, header = _read_tag(der, i)
    length, len_len = _read_len(der, i + header)
    nxt = i + header + len_len + length
    if nxt > len(der):
        raise ValueError("truncated DER")
    return nxt


def _read_tag(der: bytes, i: int) -> tuple[tuple[int, bool, int], int]:
    if i >= len(der):
        raise ValueError("truncated tag")
    first = der[i]
    klass = first >> 6
    constructed = bool(first & 0x20)
    number = first & 0x1F
    header = 1
    if number == 0x1F:
        number = 0
        while True:
            if i + header >= len(der) or header > 4:
                raise ValueError("truncated high tag")
            nxt = der[i + header]
            header += 1
            number = (number << 7) | (nxt & 0x7F)
            if nxt & 0x80 == 0:
                break
    return (klass, constructed, number), header


def _read_len(der: bytes, i: int) -> tuple[int, int]:
    if i >= len(der):
        raise ValueError("truncated length")
    first = der[i]
    if first & 0x80 == 0:
        return first, 1
    count = first & 0x7F
    if count == 0 or count > 3 or i + count >= len(der):
        raise ValueError("bad length")
    length = 0
    for k in range(1, count + 1):
        length = (length << 8) | der[i + k]
    return length, 1 + count


def _der_to_pem(der: bytes) -> str:
    body = base64.encodebytes(der).decode("ascii")
    return f"-----BEGIN CERTIFICATE-----\n{body}-----END CERTIFICATE-----\n"
