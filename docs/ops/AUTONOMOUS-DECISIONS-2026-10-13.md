# Autonomous decisions — 2026-10-13

Phase 7, issue #51. One line each: choice | alternatives | why

- Phase 7 = CI hardening | alt same-db on runner, third restriction | why = trust the check before growing it
- Rename the operate script to `scripts/emulator-policy-restriction.sh` and point both path filters at that file plus `scripts/lib/**` | keep the Phase 4 filename; add a second script | the script already covers two restrictions; a filter that still names the old file would not run the job
- On API 34 and above require a `DevicePolicyEngine` section, `UserInfo{`, and a restriction header, and fail a `*** SERVICE ... DUMP TIMEOUT` line | keep the Phase 6 OR-marker; drop a timed-out capture to green | a cut-off dumpsys must not count as applied or cleared; the missing marker is named and the dump stays in the log dir
- Apply the API 34 markers only when `--api-level` is 34 or higher | require `DevicePolicyEngine` even when the flag is omitted | parser fixtures that omit the flag stay valid; the operate script and the CI post-run pass the device SDK
- `policy_restriction.py` usage errors exit 3; empty, unrecognised, timeout, and a missing API 34 marker stay exit 2 | reuse exit 2 for argparse | a usage error is not an empty dumpsys and must not look like a failed clear
- `CLEAR_LEG_STUB` lives in `scripts/lib/clear-leg.sh` and refuses when the caller set `SERIAL` or `ANDROID_SERIAL` | leave the stub inline; probe `adb devices` | stub mode must not aim at an adb target
- Name `*.bks` on its own workflow path line `!/tmp/mdm-ci/**/*.bks` and its own cert-guard predicate `-o -name '*.bks'` | a YAML comment; rely on the Phase 6 suffix list | Tester and Reviewer disagreed; the lines are the settlement
- Pin the JavaScript actions in `ci.yml` and `emulator-policy.yml` to Node 24 SHAs | leave the Node 20 refs the main job annotated; float a major tag | those refs are the deprecation this phase removes; `android-emulator-runner` v2.38.0 was already Node 24 and stays
- Print each ASSERT line once and echo `summary file:` instead of `cat "$SUMMARY"` | keep the second print | `note` already tees the line, so catting the summary reprints it
- `PolicyRestrictionTest` compares restriction pairs with `toMap()` plus a size check | keep the ordered list of pairs | pair order does not matter and a duplicate key fails the size check; this is the only unit change
- Next slice is the Pixel/GrapheneOS founder-only stop | put the Phase 3 same-database script on this runner; add a third restriction | neither moves `attestationStatus` `ok` on a Pixel running GrapheneOS; `chain_invalid` on the AOSP ATD image is not attestation progress
- Cursor Approval waiver stays open | call the waiver closed because `ef5b380` was green | PR #50 head `c9e646b` concluded `neutral`; main `0c54704` has no Cursor check; pull request #52 is open and on `e852c6f` the check concluded `neutral`
- API 35 ATD section marker is an anchored `Local Policies:` or `Global Policies:` line | keep requiring `DevicePolicyEngine`; accept either header as a substring | run 38441669873 `true/device_policy.txt` has no `DevicePolicyEngine` line; the real lines are `Local Policies:` and `Global Policies:`; a mid-line mention must not count
- `assert_post_run` saves and restores the prior errexit state | leave the unconditional `set -e` | the wrapper starts with errexit off; `set -e` stayed on, so factory-absent exit 1 skipped the remaining factory legs, the cert guard, and RESULT (run 38441669873)
- Pull request #52 stays open and this commit does not merge | open a second pull request; merge on a red emulator job | #52 is the Phase 7 pull request; emulator-policy on `e852c6f` is red (run 38441669873); the repair has not had a green emulator-policy run
