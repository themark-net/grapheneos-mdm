#!/usr/bin/env bash
# Android emulator device-owner for this MDM agent (issue #36).
#
# This is an AOSP ATD emulator (system-images;android-35;aosp_atd;x86_64).
# Not GrapheneOS. It does not prove attestation, verified boot, or the
# 6-tap SetupWizard. Issue #8 stays closed.
#
# How this can fail, and what we do:
# - Emulator dead: restart once with the user-space emulator binary and the
#   flags below. If that fails, exit and print the log. Do not install qemu.
#   Do not boot a second emulator when one is already on ports 5574,5575.
# - dpm set-device-owner rejected (accounts, existing other owner): print the
#   command output and exit. Do not factory-reset.
# - Lab cert SAN is only DNS:localhost and IP:127.0.0.1. 10.0.2.2 fails TLS.
#   Use adb reverse so the guest calls https://127.0.0.1:8443. If reverse
#   fails, exit. Do not fall back to 10.0.2.2.
# - No screen sets serverBaseUrl. The debug receiver writes it on the same
#   SecureConfigStore the check-in reads. Release builds omit that receiver.
# - The example desired state names a placeholder APK. This script serves an
#   empty package list so a hash mismatch is not a failed check-in.
# - The lab broadcast is not ordered. setResultCode throws and the process
#   dies before check-in. The receiver only logs. Proof is the lab log.
# - am force-stop leaves the package stopped, and a later broadcast is
#   dropped. The script sends -f 32 (FLAG_INCLUDE_STOPPED_PACKAGES).
# - OpenSSL 3's default AES PKCS#12 throws "password empty" on Android
#   even with -passout pass:. This script re-exports client.p12 with
#   openssl pkcs12 -legacy (password still empty). Do not skip that export.
# - DevicePolicyManager must be called with this app's admin component.
#   The companion used to resolve DeviceAdminReceiver::class to
#   android.app.admin.DeviceAdminReceiver, so owner APIs threw and the
#   check-in never posted.
# - Proof is dpm/dumpsys plus a lab log line or a sqlite row for the device.
#   No row and no log line is a FAIL. This script never inserts a device row.
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
OUT="${OUT:-/tmp/mdm36-issue36}"
PORT="${PORT:-8443}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

echo "== issue #36 emulator device-owner =="
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
  # A different emulator on these ports would steal the console. Refuse.
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
"${GRADLE[@]}" --no-daemon --console=plain :app:assembleDebug -Dorg.gradle.java.home="$JAVA_HOME"

APK="$ROOT/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK" ] || fail "debug APK missing: $APK"

echo "== install =="
adb -s "$SERIAL" install -r -t -d "$APK"

echo "== mTLS material into app_mtls =="
rm -rf "$OUT/certs"
# The cert script is not necessarily marked executable in git.
bash "$ROOT/server/gen-lab-certs.sh" "$OUT/certs"
# Android PKCS#12 rejects OpenSSL 3's default AES bag when the password
# is empty ("password empty"). Re-export the same key and cert as a
# legacy 3DES bag. The password stays empty.
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
  "commands": [{"type": "noop", "id": "emulator-36"}]
}
JSON
adb -s "$SERIAL" push "$OUT/certs/client.p12" /data/local/tmp/mdm36-client.p12
adb -s "$SERIAL" push "$OUT/certs/ca.pem" /data/local/tmp/mdm36-ca.pem
adb -s "$SERIAL" shell chmod 644 /data/local/tmp/mdm36-client.p12 /data/local/tmp/mdm36-ca.pem
adb -s "$SERIAL" shell run-as "$PKG" mkdir -p app_mtls
adb -s "$SERIAL" shell run-as "$PKG" cp /data/local/tmp/mdm36-client.p12 app_mtls/client.p12
adb -s "$SERIAL" shell run-as "$PKG" cp /data/local/tmp/mdm36-ca.pem app_mtls/ca.pem
adb -s "$SERIAL" shell rm -f /data/local/tmp/mdm36-client.p12 /data/local/tmp/mdm36-ca.pem
echo "-- app_mtls --"
adb -s "$SERIAL" shell run-as "$PKG" ls -l app_mtls
P12_SIZE="$(adb -s "$SERIAL" shell run-as "$PKG" wc -c app_mtls/client.p12 | awk '{print $1}' | tr -d '\r')"
CA_SIZE="$(adb -s "$SERIAL" shell run-as "$PKG" wc -c app_mtls/ca.pem | awk '{print $1}' | tr -d '\r')"
[ "${P12_SIZE:-0}" -gt 0 ] || fail "client.p12 missing in app_mtls"
[ "${CA_SIZE:-0}" -gt 0 ] || fail "ca.pem missing in app_mtls"

adb -s "$SERIAL" shell am force-stop "$PKG" || true

