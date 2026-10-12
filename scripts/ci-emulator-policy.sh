#!/usr/bin/env bash
# Phase 5 (issue #47) and Phase 6 (issue #49): run the operate script on a
# GitHub-hosted KVM runner, inside reactivecircus/android-emulator-runner.
#
# This is an AOSP ATD emulator (system-images;android-35;aosp_atd;x86_64).
# Not GrapheneOS. Attestation is not asserted. No wipe and no factory reset.
#
# Legs, in order, each with its own OUT under LOGDIR.
# disallowAddUser (token no_add_user), then its post-run state:
#   absent           -> must exit 1 (negative proof)
#   false            -> must exit 1 (negative proof)
#   true-then-false  -> must exit 0 (true applies no_add_user, then a false
#                       check-in with no owner reset clears it)
#   true             -> must exit 0
#   post-run         -> device owner and no_add_user applied
# disallowFactoryReset (token no_factory_reset), then its post-run state:
#   factory-absent           -> must exit 1
#   factory-false            -> must exit 1
#   factory-true-then-false  -> must exit 0 (clears only when
#                               policy_restriction.py prints
#                               "restriction no_factory_reset is not applied")
#   factory-true             -> must exit 0
#   post-run-factory-reset   -> device owner and no_factory_reset applied
#
# The add-user post-run check runs before the factory-reset legs. Those
# legs remove the test-only owner, which drops no_add_user.
#
# The exit code of every leg is asserted here, not inferred. The job fails
# when any assertion fails.
#
# Each leg appends to $GITHUB_STEP_SUMMARY: a restriction line, the
# policy_restriction.py output, the GET /api/devices row, and the PASS or
# FAIL line.
#
# Lab certs are written to /tmp/mdm-certs/<leg>, not under LOGDIR. The
# uploaded artifact is LOGDIR. A cert or key file under LOGDIR fails the
# job. fleet.sqlite* (including -wal/-shm) is deleted before exit: the WAL
# can hold an attestation chain. The workflow also excludes those paths.
#
# CI defaults (override from the environment): SERIAL=emulator-5554,
# ANDROID_ADB_SERVER_PORT=5037 (the runner's adb server), ANDROID_USER_HOME
# =$HOME/.android, GRADLE_BIN=gradle on PATH. The operate script's nimo
# defaults (emulator-5574, 5038, CERTS_DIR=$OUT/certs,
# RESTRICTION=disallowAddUser) are untouched.
#
# Touching $LOGDIR/script-started is the boot-retry marker. The workflow
# retries the emulator step once only when this file was never created.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/emulator-policy-disallow-add-user.sh"
LOGDIR="${LOGDIR:-/tmp/mdm-ci}"
CERTS_ROOT="${CERTS_ROOT:-/tmp/mdm-certs}"
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
# Created only after this script starts. A boot failure never reaches here.
touch "$LOGDIR/script-started"
SUMMARY="$LOGDIR/summary.txt"
: >"$SUMMARY"
FAILED=0

scrub_fleet_sqlite() {
  find "$LOGDIR" -type f -name 'fleet.sqlite*' -delete 2>/dev/null || true
}

cleanup_certs() {
  scrub_fleet_sqlite
  rm -rf "$CERTS_ROOT"
}
trap cleanup_certs EXIT

note() {
  echo "$*" | tee -a "$SUMMARY"
}

append_job_summary() {
  printf '%s\n' "$1" | tee -a "$LOGDIR/job-summary.md"
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    printf '%s\n' "$1" >>"$GITHUB_STEP_SUMMARY"
  fi
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

# Lines from policy_restriction.py, one job-summary line each.
restriction_summary_lines() {
  local file="$1"
  local label="$2"
  local line
  if [ ! -s "$file" ]; then
    printf '%s\n' "${label}: (no output)"
    return 0
  fi
  while IFS= read -r line || [ -n "$line" ]; do
    [ -z "$line" ] && continue
    printf '%s\n' "${label}: ${line}"
  done <"$file"
}

devices_summary_line() {
  local file="$1"
  if [ ! -f "$file" ]; then
    printf '%s\n' "GET /api/devices: not reached"
    return 0
  fi
  python3 - "$file" <<'PY'
import json, sys
path = sys.argv[1]
try:
    doc = json.load(open(path, encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    print(f"GET /api/devices: unreadable ({exc})")
    raise SystemExit(0)
devices = doc.get("devices") if isinstance(doc, dict) else None
if not devices:
    print("GET /api/devices: (empty)")
    raise SystemExit(0)
for device in devices:
    if isinstance(device, dict):
        print("GET /api/devices: " + json.dumps(device, separators=(",", ":")))
PY
}

# job_summary_for_leg <name> <log> <token>
job_summary_for_leg() {
  local name="$1" log="$2" token="$3"
  local out="$LOGDIR/$name"
  local block pf
  block="$(
    printf '%s\n' "### leg ${name}"
    printf '%s\n' "restriction: ${token}"
    restriction_summary_lines "$out/restriction-match.txt" "policy_restriction"
    if [ -f "$out/restriction-after-false.txt" ]; then
      restriction_summary_lines "$out/restriction-after-false.txt" "policy_restriction after false"
    fi
    devices_summary_line "$out/ui-devices.json"
    pf="$(grep -E '^(PASS|FAIL):' "$log" | tail -n 1 || true)"
    if [ -n "$pf" ]; then
      printf '%s\n' "$pf"
    else
      printf '%s\n' "PASS/FAIL: (no PASS or FAIL line)"
    fi
  )"
  append_job_summary "$block"
  append_job_summary ""
}

# run_leg <name> <restriction> <mode> <expected exit> <expected line>
run_leg() {
  local name="$1" restriction="$2" mode="$3" want="$4" line="$5"
  local log="$LOGDIR/$name.log"
  local rc envname token
  case "$restriction" in
    disallowAddUser)
      envname="DISALLOW_ADD_USER"
      token="no_add_user"
      ;;
    disallowFactoryReset)
      envname="DISALLOW_FACTORY_RESET"
      token="no_factory_reset"
      ;;
    *)
      note "ASSERT FAIL: leg $name unknown restriction $restriction"
      FAILED=1
      return 0
      ;;
  esac
  echo "::group::leg $name ($envname=$mode, expect exit $want)"
  rm -rf "$CERTS_ROOT/$name"
  mkdir -p "$CERTS_ROOT/$name"
  env \
    "OUT=$LOGDIR/$name" \
    "RESTRICTION=$restriction" \
    "$envname=$mode" \
    "CERTS_DIR=$CERTS_ROOT/$name" \
    bash "$SCRIPT" 2>&1 | tee "$log"
  rc=${PIPESTATUS[0]}
  echo "::endgroup::"
  collect_device_state "$name"
  job_summary_for_leg "$name" "$log" "$token"
  if [ "$rc" -ne "$want" ]; then
    note "ASSERT FAIL: leg $name $envname=$mode exit=$rc expected=$want"
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
  note "ASSERT OK: leg $name $envname=$mode exit=$rc expected=$want"
  note "  $(grep -F "$line" "$log" | head -n 1)"
}

