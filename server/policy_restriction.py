#!/usr/bin/env python3
"""Report whether a user restriction is applied in dumpsys text.

Reads `dumpsys device_policy` and `dumpsys user`. Exits 0 and prints the
matching lines when the restriction is applied. Exits 1 when it is not.

A match is a whole restriction token. `no_add_user` does not match
`no_add_managed_profile`, `no_add_clone_profile`, or `no_add_private_profile`.
A line that sets the token to false is not a match.

dumpsys user evidence is a line inside one of these blocks:

  Effective restrictions:
  Device policy global restrictions:
  Device policy local restrictions:
  Device policy restrictions:

The last header is what Android 15 prints per user. dumpsys device_policy
evidence is a DevicePolicyEngine `UserRestrictionPolicyKey` whose resolved
value is true, or a bundle / assignment such as `no_add_user=true`.
Either file is enough.

  python3 policy_restriction.py --restriction no_add_user \\
      --device-policy device_policy.txt --user dumpsys_user.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Longer headers are matched as whole labels. "Restrictions:" alone is the
# base user bundle and is not one of these blocks.
_BLOCK_HEADERS = (
    "Effective restrictions:",
    "Device policy global restrictions:",
    "Device policy local restrictions:",
    "Device policy restrictions:",
)

_NAME = re.compile(r"^[A-Za-z0-9_]+$")


def applied_lines(device_policy: str, user_dump: str, restriction: str) -> list[str]:
    """Return lines that show `restriction` applied. Empty when it is not."""
    if not _NAME.fullmatch(restriction):
        raise ValueError(f"restriction must be a single token, got {restriction!r}")
    device_policy = _normalize(device_policy)
    user_dump = _normalize(user_dump)
    found: list[str] = []
    seen: set[str] = set()
    for line in _user_block_lines(user_dump, restriction):
        _add(found, seen, line)
    for line in _device_policy_lines(device_policy, restriction):
        _add(found, seen, line)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restriction", required=True)
    parser.add_argument("--device-policy", required=True, type=Path)
    parser.add_argument("--user", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        device_policy = args.device_policy.read_text(encoding="utf-8", errors="replace")
        user_dump = args.user.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"could not read dumpsys file: {exc}", file=sys.stderr)
        return 1
    try:
        lines = applied_lines(device_policy, user_dump, args.restriction)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not lines:
        print(f"restriction {args.restriction} is not applied", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _add(found: list[str], seen: set[str], line: str) -> None:
    cleaned = line.rstrip()
    if cleaned not in seen:
        seen.add(cleaned)
        found.append(cleaned)


def _token(restriction: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(restriction)}(?![A-Za-z0-9_])")


def _assignments(restriction: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(restriction)}(?![A-Za-z0-9_])"
        rf"\s*[=:]\s*(?P<val>(?i:true|false))\b"
    )


def _assignment_state(line: str, restriction: str) -> str | None:
    """'true' or 'false' when this line assigns `restriction`, else None."""
    saw_true = False
    saw_false = False
    for match in _assignments(restriction).finditer(line):
        if match.group("val").lower() == "true":
            saw_true = True
        else:
            saw_false = True
    if saw_true:
        return "true"
    if saw_false:
        return "false"
    return None


def _bare(line: str, restriction: str) -> bool:
    return _token(restriction).search(line) is not None


def _entry_applied(line: str, restriction: str) -> bool:
    state = _assignment_state(line, restriction)
    if state == "false":
        return False
    if state == "true":
        return True
    stripped = line.strip()
    if stripped in {"none", "null", "{}", ""}:
        return False
    return _bare(line, restriction)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _header_rest(stripped: str) -> str | None:
    for header in _BLOCK_HEADERS:
        if stripped == header:
            return ""
        if stripped.startswith(header):
            return stripped[len(header) :].strip()
    return None


def _user_block_lines(text: str, restriction: str) -> list[str]:
    lines = text.splitlines()
    found: list[str] = []
    index = 0
    while index < len(lines):
        raw = lines[index]
        rest = _header_rest(raw.strip())
        if rest is None:
            index += 1
            continue
        if rest and _entry_applied(rest, restriction):
            found.append(raw)
        header_indent = _indent(raw)
        index += 1
        while index < len(lines):
            entry = lines[index]
            if entry.strip() == "":
                index += 1
                continue
            if _indent(entry) <= header_indent:
                break
            if _entry_applied(entry, restriction):
                found.append(entry)
            index += 1
    return found


_POLICY_VALUE = re.compile(r"(?i)(?:mValue\s*=\s*|PolicyValue:\s*)(true|false)\b")


def _block_applied(block: list[str]) -> bool:
    """True when the resolved value in this policy block is true.

    When the block has a "Resolved Policy" section, only that section counts:
    a per-admin true with a resolved null is not applied.
    """
    start = None
    for index, line in enumerate(block):
        if "resolved policy" in line.lower():
            start = index
    scope = block if start is None else block[start:]
    values = [match.group(1).lower() for line in scope for match in _POLICY_VALUE.finditer(line)]
    return bool(values) and values[-1] == "true"


def _policy_key(restriction: str) -> re.Pattern[str]:
    # Android 15 prints "UserRestrictionPolicyKey userRestriction_no_add_user".
    # Older text uses "{ mRestriction= no_add_user }".
    return re.compile(
        rf"UserRestrictionPolicyKey\b.*?(?:(?<![A-Za-z0-9_])|userRestriction_)"
        rf"{re.escape(restriction)}(?![A-Za-z0-9_])"
    )


def _is_next_policy(line: str, key_indent: int) -> bool:
    if line.strip() == "":
        return False
    if _indent(line) <= key_indent:
        return True
    if "UserRestrictionPolicyKey" in line:
        return True
    return False


def _device_policy_lines(text: str, restriction: str) -> list[str]:
    lines = text.splitlines()
    found: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        state = _assignment_state(line, restriction)
        if state == "true":
            found.append(line)
            index += 1
            continue
        if state == "false":
            index += 1
            continue
        if _policy_key(restriction).search(line):
            block = [line]
            key_indent = _indent(line)
            index += 1
            while index < len(lines) and not _is_next_policy(lines[index], key_indent):
                block.append(lines[index])
                index += 1
            if _block_applied(block):
                found.append(block[0])
                for entry in block[1:]:
                    match = _POLICY_VALUE.search(entry)
                    if match and match.group(1).lower() == "true":
                        found.append(entry)
            continue
        index += 1
    return found


if __name__ == "__main__":
    raise SystemExit(main())
