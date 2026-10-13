# Handoff — Phase 7 CI hardening — 2026-10-13

Issue #51. Branch `build/p7-ci-hardening`, based on `main` at `0c54704` (`0c54704e5a4218cbf09d752599edb3b0e19e1f5e`, Phase 6, PR #50). Not Feature GO. Not merged. No pull request was opened. Draft PR #42 is untouched. Issue #8 stays closed.

The image is the AOSP ATD Android 15 emulator (`system-images;android-35;aosp_atd;x86_64`, `avd-name: mdm36`). It is not GrapheneOS. Attestation is not asserted. No Pixel. The operate script does not factory-reset or wipe. No self-hosted runner. No host or runner change.

Decisions: [AUTONOMOUS-DECISIONS-2026-10-13.md](AUTONOMOUS-DECISIONS-2026-10-13.md). The required line is there verbatim: Phase 7 = CI hardening | alt same-db on runner, third restriction | why = trust the check before growing it.

## Definition of done

CEO comment on issue #51 asks for each hardening item done or declined, with the reason in the PR body. This session does not open a pull request, so the reasons are here. None of the seven items is declined.

| Item | Result | Reason |
| --- | --- | --- |
| API 34+ `DevicePolicyEngine` section, `UserInfo{`, restriction header, and fail on `*** SERVICE ... DUMP TIMEOUT` | Done | A cut-off or timed-out dumpsys must not count as applied or cleared. The failure names the missing marker. The dump stays in the leg log dir, which the workflow uploads. |
| Move `CLEAR_LEG_STUB` into a sourced lib and refuse it when adb or `SERIAL` is configured | Done | [scripts/lib/clear-leg.sh](../../scripts/lib/clear-leg.sh) is sourced by [scripts/emulator-policy-restriction.sh](../../scripts/emulator-policy-restriction.sh). Stub mode exits before adb when the caller set `SERIAL` or `ANDROID_SERIAL`. |
| Distinct exit code for argparse usage versus empty or unrecognised dumpsys | Done | Exit 2 is empty, unrecognised, timeout, or a missing API 34 marker. Exit 3 is argparse usage. Exit 3 does not reuse 2. Neither prints `restriction <token> is not applied`. |
| Explicit `.bks` in the upload exclusions and the CI cert guard | Done | The workflow path line is `!/tmp/mdm-ci/**/*.bks`. The guard predicate is its own line `-o -name '*.bks'`. That settles the Tester and Reviewer disagreement by pointing at the lines. |
| Compare Kotlin `PolicyRestrictionTest` pairs as a map | Done | `trueFlagsAddRestrictions` and `falseFlagsClearRestrictions` compare `updates.toMap()` to a `mapOf` and assert `expected.size == updates.size`, so a duplicate key fails. This is the only unit change. `PolicyManager.kt` is unchanged. |
| Rename the operate script | Done | The path is [scripts/emulator-policy-restriction.sh](../../scripts/emulator-policy-restriction.sh). Both `pull_request` and `push` path lists include that file and `scripts/lib/**`. The retired filename has zero hits in `.yml`, `.yaml`, `.sh`, `.py`, `.md`, and `.kts`. Historical handoffs now name the new path. |
| Node 20 action deprecations and duplicate ASSERT lines | Done | `ci.yml` and `emulator-policy.yml` pin checkout v7.0.1, setup-java v6.0.1, setup-python v7.0.0, upload-artifact v7.0.2, setup-gradle v6.4.0, and setup-android v4.0.4. `android-emulator-runner` v2.38.0 was already Node 24 and is unchanged. The wrapper no longer cats `summary.txt`, so each ASSERT line is printed once. |

## Negative proofs

Each proof is a host fixture. The `ubuntu-latest` KVM job has not run on this head, so these are not a green emulator-policy run.