# assert_post_run <tag> <token>
# tag post-run keeps the Phase 5 assertion text for no_add_user.
assert_post_run() {
  local tag="$1" token="$2"
  local post
  echo "== post-run state ($tag, $token) =="
  collect_device_state "$tag"
  post="$LOGDIR/device-$tag"
  cat "$post/dpm_list_owners.txt"
  if grep -q "$PKG" "$post/dpm_list_owners.txt"; then
    note "ASSERT OK: ${tag} device owner is $PKG"
  else
    note "ASSERT FAIL: ${tag} device owner is not $PKG"
    FAILED=1
  fi
  if python3 "$ROOT/server/policy_restriction.py" --restriction "$token" \
    --device-policy "$post/dumpsys_device_policy.txt" \
    --user "$post/dumpsys_user.txt" >"$post/restriction.txt" 2>&1; then
    cat "$post/restriction.txt"
    note "ASSERT OK: ${tag} ${token} is applied"
  else
    cat "$post/restriction.txt"
    note "ASSERT FAIL: ${tag} ${token} is not applied"
    FAILED=1
  fi
}

note "== emulator policy legs (AOSP ATD emulator, not GrapheneOS; attestation not asserted) =="
note "SERIAL=$SERIAL ANDROID_ADB_SERVER_PORT=$ANDROID_ADB_SERVER_PORT GRADLE_BIN=$GRADLE_BIN UI_PORT=$UI_PORT"
note "CERTS_ROOT=$CERTS_ROOT (not uploaded; LOGDIR=$LOGDIR)"

run_leg absent disallowAddUser absent 1 "FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=absent)"
run_leg false disallowAddUser false 1 "FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=false)"
run_leg true-then-false disallowAddUser true-then-false 0 "PASS: no_add_user applied via disallowAddUser=true, then cleared by disallowAddUser=false with no owner reset"
run_leg true disallowAddUser true 0 "PASS: no_add_user applied via policyFlags.disallowAddUser=true"
assert_post_run post-run no_add_user

run_leg factory-absent disallowFactoryReset absent 1 "FAIL: restriction no_factory_reset not applied (DISALLOW_FACTORY_RESET=absent)"
run_leg factory-false disallowFactoryReset false 1 "FAIL: restriction no_factory_reset not applied (DISALLOW_FACTORY_RESET=false)"
run_leg factory-true-then-false disallowFactoryReset true-then-false 0 "PASS: no_factory_reset applied via disallowFactoryReset=true, then cleared by disallowFactoryReset=false with no owner reset"
run_leg factory-true disallowFactoryReset true 0 "PASS: no_factory_reset applied via policyFlags.disallowFactoryReset=true"
assert_post_run post-run-factory-reset no_factory_reset

echo "== cert material must not sit under the uploaded log dir =="
CERT_HITS="$(find "$LOGDIR" -type f \( \
  -name '*.pem' -o -name '*.p12' -o -name '*.key' -o -name '*.crt' \
  -o -name '*.der' -o -name '*.cer' -o -name '*.pfx' \
  -o -name '*.jks' -o -name '*.keystore' -o -name '*.csr' \
\) -print || true)"
CERT_DIRS="$(find "$LOGDIR" -type d -name certs -print || true)"
if [ -n "$CERT_HITS" ] || [ -n "$CERT_DIRS" ]; then
  printf '%s\n' "$CERT_HITS" "$CERT_DIRS"
  note "ASSERT FAIL: cert or key path under $LOGDIR"
  FAILED=1
else
  note "ASSERT OK: no cert or key file under $LOGDIR"
fi

echo "== fleet sqlite must not be uploaded (WAL can hold an attestation chain) =="
scrub_fleet_sqlite
SQLITE_HITS="$(find "$LOGDIR" -type f -name 'fleet.sqlite*' -print || true)"
if [ -n "$SQLITE_HITS" ]; then
  printf '%s\n' "$SQLITE_HITS"
  note "ASSERT FAIL: fleet.sqlite* still under $LOGDIR"
  FAILED=1
else
  note "ASSERT OK: no fleet.sqlite* under $LOGDIR"
fi

echo "== summary =="
cat "$SUMMARY"
if [ "$FAILED" -ne 0 ]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: PASS (AOSP ATD emulator, not GrapheneOS; attestation not asserted)"
