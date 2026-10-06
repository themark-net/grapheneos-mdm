#!/usr/bin/env bash
# Same-database attestation on the AOSP ATD emulator (Phase 3).
#
# This is an AOSP ATD emulator (system-images;android-35;aosp_atd;x86_64).
# Not GrapheneOS. Issue #8 stays closed. attestationStatus ok is the only
# verified-boot pass, and this userdebug/test-keys image is not expected
# to return ok.
#
# How this can fail, and what we do:
# - Emulator dead: restart once with the user-space emulator binary and the
#   flags below. If that fails, exit and print the log. Do not install qemu.
#   Do not boot a second emulator when one is already on ports 5574,5575.
# - A device-owner package rejects pm clear, so the old nonce and keystore
#   alias survive. assembleDebug is not testOnly unless
#   -Pandroid.injected.testOnly=true, and dpm remove-active-admin rejects
#   a non-test owner. The testOnly bit is stored when the admin is first
#   set, so installing a testOnly APK over the #38 owner does not flip it.
#   This script builds that testOnly debug APK and installs it. If remove
#   still says non-test admin, it stops the framework and deletes
#   device_owner_2.xml and device_policies.xml (not a factory reset), then
#   starts the framework, pm clears, and sets device owner again. A leftover
#   attestation_challenge_* pref or keystore alias grapheneos_mdm_attest
#   is a setup failure, not a result.
# - dpm set-device-owner rejected (accounts, existing other owner): print the
#   command output and exit. Do not factory-reset.
# - set-device-owner enqueues an immediate check-in (admin_enabled). The
#   lab URL is not set yet, and LabServerConfigReceiver runs one check-in
#   per broadcast with allowFollowUpCheckIn=false. force-stop after
#   set-device-owner cancels that worker so it cannot become a third POST.
# - Lab cert SAN is only DNS:localhost and IP:127.0.0.1. 10.0.2.2 fails TLS.
#   Use adb reverse so the guest calls https://127.0.0.1:8443. If reverse
#   fails, exit. Do not fall back to 10.0.2.2.
# - The example desired state names a placeholder APK. This script serves an
#   empty package list and a noop command so a hash mismatch is not a failure.
# - OpenSSL 3's default AES PKCS#12 throws "password empty" on Android
#   even with -passout pass:. This script re-exports client.p12 with
#   openssl pkcs12 -legacy (password still empty). Do not skip that export.
# - One new sqlite file. Two broadcasts. The second lab line is the record.
#   Exit non-zero when that line is missing, when a later line overwrites
#   the row, or when attestationStatus is challenge_mismatch, none, missing,
#   parse_error, or unsupported. chain_invalid and boot_unverified are
#   records. Do not call verified boot passed unless the status is ok.
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
LAB_URL="https://127.0.0.1:8443"
OUT="${OUT:-/tmp/mdm-phase3-attestation}"
PORT="${PORT:-8443}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

echo "== phase 3 same-database emulator attestation =="
echo "ROOT=$ROOT"
echo "ANDROID_HOME=$ANDROID_HOME"
echo "JAVA_HOME=$JAVA_HOME"
echo "ANDROID_ADB_SERVER_PORT=$ANDROID_ADB_SERVER_PORT"
echo "SERIAL=$SERIAL"