- Bad dumpsys, API 35: a factory-false dump that still exits 1 with `restriction <token> is not applied` fails with exit 2 when the `DevicePolicyEngine` section, `UserInfo{`, or a restriction header is removed. `server/tests/test_policy_restriction.py` (`test_api35_names_each_missing_marker`). The shell clear leg names `lacks a DevicePolicyEngine section`, `lacks UserInfo{`, and `lacks a restriction header` (`server/tests/test_clear_leg_stub.py`). `Restrictions:` alone is not a header.
- Timeout: the same applied dump plus a `*** SERVICE ... DUMP TIMEOUT` line exits 2 from `policy_restriction.py` and does not print `is not applied`. The clear-leg stub exits 1 and does not print `PASS`. The restriction step names `dumpsys contains *** SERVICE ... DUMP TIMEOUT`.
- API gate: a Device Owner marker with no `DevicePolicyEngine` section passes the stub at `API_LEVEL=33` and fails it at `API_LEVEL=35`.
- Stub with adb: the same recognised clear passes with `SERIAL` and `ANDROID_SERIAL` unset, then fails `CLEAR_LEG_STUB refused because adb/SERIAL is configured` when either variable is `emulator-5554`. No `set-device-owner` line.
- Usage versus empty: a CLI with no arguments exits 3 and prints `usage:`. Empty dump files still exit 2 and do not print `usage:`.
- `.bks` mutation: `secret.bks` is a cert-guard hit. The same bytes renamed to `secret.txt` are not. A `certs/` directory is also a hit. The workflow text contains the path line `!/tmp/mdm-ci/**/*.bks` once, and the guard contains `-o -name '*.bks'`.
- Rename: the orphan scan fails if the retired filename remains, if the new script is missing, or if either path-filter line appears other than twice.
- Node 24 and ASSERT: the workflow text must contain the Node 24 pin strings and must not contain the Node 20 refs the main job annotated. The wrapper must not contain `cat "$SUMMARY"`.
- Kotlin map: not executed on this machine. There is no Gradle on `PATH` and no `gradlew`. The size check is what fails a duplicate key. Do not read this handoff as a green Android unit run.

If a stricter marker flakes on the API 35 ATD image, the job must fail and name the missing marker, and the dump must stay in the uploaded log dir. Do not loosen the matcher to make that capture green.

## What shipped

- [scripts/lib/clear-leg.sh](../../scripts/lib/clear-leg.sh) — sourced clear-leg gate. API 34+ marker checks, timeout rejection on every API level, exit 2 and exit 3 are not a clear, and `run_clear_leg_stub` refuses a caller `SERIAL` or `ANDROID_SERIAL`.
- [scripts/lib/cert-guard.sh](../../scripts/lib/cert-guard.sh) — certificate and keystore hit list, including `-o -name '*.bks'`.
- [scripts/emulator-policy-restriction.sh](../../scripts/emulator-policy-restriction.sh) — same two restrictions. Saves the caller serial before the nimo `SERIAL` default, sources the clear-leg lib, runs the stub before adb, and reads `ro.build.version.sdk` for a real run.
- [scripts/ci-emulator-policy.sh](../../scripts/ci-emulator-policy.sh) — post-run parser gets the device SDK. Exit 2 and exit 3 are named. ASSERT lines go to the summary file once. The end of the log prints `summary file:` and does not cat the file.
- [server/policy_restriction.py](../../server/policy_restriction.py) — `--api-level`. Exit 3 is argparse. Exit 2 covers empty, unrecognised, timeout, and a missing API 34 marker.
- [.github/workflows/emulator-policy.yml](../../.github/workflows/emulator-policy.yml) — Node 24 pins, new path filters, and the `.bks` exclusion left as a real `path:` line. Job name, `ubuntu-latest`, the KVM udev step, the 45 minute timeout, and the emulator-runner SHA are unchanged.
- [.github/workflows/ci.yml](../../.github/workflows/ci.yml) — same Node 24 pins. Triggers are still `push` to `main`, `feat/**`, and `fix/**`, plus `pull_request` to `main`. A push of `build/p7-ci-hardening` does not match.
- [app/src/test/java/net/themark/grapheneosmdm/policy/PolicyRestrictionTest.kt](../../app/src/test/java/net/themark/grapheneosmdm/policy/PolicyRestrictionTest.kt) — map comparison. No production Kotlin change.

