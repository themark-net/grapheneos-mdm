# Handoff — Phase 5 GitHub-hosted KVM runner — 2026-10-09

Issue #47. Branch `build/p5-gha-kvm`, based on `main` at `51c6c3b` (Phase 4, PR #46, merged). Not merged; needs Tester + Reviewer double-PASS. Not Feature GO.

The image is the AOSP ATD Android 15 emulator (`system-images;android-35;aosp_atd;x86_64`). It is not GrapheneOS. Attestation is not asserted. No Pixel.

## What shipped

- [.github/workflows/emulator-policy.yml](../../.github/workflows/emulator-policy.yml) — job `AOSP ATD emulator policy (disallowAddUser)` on `ubuntu-latest`. Enables `/dev/kvm` with a udev rule, installs Temurin 17, Gradle 8.9 and Python 3.12 with setup actions, builds the test-only debug APK, boots the emulator with `reactivecircus/android-emulator-runner` v2.38.0 (pinned to `a421e43855164a8197daf9d8d40fe71c6996bb0d`), runs the CI wrapper, and uploads `/tmp/mdm-ci` as `emulator-policy-logs` with `if: always()` (lab certs excluded). Path-filtered `pull_request` and `push` to `main`, plus `workflow_dispatch`. No cron. Concurrency cancel-in-progress. Timeout 45 minutes.
- [scripts/ci-emulator-policy.sh](../../scripts/ci-emulator-policy.sh) — runs the operate script four times and asserts each exit code (`absent` 1, `false` 1, `true-then-false` 0, `true` 0) and the expected FAIL/PASS line. A negative leg that prints `PASS:` fails. Then it asserts the post-run state (device owner, `no_add_user` applied). Prints `ASSERT OK:` / `ASSERT FAIL:` lines and `RESULT: PASS|FAIL`.
- [scripts/emulator-policy-disallow-add-user.sh](../../scripts/emulator-policy-disallow-add-user.sh):
  - `UI_PORT` is used everywhere (listener check, error text, PASS line). Default 8787. `LAB_URL` follows `PORT` (default 8443).
  - New mode `DISALLOW_ADD_USER=true-then-false`: apply true, then a per-device override `{"disallowAddUser": false}` through `fleet_store.py set-desired`, a second broadcast with no owner reset and no `pm clear`, and `no_add_user` must be gone.
  - Header lists the env overrides. nimo defaults (`emulator-5574`, adb server 5038, AVD `mdm36`) are unchanged.
- Docs: [docs/EMULATOR.md](../EMULATOR.md) (Phase 5 section, post-run state, env overrides), [docs/ROADMAP.md](../ROADMAP.md), [docs/PENDING-HANDOFF.md](../PENDING-HANDOFF.md). Stale "bench placeholder" and "open issue list is empty" lines removed.

App code: `PolicyManager.applyDesiredState` already calls `dpm.clearUserRestriction(admin, DISALLOW_ADD_USER)` when `disallowAddUser` is `false` (`userRestrictionUpdates`, test `PolicyRestrictionTest.falseFlagsClearRestrictions`). No app change was needed.

## How to run

On GitHub: any PR that touches the filtered paths, or Actions → "Emulator policy (AOSP ATD)" → Run workflow.

On nimo (unchanged defaults):

```bash
GRADLE_BIN=/tmp/gradle-8.9/bin/gradle scripts/emulator-policy-disallow-add-user.sh
DISALLOW_ADD_USER=true-then-false GRADLE_BIN=/tmp/gradle-8.9/bin/gradle scripts/emulator-policy-disallow-add-user.sh
```

Local checks, no device:

```bash
python3 -m unittest discover -s server/tests -v
python3 -m unittest discover -s protocol/tests -v
bash -n scripts/emulator-policy-disallow-add-user.sh scripts/ci-emulator-policy.sh
actionlint .github/workflows/*.yml
```

## Failure modes and recovery

- `/dev/kvm` missing or the emulator does not boot within `emulator-boot-timeout` (900 s): the runner step fails before the wrapper runs. Read the step log. Do not move to a self-hosted runner without the founder.
- Fingerprint is not `Android/sdk_slim_x86_64/emu64x:15/*`: the operate script exits. The ATD image on the runner changed; look at `device-*/fingerprint.txt` in the artifact before widening the pattern.
- A leg exits with the wrong code: `ASSERT FAIL: leg <name> … exit=<rc> expected=<want>`. The leg's own log is `<name>.log` and `<name>/result.txt` in the artifact, with `device-<name>/logcat.txt` and dumpsys.
- `FAIL: step clear: no_add_user still applied after disallowAddUser=false`: the false check-in did not clear the restriction. Read `true-then-false/device_policy-after-false.txt` and `PolicyManager` logcat.
- Post-run assertion fails: the last `true` leg left no owner or no restriction. Read `device-post-run/`.

## CI result

Green on `ddf5ff9` (`ddf5ff93d7a2c9d67bc879c7fab2d996a10cc233`), PR #48.

Run: https://github.com/themark-net/grapheneos-mdm/actions/runs/37974703736

Job: `AOSP ATD emulator policy (disallowAddUser)`, conclusion success. `/dev/kvm` was mode `0666`. The fingerprint was `Android/sdk_slim_x86_64/emu64x:15/AE3A.240806.019/12368160:userdebug/test-keys`, which matches the nimo guard, so no override was added. The image is an AOSP ATD emulator, not GrapheneOS. Attestation was not asserted.

```
ASSERT OK: leg absent DISALLOW_ADD_USER=absent exit=1 expected=1
  FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=absent)
ASSERT OK: leg false DISALLOW_ADD_USER=false exit=1 expected=1
  FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=false)
ASSERT OK: leg true-then-false DISALLOW_ADD_USER=true-then-false exit=0 expected=0
  PASS: no_add_user applied via disallowAddUser=true, then cleared by disallowAddUser=false with no owner reset; deviceId=39e2226490a7ea0a. AOSP ATD emulator, not GrapheneOS; attestation not asserted.
ASSERT OK: leg true DISALLOW_ADD_USER=true exit=0 expected=0
  PASS: no_add_user applied via policyFlags.disallowAddUser=true; operator list on 127.0.0.1:8787 shows deviceId=39e2226490a7ea0a. AOSP ATD emulator, not GrapheneOS; attestation not asserted.
ASSERT OK: post-run device owner is net.themark.grapheneosmdm
ASSERT OK: post-run no_add_user is applied
RESULT: PASS (AOSP ATD emulator, not GrapheneOS; attestation not asserted)
```

Android unit tests on the same SHA also succeeded: https://github.com/themark-net/grapheneos-mdm/actions/runs/37974703559