echo "== set-device-owner =="
set +e
SET_OUT="$(adb -s "$SERIAL" shell dpm set-device-owner "$COMPONENT" 2>&1)"
SET_RC=$?
set -e
echo "$SET_OUT"
echo "set-device-owner exit=$SET_RC"

echo "== list-owners =="
OWNERS="$(adb -s "$SERIAL" shell dpm list-owners 2>&1 | tr -d '\r')"
echo "$OWNERS"
echo "$OWNERS" | grep -q "DeviceAdminReceiver" || fail "list-owners does not name DeviceAdminReceiver"
echo "$OWNERS" | grep -q "$PKG" || fail "list-owners does not name $PKG"

echo "== dumpsys device_policy (owner lines) =="
adb -s "$SERIAL" shell dumpsys device_policy >"$OUT/device_policy.txt"
grep -n -E "Device Owner|device owner|DeviceAdminReceiver|${PKG}" "$OUT/device_policy.txt" | head -n 40
grep -q "DeviceAdminReceiver" "$OUT/device_policy.txt" || fail "dumpsys device_policy has no DeviceAdminReceiver"

cleanup() {
  if [ -n "${LAB_PID:-}" ] && kill -0 "$LAB_PID" 2>/dev/null; then
    kill "$LAB_PID" 2>/dev/null || true
    wait "$LAB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "== lab server =="
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

echo "== broadcast lab URL =="
adb -s "$SERIAL" logcat -c || true
set +e
# -f 32 is FLAG_INCLUDE_STOPPED_PACKAGES. Without it, a force-stopped
# package never runs the receiver and am still prints result=0.
BC_OUT="$(adb -s "$SERIAL" shell am broadcast -f 32 \
  -a net.themark.grapheneosmdm.action.SET_LAB_SERVER \
  -n "$PKG/.lab.LabServerConfigReceiver" \
  --es serverBaseUrl "$LAB_URL" 2>&1)"
BC_RC=$?
set -e
echo "$BC_OUT"
echo "am broadcast exit=$BC_RC"
[ "$BC_RC" -eq 0 ] || fail "lab broadcast failed: $BC_OUT"

echo "== wait for check-in =="
FOUND=0
for _ in $(seq 1 30); do
  if grep -q "check-in deviceId=" "$OUT/lab.log" 2>/dev/null; then
    FOUND=1
    break
  fi
  sleep 1
done

echo "---- lab log ----"
cat "$OUT/lab.log" || true
echo "---- logcat (LabServerConfig / CheckInRunner / ApiClient / Mtls) ----"
adb -s "$SERIAL" logcat -d -s LabServerConfig:I LabServerConfig:W LabServerConfig:E CheckInRunner:I CheckInRunner:W CheckInRunner:E ApiClient:I ApiClient:W MtlsMaterialLoader:W MtlsMaterialLoader:E AndroidRuntime:E || true

if [ "$FOUND" -ne 1 ]; then
  fail "no lab check-in log line (adb reverse or TLS). See lab log and logcat above"
fi

echo "== fleet_store list =="
python3 "$ROOT/server/fleet_store.py" --db "$OUT/fleet.sqlite" list | tee "$OUT/fleet-list.json"

python3 - "$OUT/fleet.sqlite" "$ROOT/server" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[2])
from fleet_store import FleetStore
store = FleetStore(sys.argv[1])
rows = store.list_devices()
matched = []
for row in rows:
    full = store.get_device(row["deviceId"])
    inv = full["inventory"] if full else {}
    print(
        "device", row["deviceId"],
        "cn", row.get("clientCn"),
        "owner", inv.get("isDeviceOwner"),
        "model", inv.get("model"),
        "os", inv.get("osVersion"),
        "attestation", row.get("attestationStatus"),
        "boot", row.get("verifiedBootState"),
    )
    if row.get("clientCn") == "lab-device-01" and inv.get("isDeviceOwner") is True:
        matched.append(row["deviceId"])
        show = json.dumps(
            {
                "deviceId": row["deviceId"],
                "clientCn": row.get("clientCn"),
                "lastCheckinAt": row.get("lastCheckinAt"),
                "osVersion": inv.get("osVersion"),
                "model": inv.get("model"),
                "isDeviceOwner": inv.get("isDeviceOwner"),
                "attestationStatus": row.get("attestationStatus"),
                "verifiedBootState": row.get("verifiedBootState"),
            },
            indent=2,
        )
        print(show)
if not matched:
    sys.exit("no sqlite row for lab-device-01 with isDeviceOwner true")
PY

echo "PASS: device owner is $COMPONENT and the emulator checked in to $LAB_URL"
echo "NOTE: attestationStatus on this AOSP ATD image is not a GrapheneOS verified-boot result."
echo "result file: $OUT/result.txt"
