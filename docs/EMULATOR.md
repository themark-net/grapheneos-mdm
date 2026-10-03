# Android emulator device owner (issue #36)

This bench runs **this agent** on a normal Android emulator. It is **not** GrapheneOS.

| | |
| --- | --- |
| Image | `system-images;android-35;aosp_atd;x86_64` (AOSP ATD, Android 15, tag `aosp_atd`) |
| Not this | A GrapheneOS image, a Google Play image, or a Pixel |
| Enrollment | `adb shell dpm set-device-owner net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver` |
| What it does not prove | Attestation, verified boot, or the 6-tap SetupWizard |

Issue #8 stays closed. Stock GrapheneOS SetupWizard still has no scanner. That gap is unchanged. Do not read a successful emulator check-in as a GrapheneOS enroll.

The operate script is [scripts/emulator-device-owner.sh](../scripts/emulator-device-owner.sh). It builds the debug APK, installs it, sets device owner, and records the lab check-in. A failure exits non-zero and prints the command output. It does not insert a fake device row.

## SDK

Use a user-space Android SDK. Do not install packages into `/usr` and do not commit SDK bits, system images, AVDs, APKs, or lab certs.

The script reads `ANDROID_HOME` (default: `../android-sdk` next to this worktree), `JAVA_HOME` (default: `$ANDROID_HOME/jdk`), and `ANDROID_ADB_SERVER_PORT` (default: `5038` on this bench). It prepends that SDK's `platform-tools` and `emulator` on `PATH`. Gradle is invoked as `:app:assembleDebug` with `-Dorg.gradle.java.home`. `sdk.dir` is written to `local.properties`, which is gitignored. Do not commit `local.properties` and do not put `ANDROID_HOME` in `gradle.properties`.

## Check-in path

`server/lab_checkin.py` listens on `127.0.0.1:8443` and requires mTLS. `server/gen-lab-certs.sh` puts only `DNS:localhost` and `IP:127.0.0.1` on the server certificate. The emulator alias `10.0.2.2` fails that hostname check.

The script runs `adb -s emulator-5574 reverse tcp:8443 tcp:8443` and points the agent at `https://127.0.0.1:8443`. If reverse or the check-in fails, that is a failure. There is no fallback to `10.0.2.2`.

Client material is the empty-password `client.p12` and `ca.pem` from `gen-lab-certs.sh`. The agent reads them from the app-private directory `app_mtls` (`Context.getDir("mtls")`). Android's PKCS#12 store throws `password empty` on the OpenSSL 3 AES bag that `gen-lab-certs.sh` writes, even though the password is empty. The operate script re-exports that same key and certificate with `openssl pkcs12 -legacy` (3DES, password still empty) before copying it into `app_mtls`.

There is no URL field on the screen. The debug APK adds `LabServerConfigReceiver`, guarded by `android.permission.DUMP` and `FLAG_DEBUGGABLE`. Shell sends:

```bash
adb -s emulator-5574 shell am broadcast -f 32 \
  -a net.themark.grapheneosmdm.action.SET_LAB_SERVER \
  -n net.themark.grapheneosmdm/.lab.LabServerConfigReceiver \
  --es serverBaseUrl https://127.0.0.1:8443
```

Release builds do not contain that receiver. The main screen is unchanged.

The lab desired state for this run has an empty package list and no policy flags. The example desired state points at a placeholder catalog APK, and a hash mismatch after a real check-in would look like a failure.

## Proof

Device owner: `adb shell dpm list-owners` and `dumpsys device_policy` show `net.themark.grapheneosmdm.receiver.DeviceAdminReceiver`.

Check-in: a `check-in deviceId=` line in the lab log, or a `fleet_store.py --db … list` row whose client certificate CN is `lab-device-01`. The inventory field `isDeviceOwner` is the agent's own report. Attestation status on this image is not a verified-boot result. The fingerprint looks like `Android/sdk_slim_x86_64/emu64x:15/…:userdebug/test-keys`.

## If the emulator is down

Restart it once with the user-space emulator binary, AVD `mdm36`, and `-no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader_indirect -accel on -ports 5574,5575`. If that process exits, stop and keep the stderr. Do not install qemu and do not start a second emulator while one is already bound to those ports.