Docs: [docs/ROADMAP.md](../ROADMAP.md), [docs/EMULATOR.md](../EMULATOR.md), [docs/PENDING-HANDOFF.md](../PENDING-HANDOFF.md), this file, and [AUTONOMOUS-DECISIONS-2026-10-13.md](AUTONOMOUS-DECISIONS-2026-10-13.md).

## Cursor Approval

The waiver stays open. It is not closed.

- PR #50 head `c9e646b94402a368cc9ff859ab763ad3e39980c4`: check `Cursor Approval Agent: Pull Request Router and Approver` (app `cursor`) concluded `neutral`. Summary: `Approval Agent run encountered an error`. Run `bc-9a8d6e3e-32bc-4fed-8c99-406f4b3832f4`.
- The same check was `success` on `ef5b38089fcab96c616547adc18f58b879e66e62`.
- Main `0c54704` has three green GitHub Actions checks (Android unit tests, Protocol schemas + lab check-in, AOSP ATD emulator policy) and no Cursor Approval check.
- This branch was not opened as a pull request. A push of `build/p7-ci-hardening` does not start Cursor Approval. The check has not run on the Phase 7 head.

## CI on this head

The emulator-policy job has not run on this head. [.github/workflows/emulator-policy.yml](../../.github/workflows/emulator-policy.yml) runs on `pull_request` (path filtered), on `push` to `main` (path filtered), and on `workflow_dispatch`. A push of `build/p7-ci-hardening` is none of those. This session does not dispatch the workflow and does not open a pull request.

The path filters do include `scripts/emulator-policy-restriction.sh` and `scripts/lib/**` on both the pull-request list and the main-push list. A later pull request that touches those paths will start the job. Until that run exists, do not call this head CI-green, and do not treat the merge gate as met.

`ci.yml` also does not run on this branch name.

Merge gate from the CEO comment, not performed here: Tester and Reviewer double-PASS at the exact head SHA with a green emulator-policy run, then an org merge that says `Closes #51`. Founder does not gate. This session does not merge.

## Next slice

None. This drive is at the Pixel/GrapheneOS founder-only stop. No remaining org-can-do slice moves the founder bar.

The founder bar is the same device-owner check-in loop on a Pixel running GrapheneOS, with `attestationStatus` `ok`. The AOSP ATD emulator does not meet that bar. The Phase 3 same-database script on this runner records `chain_invalid`. That is not attestation progress. A third restriction does not move the bar. Pixel enroll, fleet CA material, the production control plane, and the license stay founder-needed. Do not start them from an org harness.

## How to check locally

No device:

```bash
python3 -m unittest discover -s server/tests -v
python3 -m unittest discover -s protocol/tests -v
bash -n scripts/emulator-policy-restriction.sh scripts/ci-emulator-policy.sh scripts/lib/clear-leg.sh scripts/lib/cert-guard.sh
```

Android unit tests need Gradle. This worktree has no `gradle` and no `gradlew`. `actionlint` and `shellcheck` are also absent on this machine.

## Failure modes and recovery

- A stricter marker flakes on API 35 ATD: the leg fails and names the missing marker (`DevicePolicyEngine` section, `UserInfo{`, restriction header, or `DUMP TIMEOUT`). The dump stays under the leg log dir and the workflow uploads that dir, minus sqlite and cert exclusions. Fix the matcher or the capture. Do not loosen the rule to make the leg green.
- Exit 2 or exit 3 on the clear leg: that is a failed clear, not "not applied". Read the dumpsys files in the leg directory.
- `CLEAR_LEG_STUB refused because adb/SERIAL is configured`: the caller exported `SERIAL` or `ANDROID_SERIAL`. Unset them for a host fixture. Do not point stub mode at an emulator.
- The emulator job does not appear after a future pull request: the path filter missed the changed files. Both trigger lists must name `scripts/emulator-policy-restriction.sh` and `scripts/lib/**`. Do not delete those lines to make a docs-only check look quiet.
- Cursor Approval stays neutral or missing: leave the waiver open. Do not waive it by editing this file into a success claim.
