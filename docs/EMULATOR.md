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

The user-restriction script is [scripts/emulator-policy-restriction.sh](../scripts/emulator-policy-restriction.sh). `disallowAddUser` is Phase 4 (issue #45). `RESTRICTION=disallowFactoryReset` is Phase 6 (issue #49). Phase 7 (issue #51) is the CI hardening of that same script. Details are in [Phase 4 — disallowAddUser on the operator page](#phase-4--disallowadduser-on-the-operator-page), [Phase 6 — disallowFactoryReset](#phase-6--disallowfactoryreset-on-the-kvm-job), and [Phase 7 — CI hardening](#phase-7--ci-hardening).

Phase 5 (issue #47) runs that script on a GitHub-hosted KVM runner. Phase 6 adds the factory-reset legs to the same job. Details are in [Phase 5 — GitHub-hosted KVM runner](#phase-5--github-hosted-kvm-runner).

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

## Phase 4 — disallowAddUser on the operator page

Issue #45. The image is the same AOSP ATD emulator. This section does not assert attestation and does not call the image GrapheneOS.

```bash
scripts/emulator-policy-restriction.sh
DISALLOW_ADD_USER=false scripts/emulator-policy-restriction.sh
DISALLOW_ADD_USER=absent scripts/emulator-policy-restriction.sh
```

`OUT` defaults to `/tmp/mdm-phase4-policy`. `ANDROID_HOME`, AVD `mdm36`, serial `emulator-5574`, and `ANDROID_ADB_SERVER_PORT=5038` match the other bench scripts. This tree has no `gradlew`. Set `GRADLE_BIN` to a Gradle 8.9 binary, or the script uses `gradle` on `PATH`.

`DISALLOW_ADD_USER` defaults to `true`. The script writes `desired.json` with `schemaVersion` 1, an empty `requiredPackages` list, a `noop` command id `emulator-phase4`, and:

| `DISALLOW_ADD_USER` | `policyFlags` | Expected script result |
| --- | --- | --- |
| `true` (default) | `{"disallowAddUser": true}` | Exit 0. `no_add_user` is applied. The PASS line names that flag and the device id. |
| `false` | `{"disallowAddUser": false}` | Exit non-zero. `FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=false)`. |
| `absent` | `{}` | Exit non-zero. `FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=absent)`. |
| `true-then-false` (Phase 5) | `{"disallowAddUser": true}`, then a per-device override `{"disallowAddUser": false}` | Exit 0 only when `no_add_user` is applied after the first check-in and gone after the second, with no owner reset in between. |
| any other value | (not written) | Exit non-zero before the emulator is used. |

`false` and `absent` are expected to FAIL. That is the negative proof. The script stops at the restriction step and does not print PASS.

The run removes a previous test-only device owner when one is set, `pm clear`s `net.themark.grapheneosmdm`, copies mTLS material, and calls `dpm set-device-owner`. It `adb reverse`s `tcp:8443` and broadcasts `LabServerConfigReceiver` once. It waits for one `lab-checkin outcome=SUCCESS`, one `check-in deviceId=` line, and the logcat line `Desired state policy flags applied` from tag `PolicyManager`. It saves `dumpsys device_policy` and `dumpsys user`, then runs `server/policy_restriction.py --restriction no_add_user`. On success it starts `ui_server.py` on 127.0.0.1:`UI_PORT` (default 8787) against that sqlite, checks the listen address, and checks that `GET /api/devices` lists the check-in device id and that `GET /` is HTML with status 200.

The log order is enroll, check-in, restriction, operator list. Guest temp files are named `mdm-phase4-*`. Cleanup kills the lab server and `ui_server.py` and removes `adb reverse tcp:$PORT` (default 8443). It does not stop the emulator. There is no wipe command and no `-wipe-data`.

If the restriction is missing, the script exits non-zero and names that step. Read `PolicyManager` logcat for the policyFlags parse. If `UI_PORT` (default 8787) is busy, or the UI is bound to `0.0.0.0`, `*`, or `::`, the script exits and does not bind off 127.0.0.1. If the emulator or KVM is unavailable, that is a host blocker. Do not fake a PASS.

`true-then-false` runs the `true` steps through the operator list, then writes `desired-false.json` (`{"disallowAddUser": false}`, noop id `emulator-phase5-clear`), stores it as a per-device override with `server/fleet_store.py --db … set-desired <deviceId>`, and broadcasts a second check-in. It does not remove the owner and does not `pm clear` in between. It waits for two `lab-checkin outcome=SUCCESS` lines, two `check-in deviceId=` lines and two `Desired state policy flags applied` lines, saves `device_policy-after-false.txt` and `dumpsys_user-after-false.txt`, and, on API 34 and above, requires an anchored `Local Policies:` or `Global Policies:` line in the after-false `device_policy` dump plus `UserRestrictionPolicyKey` or a non-empty indented line under that header (a header alone does not count; a mid-line mention does not count), `UserInfo{` and a restriction header in `dumpsys user`, and no `*** SERVICE ... DUMP TIMEOUT` line. `policy_restriction.py` must exit 1 and print `restriction no_add_user is not applied`. Exit 0 is `FAIL: step clear: no_add_user still applied after disallowAddUser=false`. Exit 2 (empty, unrecognised, timeout, or a missing API 34 marker) is a failed clear. Exit 3 is an argparse usage error and is also a failed clear. Any other exit, or exit 1 without that sentence, is a failed clear. The agent maps `false` to `DevicePolicyManager.clearUserRestriction` (`PolicyManager.applyDesiredState`, covered by `PolicyRestrictionTest.falseFlagsClearRestrictions`).

### Post-run emulator state

The script does not stop the emulator and does not undo its policy. After a `true` run, `net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver` is device owner (test-only) and `no_add_user` is set. After `true-then-false`, the app is still device owner and `no_add_user` is cleared. After `false` or `absent`, the app is device owner and `no_add_user` is not set. The next run of any emulator script removes the test-only owner first, which also drops the restrictions that owner set.

### Environment overrides

The nimo defaults are unchanged. CI overrides them through [scripts/ci-emulator-policy.sh](../scripts/ci-emulator-policy.sh).

| Variable | nimo default | GitHub Actions |
| --- | --- | --- |
| `SERIAL` | `emulator-5574` | `emulator-5554` |
| `ANDROID_ADB_SERVER_PORT` | `5038` | `5037` |
| `ANDROID_HOME` | `../android-sdk` | runner SDK |
| `ANDROID_USER_HOME` | `$ANDROID_HOME/user-home` | `$HOME/.android` |
| `GRADLE_BIN` | unset (bench uses a user-space Gradle 8.9) | `gradle` from `gradle/actions/setup-gradle` (8.9) |
| `UI_PORT` | `8787` | `8787` |
| `PORT` | `8443` | `8443` |
| `OUT` | `/tmp/mdm-phase4-policy` | `/tmp/mdm-ci/<leg>` |
| `CERTS_DIR` | `$OUT/certs` | `/tmp/mdm-certs/<leg>` (not under the uploaded log dir) |
| `RESTRICTION` | `disallowAddUser` | `disallowAddUser`, then `disallowFactoryReset` |
| AVD name | `mdm36` | `avd-name: mdm36` on the emulator runner |

`server/tests/test_policy_restriction.py` checks the dumpsys parser. It does not boot an emulator.

### Bench log 2026-10-09

Run on nimo, 2026-10-09 ~00:55 PT, AVD `mdm36`, serial `emulator-5574`, fingerprint `Android/sdk_slim_x86_64/emu64x:15/AE3A.240806.019/12368160:userdebug/test-keys`. AOSP ATD emulator, not GrapheneOS. `GRADLE_BIN` was a user-space Gradle 8.9. Same script, three modes, run in this order:

```text
# DISALLOW_ADD_USER=absent  -> exit 1
  "policyFlags": {},
check-in deviceId=a7fdb4548155d650 packages=73 client=lab-device-01 attestation=none
I PolicyManager: Desired state policy flags applied
== restriction ==
restriction no_add_user is not applied
FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=absent)

# DISALLOW_ADD_USER=false   -> exit 1
  "policyFlags": {"disallowAddUser": false},
check-in deviceId=a7fdb4548155d650 packages=73 client=lab-device-01 attestation=none
I PolicyManager: Desired state policy flags applied
== restriction ==
restriction no_add_user is not applied
FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=false)

# DISALLOW_ADD_USER=true (default) -> exit 0
  "policyFlags": {"disallowAddUser": true},
Success: Device owner set to package net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
check-in deviceId=a7fdb4548155d650 packages=73 client=lab-device-01 attestation=none
I PolicyManager: Desired state policy flags applied
== restriction ==
      no_add_user                                         (dumpsys user, Effective restrictions:)
    no_add_user                                           (dumpsys user, Device policy global restrictions:)
    UserRestrictionPolicyKey userRestriction_no_add_user  (dumpsys device_policy, Global Policies)
        BooleanPolicyValue { mValue= true }               (Resolved Policy (MostRestrictive))
== operator list ==
fleet UI http://127.0.0.1:8787/  db=/tmp/mdm-phase4-policy/fleet.sqlite
-- ss listeners on 8787 --
127.0.0.1:8787
a7fdb4548155d650
operator page HTTP 200
PASS: no_add_user applied via policyFlags.disallowAddUser=true; operator list on 127.0.0.1:8787 shows deviceId=a7fdb4548155d650. AOSP ATD emulator, not GrapheneOS; attestation not asserted.
```

`GET /api/devices` on 127.0.0.1:8787 returned one row: `deviceId a7fdb4548155d650`, `clientCn lab-device-01`, `osVersion 15`, `securityPatch 2024-09-05`, `attestationStatus none`, `verifiedBootState null`, `simulated false`. `attestationStatus none` is expected on a single check-in against a new sqlite (no nonce issued yet). Attestation was not passed and is not part of this phase. After each run nothing listened on 8443 or 8787. The emulator was left running.

Two fixes came out of the bench. `adb logcat -s` keeps only the last level given per tag, so `PolicyManager:I ... PolicyManager:E` hid the Info line; the script now passes one level per tag. Android 15 prints the policy key as `UserRestrictionPolicyKey userRestriction_no_add_user`, which the first parser draft missed; `server/policy_restriction.py` now accepts that prefix and reads only the `Resolved Policy` section when one is present. Both cases are in `server/tests/test_policy_restriction.py` with text captured from this run.

## Phase 5 — GitHub-hosted KVM runner

Issue #47. The image is the same AOSP ATD Android 15 emulator (`system-images;android-35;aosp_atd;x86_64`). It is not GrapheneOS. Attestation is not asserted.

[.github/workflows/emulator-policy.yml](../.github/workflows/emulator-policy.yml), job `AOSP ATD emulator policy (disallowAddUser, disallowFactoryReset)`, runs on `ubuntu-latest`. There is no self-hosted runner. Steps:

1. Enable KVM with the udev rule `KERNEL=="kvm", GROUP="kvm", MODE="0666"` on the hosted runner.
2. `actions/setup-java` v6.0.1 (Temurin 17), `gradle/actions/setup-gradle` v6.4.0 (Gradle 8.9), and `actions/setup-python` v7.0.0 (3.12), each pinned by commit SHA, as are `actions/checkout` v7.0.1 and `actions/upload-artifact` v7.0.2. Those releases run on Node 24. `reactivecircus/android-emulator-runner` v2.38.0 was already Node 24.
3. Build the test-only debug APK before the emulator boots.
4. `reactivecircus/android-emulator-runner` v2.38.0 (pinned by SHA) with `api-level: 35`, `target: aosp_atd`, `arch: x86_64`, `avd-name: mdm36` boots the emulator on `emulator-5554` and runs `scripts/ci-emulator-policy.sh`.
5. If that step fails before the wrapper creates `/tmp/mdm-ci/script-started`, the same emulator step runs once more. See [Boot retry](#boot-retry).
6. `actions/upload-artifact` uploads `/tmp/mdm-ci` as `emulator-policy-logs`, `if: always()`. The path excludes `!/tmp/mdm-ci/**/certs/**`, `fleet.sqlite*`, and `*.pem` / `*.p12` / `*.key` / `*.crt` / `*.der` / `*.cer` / `*.pfx` / `*.jks` / `*.keystore` / `*.csr` / `*.bks`. Lab certs are not written under `/tmp/mdm-ci` at all. The wrapper also deletes `fleet.sqlite*` before it exits, because the WAL can hold an attestation chain. Attestation is not asserted.

`scripts/ci-emulator-policy.sh` runs the disallowAddUser legs below, asserts that post-run state, then runs the Phase 6 disallowFactoryReset legs. Each leg has its own `OUT`. Every exit code is asserted:

| Leg | `DISALLOW_ADD_USER` | Required exit | Required line |
| --- | --- | --- | --- |
| absent | `absent` | 1 | `FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=absent)` |
| false | `false` | 1 | `FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=false)` |
| true-then-false | `true-then-false` | 0 | `PASS: no_add_user applied via disallowAddUser=true, then cleared by disallowAddUser=false with no owner reset` |
| true | `true` | 0 | `PASS: no_add_user applied via policyFlags.disallowAddUser=true` |

A negative leg that prints `PASS:` also fails the job. After the legs it saves `logcat`, `dumpsys device_policy`, `dumpsys user` and `dpm list-owners`, and asserts the post-run state: this app is device owner and `no_add_user` is applied. The summary lines start with `ASSERT OK:` or `ASSERT FAIL:` and are in `summary.txt` in the artifact.

Each leg also appends to the job summary (`$GITHUB_STEP_SUMMARY`, copied in `job-summary.md`): every `policy_restriction.py` output line, the `GET /api/devices` row (or `not reached` when the negative leg stops before the operator list), and the `PASS:` or `FAIL:` line. `true-then-false` adds the after-false `policy_restriction.py` lines as well.

### Boot retry

The emulator-runner step is attempted once. The wrapper touches `/tmp/mdm-ci/script-started` as soon as it starts, which is after the action has booted the emulator. If the step's outcome is failure and that file is missing, the job runs the same step one more time (`avd-name: mdm36`, same image, same script) and then stops. A second failure fails the job. If the script has started, a failed leg is the result: it is not retried.

### Certs stay out of the artifact

`CERTS_DIR` on the runner is `/tmp/mdm-certs/<leg>`. That directory is not the upload path. The upload also drops `!/tmp/mdm-ci/**/certs/**`, `fleet.sqlite*`, and certificate/key suffixes `.pem`, `.p12`, `.key`, `.crt`, `.der`, `.cer`, `.pfx`, `.jks`, `.keystore`, `.csr`, and `.bks`. The wrapper fails the job if a certificate or key file, or a `certs/` directory, is under `/tmp/mdm-ci`. After that check it deletes `fleet.sqlite*` and fails if any remain. The exit trap deletes them on an early exit too. The nimo default for certs is still `$OUT/certs`. The sqlite for a nimo run stays under `OUT`.

Triggers: `pull_request` and `push` to `main`, filtered to the operate script, `scripts/lib/**`, the CI wrapper, `server/**`, `app/**`, `protocol/**`, the Gradle files and the workflow file, plus `workflow_dispatch`. There is no cron. Concurrency cancels an older run on the same PR or ref. The job timeout is 45 minutes. `docs/**` is not in the filter, so a docs-only `push` to `main` does not run this job. On `pull_request` the filter matches the whole PR diff, so a docs-only head still re-runs the job while the PR also changes a listed path.

### CI result

`ef320ae` (`ef320ae6b973ca7bf03fbcd4dd94f2466c45669b`) is the last code SHA. Green run on that SHA: https://github.com/themark-net/grapheneos-mdm/actions/runs/37976338590, job `AOSP ATD emulator policy (disallowAddUser)`. The boot retry step was skipped. The image is an AOSP ATD emulator, not GrapheneOS. Attestation was not asserted. Docs head `5a4e8f1` (`5a4e8f1a9f7417e208e579a079af4c893fa7ba59`) ran the same job at https://github.com/themark-net/grapheneos-mdm/actions/runs/37977122809, because `pull_request` path filters match the whole PR diff.

```
ASSERT OK: leg absent DISALLOW_ADD_USER=absent exit=1 expected=1
ASSERT OK: leg false DISALLOW_ADD_USER=false exit=1 expected=1
ASSERT OK: leg true-then-false DISALLOW_ADD_USER=true-then-false exit=0 expected=0
ASSERT OK: leg true DISALLOW_ADD_USER=true exit=0 expected=0
ASSERT OK: post-run device owner is net.themark.grapheneosmdm
ASSERT OK: post-run no_add_user is applied
ASSERT OK: no cert or key file under /tmp/mdm-ci
```

## Phase 6 — disallowFactoryReset on the KVM job

Issue #49. The image is the same AOSP ATD Android 15 emulator (`system-images;android-35;aosp_atd;x86_64`, `avd-name: mdm36`). It is not GrapheneOS. Attestation is not asserted. The script does not factory-reset the emulator and does not wipe it.

`PolicyManager.userRestrictionUpdates` already maps `policyFlags.disallowFactoryReset` true to `DevicePolicyManager.addUserRestriction(UserManager.DISALLOW_FACTORY_RESET)` and false to `clearUserRestriction`. The platform constant is the dumpsys token `no_factory_reset`. `PolicyRestrictionTest.trueFlagsAddRestrictions` and `falseFlagsClearRestrictions` cover that mapping. The protocol schema already has the boolean. No app change.

The operate script is the Phase 4 script with `RESTRICTION=disallowFactoryReset`. The mode env is `DISALLOW_FACTORY_RESET`. Default `RESTRICTION` remains `disallowAddUser`, so the Phase 4 command is unchanged.

```bash
RESTRICTION=disallowFactoryReset scripts/emulator-policy-restriction.sh
RESTRICTION=disallowFactoryReset DISALLOW_FACTORY_RESET=false scripts/emulator-policy-restriction.sh
RESTRICTION=disallowFactoryReset DISALLOW_FACTORY_RESET=absent scripts/emulator-policy-restriction.sh
RESTRICTION=disallowFactoryReset DISALLOW_FACTORY_RESET=true-then-false scripts/emulator-policy-restriction.sh
```

| `DISALLOW_FACTORY_RESET` | `policyFlags` | Expected script result |
| --- | --- | --- |
| `true` (default) | `{"disallowFactoryReset": true}` | Exit 0. `no_factory_reset` is applied. The PASS line names that flag and the device id. |
| `false` | `{"disallowFactoryReset": false}` | Exit 1. `FAIL: restriction no_factory_reset not applied (DISALLOW_FACTORY_RESET=false)`. |
| `absent` | `{}` | Exit 1. `FAIL: restriction no_factory_reset not applied (DISALLOW_FACTORY_RESET=absent)`. |
| `true-then-false` | `{"disallowFactoryReset": true}`, then a per-device override `{"disallowFactoryReset": false}` | Exit 0 only when `no_factory_reset` is applied after the first check-in and, after the second, API 34+ sees an anchored `Local Policies:` or `Global Policies:` line plus `UserRestrictionPolicyKey` or a non-empty indented line under that header, `UserInfo{`, and a restriction header, with no DUMP TIMEOUT line, and `policy_restriction.py` exits 1 with `restriction no_factory_reset is not applied`. A header alone does not count. A mid-line mention of those headers does not count. Empty, cut-off, or timed-out dumpsys fails. No owner reset in between. |

`false` and `absent` are expected to FAIL. That is the negative proof. The desired command id is `emulator-phase6`. The clear override uses noop id `emulator-phase6-clear`. Setting the restriction does not factory-reset the device.

The same workflow, job `AOSP ATD emulator policy (disallowAddUser, disallowFactoryReset)`, runs the four disallowAddUser legs, asserts device owner and `no_add_user`, then runs:

| Leg | `RESTRICTION` | `DISALLOW_FACTORY_RESET` | Required exit | Required line |
| --- | --- | --- | --- | --- |
| factory-absent | `disallowFactoryReset` | `absent` | 1 | `FAIL: restriction no_factory_reset not applied (DISALLOW_FACTORY_RESET=absent)` |
| factory-false | `disallowFactoryReset` | `false` | 1 | `FAIL: restriction no_factory_reset not applied (DISALLOW_FACTORY_RESET=false)` |
| factory-true-then-false | `disallowFactoryReset` | `true-then-false` | 0 | `PASS: no_factory_reset applied via disallowFactoryReset=true, then cleared by disallowFactoryReset=false with no owner reset` |
| factory-true | `disallowFactoryReset` | `true` | 0 | `PASS: no_factory_reset applied via policyFlags.disallowFactoryReset=true` |

The add-user post-run check is before these legs, because removing the test-only owner drops `no_add_user`. After `factory-true` the job asserts device owner and `no_factory_reset` (`post-run-factory-reset`). Each leg's job summary has a `restriction:` line, the `policy_restriction.py` output, the `GET /api/devices` row, and the PASS or FAIL line.

Path filters, the single boot retry, and `workflow_dispatch` are unchanged. There is no cron and no self-hosted runner.

### CI result

`ef5b380` (`ef5b38089fcab96c616547adc18f58b879e66e62`) is the code SHA. Green run on that SHA: https://github.com/themark-net/grapheneos-mdm/actions/runs/38287586817, job `AOSP ATD emulator policy (disallowAddUser, disallowFactoryReset)`. The boot retry step was skipped. The fingerprint was `Android/sdk_slim_x86_64/emu64x:15/AE3A.240806.019/12368160:userdebug/test-keys`. The image is an AOSP ATD emulator, not GrapheneOS. Attestation was not asserted. `pull_request` path filters match the whole PR diff, so a docs-only head re-runs this job. That later run is not cited here.

```
ASSERT OK: leg absent DISALLOW_ADD_USER=absent exit=1 expected=1
ASSERT OK: leg false DISALLOW_ADD_USER=false exit=1 expected=1
ASSERT OK: leg true-then-false DISALLOW_ADD_USER=true-then-false exit=0 expected=0
ASSERT OK: leg true DISALLOW_ADD_USER=true exit=0 expected=0
ASSERT OK: post-run device owner is net.themark.grapheneosmdm
ASSERT OK: post-run no_add_user is applied
ASSERT OK: leg factory-absent DISALLOW_FACTORY_RESET=absent exit=1 expected=1
ASSERT OK: leg factory-false DISALLOW_FACTORY_RESET=false exit=1 expected=1
ASSERT OK: leg factory-true-then-false DISALLOW_FACTORY_RESET=true-then-false exit=0 expected=0
ASSERT OK: leg factory-true DISALLOW_FACTORY_RESET=true exit=0 expected=0
ASSERT OK: post-run-factory-reset device owner is net.themark.grapheneosmdm
ASSERT OK: post-run-factory-reset no_factory_reset is applied
ASSERT OK: no cert or key file under /tmp/mdm-ci
ASSERT OK: no fleet.sqlite* under /tmp/mdm-ci
RESULT: PASS (AOSP ATD emulator, not GrapheneOS; attestation not asserted)
```

Protocol schemas and Android unit tests on the same code SHA: https://github.com/themark-net/grapheneos-mdm/actions/runs/38287586836

## Phase 7 — CI hardening

Issue #51. Pull request #52 merged to main at `8a7164c`. Not Feature GO. The image is still the AOSP ATD Android 15 emulator. Attestation is not asserted. No Pixel. No self-hosted runner. Handoff: [docs/ops/HANDOFF-p7-ci-hardening-2026-10-13.md](ops/HANDOFF-p7-ci-hardening-2026-10-13.md).

On API 34 and above the restriction step and the clear leg both require:

- an anchored `Local Policies:` or `Global Policies:` line in `dumpsys device_policy`, plus `UserRestrictionPolicyKey` or a non-empty indented line under that header (a header alone does not count; a mid-line mention does not count; API 35 ATD dumps have no `DevicePolicyEngine` line)
- `UserInfo{` in `dumpsys user`
- one restriction header: `Effective restrictions:`, `Device policy global restrictions:`, `Device policy local restrictions:`, or `Device policy restrictions:`
- no line matching `*** SERVICE ... DUMP TIMEOUT`

A missing marker fails and names that marker. The dump stays in the leg's log directory, which the workflow uploads (with the cert and sqlite exclusions). Do not loosen the matcher to make a timed-out capture green.

`policy_restriction.py` exits 0 when the token is applied, 1 when a recognised dump does not show it, 2 when the input is empty, unrecognised, timed out, unreadable, or missing an API 34 marker, and 3 on an argparse usage error. Exit 3 is not exit 2. Neither 2 nor 3 prints `restriction <token> is not applied`.

`CLEAR_LEG_STUB=1` sources [scripts/lib/clear-leg.sh](../scripts/lib/clear-leg.sh) and does not boot an emulator. It exits before any adb command when `SERIAL` or `ANDROID_SERIAL` is set, including set to empty. Host fixtures leave those unset. `API_LEVEL` defaults to 35 for the stub.

The upload exclusion for a BouncyCastle keystore is this line in [.github/workflows/emulator-policy.yml](../.github/workflows/emulator-policy.yml):

```
!/tmp/mdm-ci/**/*.bks
```

The cert guard entry in [scripts/lib/cert-guard.sh](../scripts/lib/cert-guard.sh) is:

```
-o -name '*.bks'
```

Both are present. A planted `secret.bks` fails the guard. The same bytes renamed to `secret.txt` do not.

`PolicyRestrictionTest` compares `userRestrictionUpdates` as a map, so pair order does not matter and a dropped key fails the test.

ASSERT lines are printed once, when the leg finishes. The wrapper writes them to `summary.txt` and does not print that file again.

Cursor Approval is not green. On `e852c6f` the Cursor Approval check concluded `neutral`. #52 merged to main at `8a7164c`. The waiver is issue #53 and stays open. This commit does not close it. emulator-policy ran on `e852c6f` and failed: https://github.com/themark-net/grapheneos-mdm/actions/runs/38441669873. That run is red. emulator-policy run 38446617330 (https://github.com/themark-net/grapheneos-mdm/actions/runs/38446617330) on 8744c58 is green; #52 merged to main at 8a7164c. The image is an AOSP ATD emulator. Attestation is not asserted.

## Phase 7.1 — Hygiene

Issue #53. Not Feature GO. Decisions: [docs/ops/AUTONOMOUS-DECISIONS-2026-10-16.md](ops/AUTONOMOUS-DECISIONS-2026-10-16.md). Six follow-ups from #52, in one pull request. The image is an AOSP ATD emulator. Attestation is not asserted. Issue #53 stays open for the Cursor Approval waiver.

## Next slice

After this Phase 7.1 pull request lands, org-can-do work is exhausted. The next step is the founder-only Pixel/GrapheneOS stop. See [docs/ROADMAP.md](ROADMAP.md).
