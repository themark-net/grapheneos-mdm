#!/usr/bin/env bash
# Phase 4 (issue #45): disallowAddUser on the AOSP ATD emulator, then the
# localhost operator list.
#
# This is an AOSP ATD emulator (system-images;android-35;aosp_atd;x86_64).
# Not GrapheneOS. Issue #8 stays closed. Attestation is not asserted.
# verified boot is not claimed. Draft PR #42 is not touched.
#
# DISALLOW_ADD_USER=true|false|absent|true-then-false (default true)
# chooses policyFlags. true sets disallowAddUser true. false sets it false.
# absent sends {}. true-then-false (Phase 5) applies true exactly like the
# true mode, then, with no owner reset and no pm clear, sets a per-device
# override {"disallowAddUser": false} in the same sqlite, broadcasts a
# second check-in, and requires no_add_user to be gone
# (clearUserRestriction). Anything else exits before the emulator is
# touched.
#
# Environment overrides (nimo defaults in brackets): SERIAL [emulator-5574],
# ANDROID_ADB_SERVER_PORT [5038], AVD [mdm36], CONSOLE_PORT/ADB_PORT
# [5574/5575], GRADLE_BIN [unset], OUT [/tmp/mdm-phase4-policy],
# PORT [8443], UI_PORT [8787]. GitHub Actions sets SERIAL=emulator-5554 and
# ANDROID_ADB_SERVER_PORT=5037 through scripts/ci-emulator-policy.sh.
#
# The log record order is enroll (set-device-owner), check-in, restriction,
# operator list. One lab broadcast (two in true-then-false). No wipe, no -wipe-data, no factory reset.
# The script does not stop the emulator.
#
# How this can fail / recover:
# - Restriction not applied: exit non-zero naming that step
#   (FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=<mode>)).
#   Read PolicyManager logcat for the policyFlags parse and the line
#   "Desired state policy flags applied". Fix the desired.json flag or the
#   device-owner state, then run again. Do not claim the restriction applied.
# - Port UI_PORT (default 8787) busy, or the UI bound to 0.0.0.0, *, or ::
#   : the script exits non-zero.
#   Never bind ui_server.py off 127.0.0.1. Free UI_PORT and run again.
# - Emulator or KVM unavailable: that is a host blocker. Exit and keep the
#   emulator log. Do not install qemu. Do not boot a second emulator when
#   one is already on ports 5574,5575. Do not fake a PASS.
# - DISALLOW_ADD_USER=false or absent is expected to FAIL. That is the
#   negative proof: the restriction is not applied, so the script stops at
#   the restriction step and does not print PASS.
# - true-then-false: if no_add_user is still applied after the false
#   check-in, exit non-zero with
#   FAIL: step clear: no_add_user still applied after disallowAddUser=false.
# - Post-run state: after a true run the emulator is left with this app as
#   device owner and no_add_user set. After true-then-false the app is still
#   device owner and no_add_user is cleared. The next run removes the
#   test-only owner, which drops its restrictions.
# - A device-owner package rejects pm clear. assembleDebug is not testOnly
#   unless -Pandroid.injected.testOnly=true, and dpm remove-active-admin
#   rejects a non-test owner. The testOnly bit is stored when the admin is
#   first set. If remove still says non-test admin, stop the framework and
#   delete device_owner_2.xml and device_policies.xml (not a factory reset),
#   then start the framework, pm clear, and set device owner again.
# - dpm set-device-owner rejected: print the command output and exit.
#   Do not factory-reset.
# - set-device-owner enqueues an immediate check-in before the lab URL is
#   set. force-stop after set-device-owner cancels that worker so this run
#   has one broadcast check-in.
# - Lab cert SAN is only DNS:localhost and IP:127.0.0.1. 10.0.2.2 fails TLS.
#   Use adb reverse so the guest calls https://127.0.0.1:8443. If reverse
#   fails, exit. Do not fall back to 10.0.2.2.
# - OpenSSL 3's default AES PKCS#12 throws "password empty" on Android
#   even with -passout pass:. Re-export client.p12 with
#   openssl pkcs12 -legacy (password still empty).
# - The example desired state names a placeholder APK. This script serves
#   an empty package list and a noop command so a hash mismatch is not a
#   failure. The noop command is not a wipe.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEFAULT_SDK="$(cd "$ROOT/../android-sdk" 2>/dev/null && pwd || true)"
: "${ANDROID_HOME:=${DEFAULT_SDK}}"
: "${JAVA_HOME:=$ANDROID_HOME/jdk}"
: "${ANDROID_SDK_ROOT:=$ANDROID_HOME}"
: "${ANDROID_AVD_HOME:=$ANDROID_HOME/avd}"
: "${ANDROID_USER_HOME:=$ANDROID_HOME/user-home}"
: "${ANDROID_ADB_SERVER_PORT:=5038}"
: "${GRADLE_BIN:=}"
export ANDROID_HOME JAVA_HOME ANDROID_SDK_ROOT ANDROID_AVD_HOME ANDROID_USER_HOME ANDROID_ADB_SERVER_PORT
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

