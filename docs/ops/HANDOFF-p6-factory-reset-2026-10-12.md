# Handoff — Phase 6 disallowFactoryReset — 2026-10-12

Issue #49. Branch `build/p6-factory-reset`, based on `main` at `e43fc37` (Phase 5, PR #48, merged). Not Feature GO. Draft PR #42 is untouched. Issue #8 stays closed.

The image is the AOSP ATD Android 15 emulator (`system-images;android-35;aosp_atd;x86_64`, `avd-name: mdm36`). It is not GrapheneOS. Attestation is not asserted. No Pixel. The operate script does not factory-reset or wipe.

Lane: nimo was offline, so this ran as a Cursor cloud agent. No self-hosted runner and no host changes.

## What shipped

- [.github/workflows/emulator-policy.yml](../../.github/workflows/emulator-policy.yml) — same GitHub-hosted `ubuntu-latest` KVM job, now named `AOSP ATD emulator policy (disallowAddUser, disallowFactoryReset)`. Path filters, the single boot retry (`/tmp/mdm-ci/script-started`), `workflow_dispatch`, and the 45 minute timeout are unchanged. No cron. The upload excludes `fleet.sqlite*` and `*.pem` / `*.p12` / `*.key` / `*.crt` / `*.der` / `*.cer` / `*.pfx` / `*.jks` / `*.keystore` / `*.csr` / `*.bks`, plus `certs/`.
- [scripts/ci-emulator-policy.sh](../../scripts/ci-emulator-policy.sh) — runs disallowAddUser (`absent`, `false`, `true-then-false`, `true`), asserts device owner and `no_add_user`, then runs disallowFactoryReset under the same four modes (`factory-absent`, `factory-false`, `factory-true-then-false`, `factory-true`) and asserts device owner and `no_factory_reset`. Every exit code is asserted. Each leg writes a `restriction:` line, the `policy_restriction.py` output, the `GET /api/devices` row, and the PASS or FAIL line to `$GITHUB_STEP_SUMMARY`. Before exit it deletes `fleet.sqlite*` under the log dir. The cert check also rejects `.der`, `.cer`, `.pfx`, `.jks`, `.keystore`, `.csr`, and `.bks`.
- [scripts/emulator-policy-disallow-add-user.sh](../../scripts/emulator-policy-disallow-add-user.sh) — `RESTRICTION=disallowAddUser` (default) or `disallowFactoryReset`. The factory-reset mode env is `DISALLOW_FACTORY_RESET`. `true-then-false` exits 0 only when the after-false `device_policy` dump is non-empty and contains `DevicePolicyEngine`, `UserRestrictionPolicyKey`, or a Device Owner line, and `policy_restriction.py` exits 1 and prints `restriction <token> is not applied`. Exit 2 is a failed clear. The two mode env vars must not both be set. The default invocation and the add-user PASS/FAIL lines are unchanged.
- [server/policy_restriction.py](../../server/policy_restriction.py) — same match rules. Empty or unrecognised dumpsys exits 2 and prints `dumpsys input is empty or unrecognised`, not the not-applied sentence. A recognised dump that lacks the token still exits 1 with `restriction <token> is not applied`. Tests cover `no_factory_reset` on the Android 15 `userRestriction_` key, an explicit false, empty and cut-off input, and that a `no_factory_reset` dump is not `no_add_user` (and the reverse).
- App: `PolicyManager.userRestrictionUpdates` already maps `disallowFactoryReset` true to `UserManager.DISALLOW_FACTORY_RESET` (`no_factory_reset`) and false to clear. `PolicyRestrictionTest` lists that pair for both values. The desired-state schema already has the flag. No app change.

Docs: [docs/EMULATOR.md](../EMULATOR.md), [docs/ROADMAP.md](../ROADMAP.md), [docs/PENDING-HANDOFF.md](../PENDING-HANDOFF.md), [docs/ops/AUTONOMOUS-DECISIONS-2026-10-12.md](AUTONOMOUS-DECISIONS-2026-10-12.md).

## How to run

On GitHub: a PR that touches the filtered paths, or Actions → "Emulator policy (AOSP ATD)" → Run workflow.

On nimo (unchanged add-user default):

```bash
GRADLE_BIN=/tmp/gradle-8.9/bin/gradle scripts/emulator-policy-disallow-add-user.sh
RESTRICTION=disallowFactoryReset GRADLE_BIN=/tmp/gradle-8.9/bin/gradle scripts/emulator-policy-disallow-add-user.sh
RESTRICTION=disallowFactoryReset DISALLOW_FACTORY_RESET=true-then-false GRADLE_BIN=/tmp/gradle-8.9/bin/gradle scripts/emulator-policy-disallow-add-user.sh
```

`false` and `absent` are expected to exit 1. Do not factory-reset the emulator to prove the flag.

Local checks, no device:

```bash
python3 -m unittest discover -s server/tests -v
python3 -m unittest discover -s protocol/tests -v
bash -n scripts/emulator-policy-disallow-add-user.sh scripts/ci-emulator-policy.sh
actionlint .github/workflows/*.yml
```

## Failure modes and recovery

