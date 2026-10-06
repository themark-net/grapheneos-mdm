# Android emulator device owner (issue #36)

This bench runs **this agent** on a normal Android emulator. It is **not** GrapheneOS.

| | |
| --- | --- |
| Image | `system-images;android-35;aosp_atd;x86_64` (AOSP ATD, Android 15, tag `aosp_atd`) |
| Not this | A GrapheneOS image, a Google Play image, or a Pixel |
| Enrollment | `adb shell dpm set-device-owner net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver` |
| What it does not prove | Attestation, verified boot, or the 6-tap SetupWizard |

Issue #8 stays closed. Stock GrapheneOS SetupWizard still has no scanner. That gap is unchanged. Do not read a successful emulator check-in as a GrapheneOS enroll.

The device-owner script is [scripts/emulator-device-owner.sh](../scripts/emulator-device-owner.sh). It builds the debug APK, installs it, sets device owner, and records one lab check-in. A failure exits non-zero and prints the command output. It does not insert a fake device row.

The same-database attestation script is [scripts/emulator-same-db-attestation.sh](../scripts/emulator-same-db-attestation.sh). It is Phase 3. Details are in [Same-database attestation](#same-database-attestation-phase-3).

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

## Same-database attestation (Phase 3)

```bash
scripts/emulator-same-db-attestation.sh
```

`OUT` defaults to `/tmp/mdm-phase3-attestation`. `ANDROID_HOME`, AVD `mdm36`, serial `emulator-5574`, and ports `5574,5575` match the device-owner script. This tree has no `gradlew`. Set `GRADLE_BIN` to a Gradle 8.9 binary, or the script uses `gradle` on `PATH`.

The script removes `fleet.sqlite` in `OUT` before it listens, so the run has a new database. A device-owner package rejects `pm clear`. `assembleDebug` is not test-only unless Gradle is given `-Pandroid.injected.testOnly=true`, and `dpm remove-active-admin` rejects a non-test owner. The test-only bit is stored when the admin is first set, so installing a test-only APK over the #38 owner does not flip it. The script builds with that property and installs with `-t`. If removal still reports a non-test admin, it stops the Android framework, deletes `/data/system/device_owner_2.xml` and `/data/system/device_policies.xml`, and starts the framework again. That is not a factory reset. It then runs `pm clear`, copies mTLS material, and calls `dpm set-device-owner`. The new owner is test-only, so a later run can use `remove-active-admin`. It exits if `shared_prefs/policy_compliance.xml` still contains `attestation_challenge_next` or `attestation_challenge_for_key`, or if keystore2 `keyentry.alias` still has `grapheneos_mdm_attest`. That query is `sqlite3 /data/misc/keystore/persistent.sqlite` after `adb root`. A leftover key is a setup failure.

`LabServerConfigReceiver` saves the URL and runs `CheckInRunner` once per broadcast (`allowFollowUpCheckIn=false`). The second check-in is a second broadcast, not `checkin_now`. The script waits until the first `lab-checkin outcome=SUCCESS` is in logcat, then broadcasts again. `set-device-owner` also enqueues an `admin_enabled` check-in. The script `force-stop`s the package after owner is set and before the lab URL is saved, so that worker does not become a third POST. Desired state for the run is an empty package list, empty `policyFlags`, and a `noop` command.

The second `check-in deviceId=` line is the record. The script exits non-zero when that line is missing, when the log has any other count than two (a later POST overwrites the sqlite row), or when `attestationStatus` is `challenge_mismatch`, `none`, `missing`, `parse_error`, or `unsupported`. It prints `attestationStatus` and `verifiedBootState`. The success line quotes that status. It says verified boot passed only when the status is `ok` and `verifiedBootState` is `Verified`.

On this `userdebug` / `test-keys` image the chain check runs before the boot check. The honest status is often `chain_invalid`. `boot_unverified` is a record only when the chain passed and boot is not `Verified`. `verifiedBootState` can be null. `chain_invalid` is the server's judgment of a challenge this database issued. It is not attestation success. The image is not GrapheneOS.

`server/same_db_attestation.py` is the check the script runs. `server/tests/test_same_db_attestation.py` drives `FleetStore.observe_attestation` on a temporary sqlite and exits non-zero for a forbidden second status, a single check-in line, and a third line. That test does not boot an emulator.

### Bench result

`scripts/emulator-same-db-attestation.sh` exited 0 on 2026-10-06. Image fingerprint `Android/sdk_slim_x86_64/emu64x:15/AE3A.240806.019/12368160:userdebug/test-keys`, model `Android ATD built for x86_64`. The first lab line was `attestation=none`. The second line, which is the sqlite row, was:

```
deviceId a7fdb4548155d650
clientCn lab-device-01
osVersion 15
attestationStatus chain_invalid
verifiedBootState null
lastCheckinAt 2026-10-06T17:40:49Z
```

`chain_invalid` means the keymint chain did not sign to `server/attestation-roots.pem`. The success line quoted that status. Verified boot was not passed. `verifiedBootState` is null. This is not a GrapheneOS result and not attestation success.
