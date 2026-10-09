#!/usr/bin/env bash
# Phase 5 (issue #47): run the Phase 4 operate script on a GitHub-hosted
# KVM runner, inside reactivecircus/android-emulator-runner.
#
# This is an AOSP ATD emulator (system-images;android-35;aosp_atd;x86_64).
# Not GrapheneOS. Attestation is not asserted. No wipe.
#
# Legs, in order, each with its own OUT under LOGDIR:
#   absent           -> must exit 1 (negative proof)
#   false            -> must exit 1 (negative proof)
#   true-then-false  -> must exit 0 (true applies no_add_user, then a false
#                       check-in with no owner reset clears it)
#   true             -> must exit 0 (left as the post-run state)
# Then the post-run state is checked: this app is device owner and
# no_add_user is applied.
#
# The exit code of every leg is asserted here, not inferred. The job fails
# when any assertion fails.
#
# CI defaults (override from the environment): SERIAL=emulator-5554,
# ANDROID_ADB_SERVER_PORT=5037 (the runner's adb server), ANDROID_USER_HOME
# =$HOME/.android, GRADLE_BIN=gradle on PATH. The operate script's nimo
# defaults (emulator-5574, 5038) are untouched.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/emulator-policy-disallow-add-user.sh"
LOGDIR="${LOGDIR:-/tmp/mdm-ci}"
PKG="net.themark.grapheneosmdm"

: "${SERIAL:=emulator-5554}"
: "${ANDROID_ADB_SERVER_PORT:=5037}"
: "${ANDROID_USER_HOME:=$HOME/.android}"
if [ -z "${GRADLE_BIN:-}" ] && command -v gradle >/dev/null 2>&1; then
  GRADLE_BIN="$(command -v gradle)"
fi
: "${GRADLE_BIN:=}"
: "${UI_PORT:=8787}"
export SERIAL ANDROID_ADB_SERVER_PORT ANDROID_USER_HOME GRADLE_BIN UI_PORT

mkdir -p "$LOGDIR"
SUMMARY="$LOGDIR/summary.txt"
: >"$SUMMARY"
FAILED=0

note() {
  echo "$*" | tee -a "$SUMMARY"
}

collect_device_state() {
  local tag="$1"
  local dir="$LOGDIR/device-$tag"
  mkdir -p "$dir"
  adb -s "$SERIAL" logcat -d >"$dir/logcat.txt" 2>&1 || true
  adb -s "$SERIAL" shell dumpsys device_policy >"$dir/dumpsys_device_policy.txt" 2>&1 || true
  adb -s "$SERIAL" shell dumpsys user >"$dir/dumpsys_user.txt" 2>&1 || true
  adb -s "$SERIAL" shell dpm list-owners >"$dir/dpm_list_owners.txt" 2>&1 || true
  adb -s "$SERIAL" shell getprop ro.build.fingerprint >"$dir/fingerprint.txt" 2>&1 || true
}

# run_leg <name> <DISALLOW_ADD_USER> <expected exit> <expected line>
run_leg() {
  local name="$1" mode="$2" want="$3" line="$4"
  local log="$LOGDIR/$name.log"
  local rc
  echo "::group::leg $name (DISALLOW_ADD_USER=$mode, expect exit $want)"
  OUT="$LOGDIR/$name" DISALLOW_ADD_USER="$mode" bash "$SCRIPT" 2>&1 | tee "$log"
  rc=${PIPESTATUS[0]}
  echo "::endgroup::"
  collect_device_state "$name"
  if [ "$rc" -ne "$want" ]; then
    note "ASSERT FAIL: leg $name DISALLOW_ADD_USER=$mode exit=$rc expected=$want"
    FAILED=1
    return 0
  fi
  if ! grep -qF "$line" "$log"; then
    note "ASSERT FAIL: leg $name exit=$rc but log lacks: $line"
    FAILED=1
    return 0
  fi
  if [ "$want" -ne 0 ] && grep -q '^PASS:' "$log"; then
    note "ASSERT FAIL: leg $name is a negative leg but printed PASS"
    FAILED=1
    return 0
  fi
  note "ASSERT OK: leg $name DISALLOW_ADD_USER=$mode exit=$rc expected=$want"
  note "  $(grep -F "$line" "$log" | head -n 1)"
}

note "== Phase 5 emulator policy legs (AOSP ATD emulator, not GrapheneOS; attestation not asserted) =="
note "SERIAL=$SERIAL ANDROID_ADB_SERVER_PORT=$ANDROID_ADB_SERVER_PORT GRADLE_BIN=$GRADLE_BIN UI_PORT=$UI_PORT"

run_leg absent absent 1 "FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=absent)"
run_leg false false 1 "FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=false)"
run_leg true-then-false true-then-false 0 "PASS: no_add_user applied via disallowAddUser=true, then cleared by disallowAddUser=false with no owner reset"
run_leg true true 0 "PASS: no_add_user applied via policyFlags.disallowAddUser=true"

echo "== post-run state =="
collect_device_state post-run
POST="$LOGDIR/device-post-run"
cat "$POST/dpm_list_owners.txt"
if grep -q "$PKG" "$POST/dpm_list_owners.txt"; then
  note "ASSERT OK: post-run device owner is $PKG"
else
  note "ASSERT FAIL: post-run device owner is not $PKG"
  FAILED=1
fi
if python3 "$ROOT/server/policy_restriction.py" --restriction no_add_user \
  --device-policy "$POST/dumpsys_device_policy.txt" \
  --user "$POST/dumpsys_user.txt" >"$POST/restriction.txt" 2>&1; then
  cat "$POST/restriction.txt"
  note "ASSERT OK: post-run no_add_user is applied"
else
  cat "$POST/restriction.txt"
  note "ASSERT FAIL: post-run no_add_user is not applied"
  FAILED=1
fi

echo "== summary =="
cat "$SUMMARY"
if [ "$FAILED" -ne 0 ]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: PASS (AOSP ATD emulator, not GrapheneOS; attestation not asserted)"