SERIAL="${SERIAL:-emulator-5574}"
AVD="${AVD:-mdm36}"
CONSOLE_PORT="${CONSOLE_PORT:-5574}"
ADB_PORT="${ADB_PORT:-5575}"
COMPONENT="net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver"
PKG="net.themark.grapheneosmdm"
OUT="${OUT:-/tmp/mdm-phase4-policy}"
PORT="${PORT:-8443}"
LAB_URL="https://127.0.0.1:${PORT}"
UI_PORT="${UI_PORT:-8787}"
MODE="${DISALLOW_ADD_USER:-true}"
LAB_PID=""
UI_PID=""

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

case "$MODE" in
  true|false|absent|true-then-false) ;;
  *) fail "DISALLOW_ADD_USER must be true, false, absent, or true-then-false (got: ${MODE})" ;;
esac

[ -n "$ANDROID_HOME" ] && [ -d "$ANDROID_HOME" ] || fail "ANDROID_HOME is not a directory"
[ -x "$JAVA_HOME/bin/java" ] || fail "JAVA_HOME has no java: $JAVA_HOME"
[ -x "$ANDROID_HOME/platform-tools/adb" ] || fail "user-space adb missing"
case "$(command -v adb)" in
  "$ANDROID_HOME"/*) ;;
  *) fail "adb is not the user-space SDK adb: $(command -v adb)" ;;
esac
need python3
need openssl
need curl
need ss
need timeout

mkdir -p "$OUT"
rm -f "$OUT/result.txt"
exec > >(tee -a "$OUT/result.txt") 2>&1

echo "== phase 4 disallowAddUser on the operator page =="
echo "ROOT=$ROOT"
echo "ANDROID_HOME=$ANDROID_HOME"
echo "JAVA_HOME=$JAVA_HOME"
echo "ANDROID_ADB_SERVER_PORT=$ANDROID_ADB_SERVER_PORT"
echo "SERIAL=$SERIAL"
echo "DISALLOW_ADD_USER=$MODE"
echo "UI_PORT=$UI_PORT"
echo "OUT=$OUT"

ensure_emulator() {
  if adb -s "$SERIAL" get-state 2>/dev/null | grep -qx device; then
    echo "emulator already online: $SERIAL"
    return 0
  fi
  echo "emulator $SERIAL is not online; restart once"
  if adb devices | awk 'NR>1 && $1 ~ /^emulator-/ && $2=="device" {print $1}' | grep -qx "$SERIAL"; then
    fail "serial listed but get-state failed"
  fi
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "(^|:)${CONSOLE_PORT}$"; then
    fail "port $CONSOLE_PORT is already bound; not starting a second emulator"
  fi
  local bin="$ANDROID_HOME/emulator/emulator"
  [ -x "$bin" ] || fail "user-space emulator binary missing: $bin"
  case "$bin" in
    "$ANDROID_HOME"/*) ;;
    *) fail "refusing emulator outside ANDROID_HOME: $bin" ;;
  esac
  "$bin" -avd "$AVD" \
    -no-window -no-audio -no-boot-anim -no-snapshot \
    -gpu swiftshader_indirect -accel on \
    -ports "$CONSOLE_PORT,$ADB_PORT" \
    >"$OUT/emulator.log" 2>&1 &
  echo $! >"$OUT/emulator.pid"
  local i
  for i in $(seq 1 90); do
    if adb -s "$SERIAL" get-state 2>/dev/null | grep -qx device \
      && [ "$(adb -s "$SERIAL" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; then
      echo "emulator restarted and boot completed"
      return 0
    fi
    if ! kill -0 "$(cat "$OUT/emulator.pid")" 2>/dev/null; then
      echo "---- emulator log ----"
      cat "$OUT/emulator.log" || true
      fail "emulator process exited before boot"
    fi
    sleep 2
  done
  echo "---- emulator log (tail) ----"
  tail -n 80 "$OUT/emulator.log" || true
  fail "emulator did not finish boot"
}

wait_for_shell() {
  local i
  adb -s "$SERIAL" wait-for-device
  for i in $(seq 1 30); do
    if [ "$(adb -s "$SERIAL" shell echo ok 2>/dev/null | tr -d '\r')" = "ok" ]; then
      return 0
    fi
    sleep 1
  done
  fail "adb shell did not answer after adb root"
}

clear_persisted_nontest_owner() {
  local i zygote left boot
  echo "== userdebug: persisted testOnlyAdmin is false; drop owner files =="
  set +e
  echo "$(adb -s "$SERIAL" root 2>&1)"
  set -e
  wait_for_shell
  timeout 45 adb -s "$SERIAL" shell stop || echo "stop exit=$?"
  zygote=""
  for i in $(seq 1 30); do
    zygote="$(adb -s "$SERIAL" shell getprop init.svc.zygote 2>/dev/null | tr -d '\r' || true)"
    echo "zygote=${zygote}"
    if [ "$zygote" = "stopped" ] || [ -z "$zygote" ]; then
      break
    fi
    sleep 1
  done
  if [ "$zygote" != "stopped" ] && [ -n "$zygote" ]; then
    fail "zygote did not stop (state=${zygote}); not deleting device owner files"
  fi
  adb -s "$SERIAL" shell rm -f /data/system/device_owner_2.xml /data/system/device_policies.xml
  left="$(adb -s "$SERIAL" shell 'ls /data/system/device_owner_2.xml /data/system/device_policies.xml 2>/dev/null' | tr -d '\r' || true)"
  if [ -n "$left" ]; then
    fail "device owner files still present after delete: $left"
  fi
  echo "device owner files removed"
  adb -s "$SERIAL" shell start
  # sys.boot_completed often stays 1 across stop/start on this image.
  # Zygote was stopped; wait until it is running and dpm answers.
  for i in $(seq 1 90); do
    zygote="$(adb -s "$SERIAL" shell getprop init.svc.zygote 2>/dev/null | tr -d '\r' || true)"
    boot="$(adb -s "$SERIAL" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
    if [ "$zygote" = "running" ] && [ "$boot" = "1" ]; then
      if adb -s "$SERIAL" shell dpm list-owners >/dev/null 2>&1; then
        echo "framework restarted"
        return 0
      fi
    fi
    sleep 2
  done
  fail "framework did not finish boot after clearing device owner"
}

remove_our_owner() {
  local owners rm_out rm_rc
  owners="$(adb -s "$SERIAL" shell dpm list-owners 2>&1 | tr -d '\r' || true)"
  echo "$owners"
  if ! printf '%s\n' "$owners" | grep -q "$PKG"; then
    echo "device owner is not $PKG"
    return 0
  fi
  echo "== remove-active-admin so pm clear can run =="
  set +e
  rm_out="$(adb -s "$SERIAL" shell dpm remove-active-admin "$COMPONENT" 2>&1)"
  rm_rc=$?
  set -e
  echo "$rm_out"
  echo "remove-active-admin exit=$rm_rc"
  if [ "$rm_rc" -ne 0 ]; then
    if printf '%s\n' "$rm_out" | grep -q "non-test admin"; then
      clear_persisted_nontest_owner
    else
      fail "could not remove device owner before pm clear: $rm_out"
    fi
  fi
  owners="$(adb -s "$SERIAL" shell dpm list-owners 2>&1 | tr -d '\r' || true)"
  echo "$owners"
  if printf '%s\n' "$owners" | grep -q "$PKG"; then
    fail "device owner is still $PKG after removal"
  fi
}

checkin_count() {
  local n
  if [ ! -f "$OUT/lab.log" ]; then
    printf '0'
    return 0
  fi
  n="$(grep -c "check-in deviceId=" "$OUT/lab.log" || true)"
  printf '%s' "${n:-0}"
}

outcome_count() {
  local n
  n="$(adb -s "$SERIAL" logcat -d -s LabServerConfig:I 2>/dev/null | grep -c "lab-checkin outcome=SUCCESS" || true)"
  n="$(printf '%s' "$n" | tr -d '\r')"
  printf '%s' "${n:-0}"
}

wait_for_n() {
  local label="$1"
  local want="$2"
  local reader="$3"
  local i n
  for i in $(seq 1 90); do
    n="$($reader)"
    if [ "$n" -ge "$want" ]; then
      echo "$label=$n"
      return 0
    fi
    if [ -n "${LAB_PID:-}" ] && ! kill -0 "$LAB_PID" 2>/dev/null; then
      echo "---- lab log ----"
      cat "$OUT/lab.log" || true
      fail "lab server exited while waiting for $label >= $want"
    fi
    sleep 1
  done
  echo "---- lab log ----"
  cat "$OUT/lab.log" || true
  echo "---- logcat (LabServerConfig / CheckInRunner / PolicyManager) ----"
  adb -s "$SERIAL" logcat -d -s LabServerConfig:I CheckInRunner:D ApiClient:I MtlsMaterialLoader:W AndroidRuntime:E PolicyManager:D || true
  fail "timed out waiting for $label >= $want (saw $($reader))"
}

wait_for_policy_applied() {
  local want="${1:-1}"
  local i hit n
  for i in $(seq 1 60); do
    hit="$(adb -s "$SERIAL" logcat -d -s PolicyManager:D 2>/dev/null | tr -d '\r' | grep -F "Desired state policy flags applied" || true)"
    n="$(printf '%s\n' "$hit" | grep -c . || true)"
    if [ "${n:-0}" -ge "$want" ]; then
      echo "$hit"
      return 0
    fi
    sleep 1
  done
  echo "---- logcat (PolicyManager / CheckInRunner / LabServerConfig) ----"
  adb -s "$SERIAL" logcat -d -s PolicyManager:D CheckInRunner:D LabServerConfig:I || true
  fail "step policy-flags: PolicyManager logcat has fewer than ${want} 'Desired state policy flags applied'"
}

broadcast_lab() {
  local label="$1"
  local bc_out bc_rc
  echo "== broadcast lab URL ($label) =="
  set +e
  bc_out="$(adb -s "$SERIAL" shell am broadcast -f 32 \
    -a net.themark.grapheneosmdm.action.SET_LAB_SERVER \
    -n "$PKG/.lab.LabServerConfigReceiver" \
    --es serverBaseUrl "$LAB_URL" 2>&1)"
  bc_rc=$?
  set -e
  echo "$bc_out"
  echo "am broadcast exit=$bc_rc"
  [ "$bc_rc" -eq 0 ] || fail "lab broadcast failed ($label): $bc_out"
}

listeners_ui_port() {
  ss -ltn 2>/dev/null | awk -v want="$UI_PORT" '$1 == "LISTEN" {
    addr = $4
    port = addr
    sub(/^.*:/, "", port)
    if (port == want) print addr
  }'
}

cleanup() {
  if [ -n "${LAB_PID:-}" ] && kill -0 "$LAB_PID" 2>/dev/null; then
    kill "$LAB_PID" 2>/dev/null || true
    wait "$LAB_PID" 2>/dev/null || true
  fi
  if [ -n "${UI_PID:-}" ] && kill -0 "$UI_PID" 2>/dev/null; then
    kill "$UI_PID" 2>/dev/null || true
    wait "$UI_PID" 2>/dev/null || true
  fi
  # Do not stop the emulator.
  timeout 15 adb -s "$SERIAL" reverse --remove "tcp:${PORT}" >/dev/null 2>&1 || true
}

ensure_emulator

FINGERPRINT="$(adb -s "$SERIAL" shell getprop ro.build.fingerprint | tr -d '\r')"
echo "fingerprint=$FINGERPRINT"
case "$FINGERPRINT" in
  *Graphene*|*graphene*) fail "refusing GrapheneOS image: $FINGERPRINT" ;;
esac
case "$FINGERPRINT" in
  Android/sdk_slim_x86_64/emu64x:15/*) ;;
  *) fail "expected AOSP ATD Android 15 fingerprint, got: $FINGERPRINT" ;;
esac
echo "model=$(adb -s "$SERIAL" shell getprop ro.product.model | tr -d '\r')"

if [ ! -f "$ROOT/local.properties" ]; then
  printf 'sdk.dir=%s\n' "$ANDROID_HOME" >"$ROOT/local.properties"
  echo "wrote gitignored local.properties sdk.dir"
else
  echo "local.properties already present; leaving it"
fi

if [ -x "$ROOT/gradlew" ]; then
  GRADLE=("$ROOT/gradlew")
elif [ -n "$GRADLE_BIN" ]; then
  GRADLE=("$GRADLE_BIN")
elif command -v gradle >/dev/null 2>&1; then
  GRADLE=(gradle)
else
  fail "no gradlew, GRADLE_BIN, or gradle on PATH"
fi
echo "gradle=${GRADLE[*]}"
# assembleDebug is not testOnly unless this property is set. dpm
# remove-active-admin rejects a non-test device owner, so pm clear
# cannot run while this package is still owner. The testOnly bit is
# stored when the admin is first set.
"${GRADLE[@]}" --no-daemon --console=plain :app:assembleDebug \
  -Pandroid.injected.testOnly=true \
  -Dorg.gradle.java.home="$JAVA_HOME"

APK="$ROOT/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK" ] || fail "debug APK missing: $APK"

echo "== install testOnly debug APK, then drop any previous device owner =="
adb -s "$SERIAL" install -r -t -d "$APK"
remove_our_owner

echo "== pm clear $PKG =="
set +e
CLEAR_OUT="$(adb -s "$SERIAL" shell pm clear "$PKG" 2>&1)"
CLEAR_RC=$?
set -e
echo "$CLEAR_OUT"
echo "pm clear exit=$CLEAR_RC"
[ "$CLEAR_RC" -eq 0 ] || fail "pm clear failed: $CLEAR_OUT"
printf '%s\n' "$CLEAR_OUT" | tr -d '\r' | grep -q "Success" || fail "pm clear did not report Success: $CLEAR_OUT"

echo "== mTLS material into app_mtls =="
rm -rf "$OUT/certs"
bash "$ROOT/server/gen-lab-certs.sh" "$OUT/certs"
openssl pkcs12 -export -legacy -name lab-device-01 \
  -out "$OUT/certs/client.p12" \
  -inkey "$OUT/certs/client-key.pem" \
  -in "$OUT/certs/client.pem" \
  -certfile "$OUT/certs/ca.pem" \
  -passout pass:
case "$MODE" in
  true|true-then-false) FLAGS='{"disallowAddUser": true}' ;;
  false) FLAGS='{"disallowAddUser": false}' ;;
  absent) FLAGS='{}' ;;
esac
cat >"$OUT/desired.json" <<JSON
{
  "schemaVersion": 1,
  "requiredPackages": [],
  "policyFlags": $FLAGS,
  "commands": [{"type": "noop", "id": "emulator-phase4"}]
}
JSON
echo "== desired.json =="
cat "$OUT/desired.json"
adb -s "$SERIAL" push "$OUT/certs/client.p12" /data/local/tmp/mdm-phase4-client.p12
adb -s "$SERIAL" push "$OUT/certs/ca.pem" /data/local/tmp/mdm-phase4-ca.pem
adb -s "$SERIAL" shell chmod 644 /data/local/tmp/mdm-phase4-client.p12 /data/local/tmp/mdm-phase4-ca.pem
adb -s "$SERIAL" shell run-as "$PKG" mkdir -p app_mtls
adb -s "$SERIAL" shell run-as "$PKG" cp /data/local/tmp/mdm-phase4-client.p12 app_mtls/client.p12
adb -s "$SERIAL" shell run-as "$PKG" cp /data/local/tmp/mdm-phase4-ca.pem app_mtls/ca.pem
adb -s "$SERIAL" shell rm -f /data/local/tmp/mdm-phase4-client.p12 /data/local/tmp/mdm-phase4-ca.pem
echo "-- app_mtls --"
adb -s "$SERIAL" shell run-as "$PKG" ls -l app_mtls
P12_SIZE="$(adb -s "$SERIAL" shell run-as "$PKG" wc -c app_mtls/client.p12 | awk '{print $1}' | tr -d '\r')"
CA_SIZE="$(adb -s "$SERIAL" shell run-as "$PKG" wc -c app_mtls/ca.pem | awk '{print $1}' | tr -d '\r')"
[ "${P12_SIZE:-0}" -gt 0 ] || fail "client.p12 missing in app_mtls"
[ "${CA_SIZE:-0}" -gt 0 ] || fail "ca.pem missing in app_mtls"

echo "== enroll (set-device-owner) =="
set +e
SET_OUT="$(adb -s "$SERIAL" shell dpm set-device-owner "$COMPONENT" 2>&1)"
SET_RC=$?
set -e
echo "$SET_OUT"
echo "set-device-owner exit=$SET_RC"
[ "$SET_RC" -eq 0 ] || fail "set-device-owner failed: $SET_OUT"

echo "== list-owners =="
OWNERS="$(adb -s "$SERIAL" shell dpm list-owners 2>&1 | tr -d '\r')"
echo "$OWNERS"
echo "$OWNERS" | grep -q "DeviceAdminReceiver" || fail "list-owners does not name DeviceAdminReceiver"
echo "$OWNERS" | grep -q "$PKG" || fail "list-owners does not name $PKG"

echo "== dumpsys device_policy (owner lines) =="
adb -s "$SERIAL" shell dumpsys device_policy >"$OUT/device_policy.txt"
grep -n -E "Device Owner|device owner|DeviceAdminReceiver|${PKG}" "$OUT/device_policy.txt" | head -n 40
grep -q "DeviceAdminReceiver" "$OUT/device_policy.txt" || fail "dumpsys device_policy has no DeviceAdminReceiver"

echo "== force-stop (drop admin_enabled check-in; URL is not set yet) =="
sleep 2
adb -s "$SERIAL" shell am force-stop "$PKG" || true

echo "== check-in =="
trap cleanup EXIT
echo "== lab server (new sqlite) =="
rm -f "$OUT/fleet.sqlite" "$OUT/fleet.sqlite-wal" "$OUT/fleet.sqlite-shm" "$OUT/lab.log"
python3 "$ROOT/server/lab_checkin.py" \
  --certs "$OUT/certs" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --desired "$OUT/desired.json" \
  --db "$OUT/fleet.sqlite" \
  >"$OUT/lab.log" 2>&1 &
LAB_PID=$!
for _ in $(seq 1 25); do
  if grep -q "lab check-in listening" "$OUT/lab.log" 2>/dev/null; then
    break
  fi
  if ! kill -0 "$LAB_PID" 2>/dev/null; then
    echo "---- lab log ----"
    cat "$OUT/lab.log" || true
    fail "lab server exited"
  fi
  sleep 0.2
done
grep -q "lab check-in listening" "$OUT/lab.log" || fail "lab server did not listen"
echo "---- lab listen line ----"
grep "lab check-in listening" "$OUT/lab.log"

echo "== adb reverse =="
set +e
REV_OUT="$(adb -s "$SERIAL" reverse tcp:"$PORT" tcp:"$PORT" 2>&1)"
REV_RC=$?
set -e
echo "$REV_OUT"
echo "adb reverse exit=$REV_RC"
[ "$REV_RC" -eq 0 ] || fail "adb reverse failed: $REV_OUT"
echo "-- reverse --list --"
adb -s "$SERIAL" reverse --list
adb -s "$SERIAL" reverse --list | grep -q "tcp:${PORT} tcp:${PORT}" || fail "reverse list missing tcp:${PORT}"

adb -s "$SERIAL" logcat -c || true
broadcast_lab "once"
wait_for_n "lab-checkin SUCCESS" 1 outcome_count
wait_for_n "check-in lines" 1 checkin_count
wait_for_policy_applied

echo "---- lab log ----"
cat "$OUT/lab.log" || true
echo "---- logcat (LabServerConfig / CheckInRunner / PolicyManager) ----"
adb -s "$SERIAL" logcat -d -s LabServerConfig:I CheckInRunner:D ApiClient:I MtlsMaterialLoader:W AndroidRuntime:E PolicyManager:D || true

echo "== check-in lines =="
grep "check-in deviceId=" "$OUT/lab.log"

echo "== restriction =="
adb -s "$SERIAL" shell dumpsys device_policy >"$OUT/device_policy.txt" \
  || fail "step restriction: dumpsys device_policy failed"
adb -s "$SERIAL" shell dumpsys user >"$OUT/dumpsys_user.txt" \
  || fail "step restriction: dumpsys user failed"
set +e
python3 "$ROOT/server/policy_restriction.py" \
  --restriction no_add_user \
  --device-policy "$OUT/device_policy.txt" \
  --user "$OUT/dumpsys_user.txt" | tee "$OUT/restriction-match.txt"
RESTRICT_RC=${PIPESTATUS[0]}
set -e
if [ "$RESTRICT_RC" -ne 0 ]; then
  fail "restriction no_add_user not applied (DISALLOW_ADD_USER=${MODE})"
fi
if [ "$MODE" != "true" ] && [ "$MODE" != "true-then-false" ]; then
  fail "restriction no_add_user applied during negative mode (DISALLOW_ADD_USER=${MODE})"
fi

echo "== operator list =="
BOUND="$(listeners_ui_port || true)"
if [ -n "$BOUND" ]; then
  echo "$BOUND"
  fail "port ${UI_PORT} is already bound"
fi
python3 "$ROOT/server/ui_server.py" \
  --db "$OUT/fleet.sqlite" \
  --desired "$OUT/desired.json" \
  --host 127.0.0.1 \
  --port "$UI_PORT" \
  >"$OUT/ui.log" 2>&1 &
UI_PID=$!
for _ in $(seq 1 50); do
  if grep -q "fleet UI http://127.0.0.1:${UI_PORT}/" "$OUT/ui.log" 2>/dev/null; then
    break
  fi
  if ! kill -0 "$UI_PID" 2>/dev/null; then
    echo "---- ui log ----"
    cat "$OUT/ui.log" || true
    fail "ui_server exited"
  fi
  sleep 0.2
done
grep -q "fleet UI http://127.0.0.1:${UI_PORT}/" "$OUT/ui.log" || fail "ui_server did not listen"
echo "---- ui listen line ----"
grep "fleet UI http://127.0.0.1:${UI_PORT}/" "$OUT/ui.log"

BOUND=""
for _ in $(seq 1 20); do
  BOUND="$(listeners_ui_port || true)"
  if printf '%s\n' "$BOUND" | grep -qx "127.0.0.1:${UI_PORT}"; then
    break
  fi
  sleep 0.2
done
echo "-- ss listeners on ${UI_PORT} --"
printf '%s\n' "$BOUND"
if [ -z "$BOUND" ]; then
  fail "ui_server is not listening on 127.0.0.1:${UI_PORT}"
fi
BAD="$(printf '%s\n' "$BOUND" | grep -v -x "127.0.0.1:${UI_PORT}" || true)"
if [ -n "$BAD" ]; then
  fail "ui_server bound off 127.0.0.1:${UI_PORT}: ${BAD}"
fi
printf '%s\n' "$BOUND" | grep -qx "127.0.0.1:${UI_PORT}" \
  || fail "ui_server is not listening on 127.0.0.1:${UI_PORT}"

curl -fsS "http://127.0.0.1:${UI_PORT}/api/devices" >"$OUT/ui-devices.json" \
  || fail "step operator-list: GET /api/devices failed"
DEVICE_ID="$(grep 'check-in deviceId=' "$OUT/lab.log" | head -n 1 | sed -n 's/.*check-in deviceId=\([^[:space:]]*\).*/\1/p')"
[ -n "$DEVICE_ID" ] || fail "step operator-list: lab log has no check-in deviceId"
python3 -c 'import json,sys; doc=json.load(open(sys.argv[1], encoding="utf-8")); want=sys.argv[2]; ids=[d.get("deviceId") for d in doc.get("devices") or [] if isinstance(d, dict)]; sys.exit("deviceId %s not in operator list %s" % (want, ids)) if want not in ids else print(want)' \
  "$OUT/ui-devices.json" "$DEVICE_ID" \
  || fail "step operator-list: deviceId ${DEVICE_ID} not in $OUT/ui-devices.json"