[ -n "$ANDROID_HOME" ] && [ -d "$ANDROID_HOME" ] || fail "ANDROID_HOME is not a directory"
[ -x "$JAVA_HOME/bin/java" ] || fail "JAVA_HOME has no java: $JAVA_HOME"
[ -x "$ANDROID_HOME/platform-tools/adb" ] || fail "user-space adb missing"
case "$(command -v adb)" in
  "$ANDROID_HOME"/*) ;;
  *) fail "adb is not the user-space SDK adb: $(command -v adb)" ;;
esac
need python3
need openssl

mkdir -p "$OUT"
rm -f "$OUT/result.txt"
exec > >(tee -a "$OUT/result.txt") 2>&1

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
  echo "== remove-active-admin so pm clear can drop attestation state =="
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

assert_attestation_cleared() {
  local prefs prefs_rc count
  echo "== attestation prefs after pm clear =="
  set +e
  prefs="$(adb -s "$SERIAL" shell run-as "$PKG" cat shared_prefs/policy_compliance.xml 2>&1)"
  prefs_rc=$?
  set -e
  prefs="$(printf '%s' "$prefs" | tr -d '\r')"
  echo "$prefs"
  if printf '%s\n' "$prefs" | grep -q "attestation_challenge_next\|attestation_challenge_for_key"; then
    fail "leftover attestation challenge prefs after pm clear"
  fi
  if [ "$prefs_rc" -ne 0 ]; then
    case "$prefs" in
      *"No such file"*|*"does not exist"*|*"doesn't exist"*) ;;
      *) fail "could not read policy_compliance after pm clear: $prefs" ;;
    esac
  fi

  echo "== keystore alias after pm clear =="
  # dumpsys has no "keystore" service on this image. keystore2 keeps aliases
  # in /data/misc/keystore/persistent.sqlite. adb root is required to read it.
  set +e
  echo "$(adb -s "$SERIAL" root 2>&1)"
  set -e
  wait_for_shell
  count="$(adb -s "$SERIAL" shell "sqlite3 /data/misc/keystore/persistent.sqlite \"SELECT COUNT(*) FROM keyentry WHERE alias = 'grapheneos_mdm_attest';\"" | tr -d '\r' || true)"
  echo "grapheneos_mdm_attest rows=${count}"
  case "$count" in
    0) ;;
    ''|*[!0-9]*)
      fail "could not query keystore for alias grapheneos_mdm_attest: ${count}"
      ;;
    *)
      fail "leftover keystore alias grapheneos_mdm_attest (rows=${count})"
      ;;
  esac
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
  echo "---- logcat (LabServerConfig / CheckInRunner / ApiClient) ----"
  adb -s "$SERIAL" logcat -d -s LabServerConfig:I LabServerConfig:W LabServerConfig:E CheckInRunner:I CheckInRunner:W CheckInRunner:E CheckInRunner:D ApiClient:I ApiClient:W MtlsMaterialLoader:W MtlsMaterialLoader:E AndroidRuntime:E KeyAttestor:W || true
  fail "timed out waiting for $label >= $want (saw $($reader))"
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
# remove-active-admin rejects a non-test device owner, and pm clear
# then cannot drop the attestation key. The Phase 2 script does not
# remove the owner; this one has to.
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

assert_attestation_cleared

echo "== mTLS material into app_mtls =="
rm -rf "$OUT/certs"
bash "$ROOT/server/gen-lab-certs.sh" "$OUT/certs"
openssl pkcs12 -export -legacy -name lab-device-01 \
  -out "$OUT/certs/client.p12" \
  -inkey "$OUT/certs/client-key.pem" \
  -in "$OUT/certs/client.pem" \
  -certfile "$OUT/certs/ca.pem" \
  -passout pass:
cat >"$OUT/desired.json" <<'JSON'
{
  "schemaVersion": 1,
  "requiredPackages": [],
  "policyFlags": {},
  "commands": [{"type": "noop", "id": "emulator-phase3"}]
}
JSON
adb -s "$SERIAL" push "$OUT/certs/client.p12" /data/local/tmp/mdm-phase3-client.p12
adb -s "$SERIAL" push "$OUT/certs/ca.pem" /data/local/tmp/mdm-phase3-ca.pem
adb -s "$SERIAL" shell chmod 644 /data/local/tmp/mdm-phase3-client.p12 /data/local/tmp/mdm-phase3-ca.pem
adb -s "$SERIAL" shell run-as "$PKG" mkdir -p app_mtls
adb -s "$SERIAL" shell run-as "$PKG" cp /data/local/tmp/mdm-phase3-client.p12 app_mtls/client.p12
adb -s "$SERIAL" shell run-as "$PKG" cp /data/local/tmp/mdm-phase3-ca.pem app_mtls/ca.pem
adb -s "$SERIAL" shell rm -f /data/local/tmp/mdm-phase3-client.p12 /data/local/tmp/mdm-phase3-ca.pem
echo "-- app_mtls --"
adb -s "$SERIAL" shell run-as "$PKG" ls -l app_mtls
P12_SIZE="$(adb -s "$SERIAL" shell run-as "$PKG" wc -c app_mtls/client.p12 | awk '{print $1}' | tr -d '\r')"
CA_SIZE="$(adb -s "$SERIAL" shell run-as "$PKG" wc -c app_mtls/ca.pem | awk '{print $1}' | tr -d '\r')"
[ "${P12_SIZE:-0}" -gt 0 ] || fail "client.p12 missing in app_mtls"
[ "${CA_SIZE:-0}" -gt 0 ] || fail "ca.pem missing in app_mtls"

echo "== set-device-owner =="
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

cleanup() {
  if [ -n "${LAB_PID:-}" ] && kill -0 "$LAB_PID" 2>/dev/null; then
    kill "$LAB_PID" 2>/dev/null || true
    wait "$LAB_PID" 2>/dev/null || true
  fi
}
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
broadcast_lab "first"
wait_for_n "lab-checkin SUCCESS" 1 outcome_count
wait_for_n "check-in lines" 1 checkin_count
# The response nonce is in memory after SUCCESS. Give apply() a moment
# to hit disk in case the next broadcast starts a new process.
sleep 1
broadcast_lab "second"
wait_for_n "lab-checkin SUCCESS" 2 outcome_count
wait_for_n "check-in lines" 2 checkin_count

echo "---- lab log ----"
cat "$OUT/lab.log" || true
echo "---- logcat (LabServerConfig / CheckInRunner / ApiClient / Mtls) ----"
adb -s "$SERIAL" logcat -d -s LabServerConfig:I LabServerConfig:W LabServerConfig:E CheckInRunner:I CheckInRunner:W CheckInRunner:E CheckInRunner:D ApiClient:I ApiClient:W MtlsMaterialLoader:W MtlsMaterialLoader:E AndroidRuntime:E KeyAttestor:W || true

echo "== check-in lines =="
grep "check-in deviceId=" "$OUT/lab.log"

echo "== fleet_store list =="
python3 "$ROOT/server/fleet_store.py" --db "$OUT/fleet.sqlite" list | tee "$OUT/fleet-list.json"

python3 "$ROOT/server/same_db_attestation.py" \
  --db "$OUT/fleet.sqlite" \
  --lab-log "$OUT/lab.log"

echo "result file: $OUT/result.txt"