- `/dev/kvm` missing or the emulator does not boot within `emulator-boot-timeout` (900 s): the runner step fails before the wrapper runs. One retry only when `/tmp/mdm-ci/script-started` is missing. Do not move to a self-hosted runner.
- A factory-reset leg exits 1 on `true` because dumpsys never shows `no_factory_reset`: read `factory-true/device_policy.txt`, `dumpsys_user.txt`, and `PolicyManager` logcat. Fix the token or the parser. Do not skip the leg.
- `FAIL: step clear: after-false dumpsys is empty`, or `FAIL: step clear: after-false device_policy dump lacks DevicePolicyEngine, UserRestrictionPolicyKey, or Device Owner`: the capture is empty or cut off. That is not a clear.
- `FAIL: step clear: policy_restriction.py rejected empty or unrecognised dumpsys (exit=2)`: the parser refused the input. That is not a clear.
- `FAIL: step clear: policy_restriction.py did not report 'restriction no_factory_reset is not applied'`: the helper failed for a reason other than "not applied" (unreadable dumpsys, bad token). That is not a clear.
- `FAIL: step clear: no_factory_reset still applied after disallowFactoryReset=false`: the false check-in did not clear it. Read `device_policy-after-false.txt`.
- Post-run `no_add_user` fails after the factory-reset legs were inserted ahead of that check: the owner removal drops the previous restriction. The add-user post-run check has to stay before those legs.
- A `fleet.sqlite*` file in the artifact: the WAL can hold an attestation chain. The wrapper should have deleted it, and the upload excludes it. Do not publish the file.

## CI result

`ef5b380` (`ef5b38089fcab96c616547adc18f58b879e66e62`) is the code SHA. Emulator run: https://github.com/themark-net/grapheneos-mdm/actions/runs/38287586817

Job: `AOSP ATD emulator policy (disallowAddUser, disallowFactoryReset)`, conclusion success. The boot-retry step was skipped. The fingerprint was `Android/sdk_slim_x86_64/emu64x:15/AE3A.240806.019/12368160:userdebug/test-keys`. The image is an AOSP ATD emulator, not GrapheneOS. Attestation was not asserted. `pull_request` path filters match the whole PR diff, so a docs-only head re-runs the job. That later URL is not recorded in a follow-up commit.

Protocol schemas and Android unit tests on the same code SHA: https://github.com/themark-net/grapheneos-mdm/actions/runs/38287586836

```
ASSERT OK: leg absent DISALLOW_ADD_USER=absent exit=1 expected=1
  FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=absent)
ASSERT OK: leg false DISALLOW_ADD_USER=false exit=1 expected=1
  FAIL: restriction no_add_user not applied (DISALLOW_ADD_USER=false)
ASSERT OK: leg true-then-false DISALLOW_ADD_USER=true-then-false exit=0 expected=0
  PASS: no_add_user applied via disallowAddUser=true, then cleared by disallowAddUser=false with no owner reset; deviceId=3d43cca620302e32. AOSP ATD emulator, not GrapheneOS; attestation not asserted.
ASSERT OK: leg true DISALLOW_ADD_USER=true exit=0 expected=0
  PASS: no_add_user applied via policyFlags.disallowAddUser=true; operator list on 127.0.0.1:8787 shows deviceId=3d43cca620302e32. AOSP ATD emulator, not GrapheneOS; attestation not asserted.
ASSERT OK: post-run device owner is net.themark.grapheneosmdm
ASSERT OK: post-run no_add_user is applied
ASSERT OK: leg factory-absent DISALLOW_FACTORY_RESET=absent exit=1 expected=1
  FAIL: restriction no_factory_reset not applied (DISALLOW_FACTORY_RESET=absent)
ASSERT OK: leg factory-false DISALLOW_FACTORY_RESET=false exit=1 expected=1
  FAIL: restriction no_factory_reset not applied (DISALLOW_FACTORY_RESET=false)
ASSERT OK: leg factory-true-then-false DISALLOW_FACTORY_RESET=true-then-false exit=0 expected=0
  PASS: no_factory_reset applied via disallowFactoryReset=true, then cleared by disallowFactoryReset=false with no owner reset; deviceId=3d43cca620302e32. AOSP ATD emulator, not GrapheneOS; attestation not asserted.
ASSERT OK: leg factory-true DISALLOW_FACTORY_RESET=true exit=0 expected=0
  PASS: no_factory_reset applied via policyFlags.disallowFactoryReset=true; operator list on 127.0.0.1:8787 shows deviceId=3d43cca620302e32. AOSP ATD emulator, not GrapheneOS; attestation not asserted.
ASSERT OK: post-run-factory-reset device owner is net.themark.grapheneosmdm
ASSERT OK: post-run-factory-reset no_factory_reset is applied
ASSERT OK: no cert or key file under /tmp/mdm-ci
ASSERT OK: no fleet.sqlite* under /tmp/mdm-ci
RESULT: PASS (AOSP ATD emulator, not GrapheneOS; attestation not asserted)
```

Local stub, no emulator (`server/tests/test_clear_leg_stub.py`). An empty dumpsys and a cut-off device_policy dump both FAIL the clear leg:

```
FAIL: step clear: after-false dumpsys is empty
FAIL: step clear: after-false device_policy dump lacks DevicePolicyEngine, UserRestrictionPolicyKey, or Device Owner
```

`policy_restriction.py` on empty or marker-less input exits 2 and prints `dumpsys input is empty or unrecognised`. It does not print `is not applied`.