INDEX_CODE="$(curl -sS -o "$OUT/ui-index.html" -w '%{http_code}' "http://127.0.0.1:${UI_PORT}/")" \
  || fail "step operator-list: GET / failed"
echo "operator page HTTP ${INDEX_CODE}"
[ "$INDEX_CODE" = "200" ] || fail "step operator-list: operator page HTTP ${INDEX_CODE}"
grep -qi '<html' "$OUT/ui-index.html" || fail "step operator-list: operator page is not HTML"

if [ "$MODE" = "true-then-false" ]; then
  echo "== clear (disallowAddUser=false, no owner reset) =="
  # Same device owner, same app data, same sqlite. The operator path is a
  # per-device override; lab_checkin.py reads it on the next check-in.
  cat >"$OUT/desired-false.json" <<'JSON'
{
  "schemaVersion": 1,
  "requiredPackages": [],
  "policyFlags": {"disallowAddUser": false},
  "commands": [{"type": "noop", "id": "emulator-phase5-clear"}]
}
JSON
  cat "$OUT/desired-false.json"
  python3 "$ROOT/server/fleet_store.py" --db "$OUT/fleet.sqlite" set-desired "$DEVICE_ID" "$OUT/desired-false.json" \
    || fail "step clear: fleet_store set-desired failed"
  OWNERS="$(adb -s "$SERIAL" shell dpm list-owners 2>&1 | tr -d '\r')"
  echo "$OWNERS"
  echo "$OWNERS" | grep -q "$PKG" || fail "step clear: $PKG is no longer device owner before the false check-in"
  broadcast_lab "clear"
  wait_for_n "lab-checkin SUCCESS" 2 outcome_count
  wait_for_n "check-in lines" 2 checkin_count
  wait_for_policy_applied 2
  grep "check-in deviceId=" "$OUT/lab.log"
  adb -s "$SERIAL" shell dumpsys device_policy >"$OUT/device_policy-after-false.txt" \
    || fail "step clear: dumpsys device_policy failed"
  adb -s "$SERIAL" shell dumpsys user >"$OUT/dumpsys_user-after-false.txt" \
    || fail "step clear: dumpsys user failed"
  set +e
  python3 "$ROOT/server/policy_restriction.py" \
    --restriction no_add_user \
    --device-policy "$OUT/device_policy-after-false.txt" \
    --user "$OUT/dumpsys_user-after-false.txt" | tee "$OUT/restriction-after-false.txt"
  CLEAR_RC=${PIPESTATUS[0]}
  set -e
  if [ "$CLEAR_RC" -eq 0 ]; then
    fail "step clear: no_add_user still applied after disallowAddUser=false"
  fi
  OWNERS="$(adb -s "$SERIAL" shell dpm list-owners 2>&1 | tr -d '\r')"
  echo "$OWNERS" | grep -q "$PKG" || fail "step clear: $PKG is not device owner after the false check-in"
  echo "PASS: no_add_user applied via disallowAddUser=true, then cleared by disallowAddUser=false with no owner reset; deviceId=${DEVICE_ID}. AOSP ATD emulator, not GrapheneOS; attestation not asserted."
  echo "result file: $OUT/result.txt"
  exit 0
fi

echo "PASS: no_add_user applied via policyFlags.disallowAddUser=true; operator list on 127.0.0.1:${UI_PORT} shows deviceId=${DEVICE_ID}. AOSP ATD emulator, not GrapheneOS; attestation not asserted."
echo "result file: $OUT/result.txt"
