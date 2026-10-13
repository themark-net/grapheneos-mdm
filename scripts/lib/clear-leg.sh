#!/usr/bin/env bash
# Clear-leg gate for the emulator policy operate script.
# Sourced by scripts/emulator-policy-restriction.sh. Not executed directly.
#
# On API 34 and above, a dumpsys counts only when device_policy has an
# anchored "Local Policies:" or "Global Policies:" line and dumpsys user
# has UserInfo{ plus a restriction header. A mid-line mention of those
# headers does not count. API 35 ATD dumps have no DevicePolicyEngine
# line. A line matching '*** SERVICE ... DUMP TIMEOUT' is a failed
# capture on every API level.
#
# CLEAR_LEG_STUB=1 (via run_clear_leg_stub) runs only this gate. It refuses
# to run when the caller set SERIAL or ANDROID_SERIAL, so stub mode cannot
# aim at an adb target. The operate script saves those values before it
# applies the nimo SERIAL default.

if ! declare -F fail >/dev/null 2>&1; then
  fail() {
    echo "FAIL: $*" >&2
    exit 1
  }
fi

_dump_step_prefix() {
  if [ "$1" = "clear" ]; then
    printf '%s' "step clear: after-false"
  else
    printf '%s' "step ${1}:"
  fi
}

# require_api_dumpsys <step> <device_policy_file> <user_dump_file> <api_level>
# step is "clear" or "restriction". Exits through fail() when the capture
# must not be judged as applied or cleared.
require_api_dumpsys() {
  local step="$1" policy_file="$2" user_file="$3" api="$4"
  local prefix
  prefix="$(_dump_step_prefix "$step")"
  case "$api" in
    ''|*[!0-9]*) fail "${prefix} API level is not an integer: ${api}" ;;
  esac
  if [ ! -s "$policy_file" ] || [ ! -s "$user_file" ]; then
    if [ "$step" = "clear" ]; then
      fail "step clear: after-false dumpsys is empty"
    fi
    fail "step ${step}: dumpsys is empty"
  fi
  if grep -q -E '\*\*\* SERVICE .*DUMP TIMEOUT' "$policy_file" "$user_file"; then
    fail "step ${step}: dumpsys contains *** SERVICE ... DUMP TIMEOUT"
  fi
  if [ "$api" -ge 34 ]; then
    if ! grep -q -E '^[[:space:]]*(Local Policies:|Global Policies:)[[:space:]]*$' "$policy_file"; then
      fail "${prefix} device_policy dump lacks a Local Policies or Global Policies section"
    fi
    if ! grep -q -F 'UserInfo{' "$user_file"; then
      fail "${prefix} dumpsys user lacks UserInfo{"
    fi
    if ! grep -q -e 'Effective restrictions:' \
      -e 'Device policy global restrictions:' \
      -e 'Device policy local restrictions:' \
      -e 'Device policy restrictions:' "$user_file"; then
      fail "${prefix} dumpsys user lacks a restriction header"
    fi
    return 0
  fi
  if ! grep -q -e 'DevicePolicyEngine' -e 'UserRestrictionPolicyKey' -e 'Device Owner' -e 'DeviceOwner' "$policy_file"; then
    fail "${prefix} device_policy dump lacks DevicePolicyEngine, UserRestrictionPolicyKey, or Device Owner"
  fi
}

# accept_cleared_restriction <policy> <user> <output> <api_level>
# Uses TOKEN, FLAG_KEY, and ROOT from the caller. Exit 2 from
# policy_restriction.py is an empty or unrecognised dumpsys. Exit 3 is an
# argparse usage error. Neither one is a clear.
accept_cleared_restriction() {
  local policy_file="$1" user_file="$2" out_file="$3" api="$4"
  local rc msg
  require_api_dumpsys clear "$policy_file" "$user_file" "$api"
  set +e
  python3 "$ROOT/server/policy_restriction.py" \
    --restriction "$TOKEN" \
    --device-policy "$policy_file" \
    --user "$user_file" \
    --api-level "$api" \
    >"$out_file" 2>&1
  rc=$?
  set -e
  cat "$out_file"
  if [ "$rc" -eq 3 ]; then
    fail "step clear: policy_restriction.py usage error (exit=3)"
  fi
  if [ "$rc" -eq 2 ]; then
    fail "step clear: policy_restriction.py rejected empty or unrecognised dumpsys (exit=2)"
  fi
  if [ "$rc" -eq 0 ]; then
    fail "step clear: ${TOKEN} still applied after ${FLAG_KEY}=false"
  fi
  if [ "$rc" -ne 1 ]; then
    fail "step clear: policy_restriction.py exit=${rc}, expected 1"
  fi
  msg="restriction ${TOKEN} is not applied"
  if ! grep -qF "$msg" "$out_file"; then
    fail "step clear: policy_restriction.py did not report '${msg}' (exit=${rc})"
  fi
}

# Host-only entry. Caller sets DEVICE_POLICY_FILE, USER_DUMP_FILE, TOKEN,
# FLAG_KEY, ROOT, and optional OUT and API_LEVEL (default 35).
run_clear_leg_stub() {
  if [ -n "${_CALLER_SERIAL:-}" ] || [ -n "${_CALLER_ANDROID_SERIAL:-}" ]; then
    fail "CLEAR_LEG_STUB refused because adb/SERIAL is configured"
  fi
  [ -n "${DEVICE_POLICY_FILE:-}" ] || fail "CLEAR_LEG_STUB requires DEVICE_POLICY_FILE"
  [ -n "${USER_DUMP_FILE:-}" ] || fail "CLEAR_LEG_STUB requires USER_DUMP_FILE"
  local api="${API_LEVEL:-35}"
  mkdir -p "${OUT:-/tmp}"
  accept_cleared_restriction "$DEVICE_POLICY_FILE" "$USER_DUMP_FILE" "${OUT:-/tmp}/restriction-after-false.txt" "$api"
  echo "PASS: clear leg accepted ${TOKEN}"
}
