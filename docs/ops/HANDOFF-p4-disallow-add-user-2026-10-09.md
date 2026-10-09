# Handoff — Phase 4 disallowAddUser — 2026-10-09

Issue #45. Branch `build/p4-disallow-add-user`. Implemented with Grok Build headless on nimo, then benched by DevBot on AVD `mdm36`. Base: `origin/main` 4784a790 (Phase 3, #44). Not merged; needs Tester + Reviewer double-PASS.

## What shipped

- [scripts/emulator-policy-disallow-add-user.sh](../../scripts/emulator-policy-disallow-add-user.sh) — one AOSP ATD run. Enroll with `dpm set-device-owner`, one lab check-in, then `no_add_user`, then the operator list on 127.0.0.1:8787.
- [server/policy_restriction.py](../../server/policy_restriction.py) — reads `dumpsys device_policy` and `dumpsys user`. Exit 0 prints the matching lines when `no_add_user` is applied. Exit 1 when it is not.
- [server/tests/test_policy_restriction.py](../../server/tests/test_policy_restriction.py) — the parser cases that a substring match gets wrong. No emulator.

The agent already maps `policyFlags.disallowAddUser` true to `dpm.addUserRestriction(DISALLOW_ADD_USER)`, false to `clearUserRestriction`, and absent to leave the restriction untouched (`PolicyManager.kt`, tag `PolicyManager`, log line `Desired state policy flags applied`).

The desired state for the run is `schemaVersion` 1, `requiredPackages` empty, command `{"type":"noop","id":"emulator-phase4"}`, and `policyFlags` from `DISALLOW_ADD_USER`:

| `DISALLOW_ADD_USER` | `policyFlags` |
| --- | --- |
| `true` (default) | `{"disallowAddUser": true}` |
| `false` | `{"disallowAddUser": false}` |
| `absent` | `{}` |

## How to run

From this repo, with the user-space SDK (AVD `mdm36`, serial `emulator-5574`, `ANDROID_ADB_SERVER_PORT=5038`):

```bash
GRADLE_BIN=/path/to/gradle-8.9/bin/gradle scripts/emulator-policy-disallow-add-user.sh
DISALLOW_ADD_USER=false GRADLE_BIN=/path/to/gradle-8.9/bin/gradle scripts/emulator-policy-disallow-add-user.sh
DISALLOW_ADD_USER=absent GRADLE_BIN=/path/to/gradle-8.9/bin/gradle scripts/emulator-policy-disallow-add-user.sh
```

`OUT` defaults to `/tmp/mdm-phase4-policy`. The script writes a new `fleet.sqlite` there. Guest temp files are `mdm-phase4-*`. Procedure and the bench placeholder are in [docs/EMULATOR.md](../EMULATOR.md).

Parser check, no device:

```bash
python3 -m unittest discover -s server/tests -v
bash -n scripts/emulator-policy-disallow-add-user.sh
```

## Failure modes and recovery

- Restriction not applied: the script exits non-zero with `FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=<mode>)`. Read `PolicyManager` logcat for the policyFlags parse and for `Desired state policy flags applied`. Fix the flag or the device-owner state and run again. Do not claim the restriction applied.
- `DISALLOW_ADD_USER=false` and `absent` are expected to fail at that step. That is the negative proof. The PASS line is only for `true`, and only after the operator list shows the device id.
- If a negative mode still shows `no_add_user` applied, the script exits with `FAIL: restriction no_add_user applied during negative mode (DISALLOW_ADD_USER=<mode>)` and does not print PASS.
- Port 8787 already bound, or the UI bound to `0.0.0.0`, `*`, or `::`: exit non-zero. `ui_server.py` is started with `--host 127.0.0.1 --port 8787` only. Free the port and run again.
- Emulator or KVM unavailable: host blocker. The script prints the emulator log and exits. Do not install qemu, do not start a second emulator on ports 5574,5575, and do not fake a PASS.
- `dpm set-device-owner` rejected: the command output is in the log. No factory reset and no wipe.
- A non-test device owner blocks `pm clear`. The script builds with `-Pandroid.injected.testOnly=true`. If remove still reports a non-test admin, it stops the framework and deletes `device_owner_2.xml` and `device_policies.xml`. That is not a factory reset.
- Lab TLS fails if the guest uses `10.0.2.2`. The script uses `adb reverse tcp:8443` and `https://127.0.0.1:8443`. The cert SAN is `localhost` and `127.0.0.1`.
- Cleanup kills the lab server and `ui_server.py` and removes `adb reverse tcp:8443`. It does not stop the emulator.

## Non-goals

- This image is an AOSP ATD emulator. It is not GrapheneOS.
- Attestation is not asserted. The script does not run `same_db_attestation.py` and does not say verified boot passed.
- A Pixel running GrapheneOS stays founder-only.
- Issue #8 stays closed.
- Draft PR #42 stays untouched.
- No wipe, no `-wipe-data`, no factory reset.

## Next

Phase 5 in [docs/ROADMAP.md](../ROADMAP.md): run the operate script on a KVM runner. Open questions for Phase 5: the bench needs a user-space Gradle 8.9 (`GRADLE_BIN`) because the tree has no `gradlew`; a KVM runner has to supply that too.

## Bench result 2026-10-09 (nimo)

- `DISALLOW_ADD_USER=absent`: exit 1, `FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=absent)`.
- `DISALLOW_ADD_USER=false`: exit 1, `FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=false)`.
- `DISALLOW_ADD_USER=true`: exit 0. `dumpsys user` `Effective restrictions:` lists `no_add_user`; `dumpsys device_policy` shows `UserRestrictionPolicyKey userRestriction_no_add_user` resolved `BooleanPolicyValue { mValue= true }`. `ui_server.py` listened on `127.0.0.1:8787` only and `GET /api/devices` listed `deviceId a7fdb4548155d650`.
- The device row has `attestationStatus none` and `verifiedBootState null`. Attestation was not passed and is not claimed.
- Fixes found on the bench: `adb logcat -s` keeps only the last level per tag (now one level per tag), and the Android 15 `userRestriction_` key prefix (parser + test with captured text).

Full log: [docs/EMULATOR.md](../EMULATOR.md#bench-log-2026-10-09).
