# Roadmap

Phases for grapheneos-mdm after Feature GO (2026-10-02). Host-only work and the AOSP emulator are **org-can-do**. A physical Pixel, real GrapheneOS, money, legal, and credentials are **founder-needed**.

Issue #8 stays closed. GrapheneOS SetupWizard2 PR #40 is still open and still has no 6-tap scanner. This repo does not grow that wizard.

## Success bar

A bench device is device owner, checks in twice over mTLS to one lab sqlite, and the second inventory's attestation status is the server's judgment of a challenge that database issued. The device is listed on the localhost operator page. One desired-state restriction from that server is applied on the device.

`attestationStatus` `ok` means the keymint chain signs to `server/attestation-roots.pem` and `verifiedBootState` is `Verified`. Any other status is a recorded result, not attestation success.

The org bar is the AOSP ATD emulator. The founder bar is the same loop on a Pixel running GrapheneOS. The emulator does not meet the founder bar.

## Done

### Phase 1 — Lab agent and operator page

Exit: the agent checks in with mutual TLS, applies desired state, and the lab sqlite is editable on 127.0.0.1:8787. Met at PR #34, squash `49a16c82964e4f35fdffd5c3cb7545728cdaa5cd`.

Shipped in that phase: mTLS check-in, catalog install, WorkManager scheduling, restriction clear, fleet sqlite, `minSecurityPatch` report, password / hide / suspend / uninstall, permission grants, GPS fix, key attestation challenge, preferred activities, user list, updater settings intent, QR handlers, fleet groups, provisioning QR payload, Ansible `group_vars` sync, localhost operator page with the wipe confirm gate.

### Phase 2 — Proof without a Pixel

Exit: a host command can insert one labeled simulated row, and an AOSP ATD emulator can become device owner and POST `/v1/checkin`. Met 2026-10-03.

| | |
| --- | --- |
| #35 / PR #37 | Host-only `--simulate`. Squash `38d12fa7aa806cba5c9b2e4e2733ae76b143f6ac`. |
| #36 / PR #38 | Emulator device owner. Squash `b5fd229f86326b7c428365c8f49b6fb218a6d002`. |

The #38 check-in row was `attestationStatus challenge_mismatch` and `verifiedBootState` null. One check-in against a new sqlite cannot match: the nonce arrives in the response, and that run also left a previous nonce in the app. Phase 3 is the second check-in against the database that issued the nonce.

### Phase 3 — Same-database emulator attestation

**org-can-do.** Implemented on this branch. Still not Feature GO. A physical Pixel and a GrapheneOS image stay founder-only.

Script: [scripts/emulator-same-db-attestation.sh](../scripts/emulator-same-db-attestation.sh). Procedure: [docs/EMULATOR.md](EMULATOR.md). A new sqlite, `pm clear` of `net.themark.grapheneosmdm` after removing the test-only device owner, then two check-ins. The second lab line is the record. The script exits non-zero when that observation is missing or when `attestationStatus` is `challenge_mismatch`, `none`, `missing`, `parse_error`, or `unsupported`.

`ok` still means the chain trusts `server/attestation-roots.pem` and `verifiedBootState` is `Verified`. The 2026-10-06 bench run on `userdebug` / `test-keys` printed second-check-in `attestationStatus chain_invalid` and `verifiedBootState` null. That is the server record. `boot_unverified` is a record only when that chain check passed and boot is not `Verified`. The success line quotes the status. It does not call verified boot passed unless the status is `ok`. The full row is in [docs/EMULATOR.md](EMULATOR.md) and [docs/PENDING-HANDOFF.md](PENDING-HANDOFF.md).

Out of this phase, still: CI, GrapheneOS, issue #8. The operator page and `disallowAddUser` are Phase 4.

### Phase 4 — Emulator policy on the operator page

**org-can-do.** Merged as PR #46 (squash `51c6c3b`), bench log in [docs/EMULATOR.md](EMULATOR.md). Still not Feature GO. Issue #45.

Script: [scripts/emulator-policy-restriction.sh](../scripts/emulator-policy-restriction.sh). One check-in on the AOSP ATD bench. `DISALLOW_ADD_USER` selects `policyFlags.disallowAddUser` (`true`, `false`, or absent). The desired state names no catalog APK. After check-in, [server/policy_restriction.py](../server/policy_restriction.py) reads `dumpsys device_policy` and `dumpsys user` for an applied `no_add_user`. `ui_server.py` on 127.0.0.1:8787 lists that device id. The script log order is enroll, check-in, restriction, operator list. `false` and `absent` are expected to fail at the restriction step. No wipe. The image is an AOSP ATD emulator. Attestation is not asserted.

Bench result (2026-10-09, nimo): `false` and `absent` FAIL at the restriction step, `true` PASSes with `no_add_user` applied and the device id listed on 127.0.0.1:8787. Log: [docs/EMULATOR.md](EMULATOR.md#bench-log-2026-10-09).

### Phase 5 — Run the operate script on a GitHub-hosted KVM runner

**org-can-do.** Issue #47, branch `build/p5-gha-kvm`. Not Feature GO. Handoff: [docs/ops/HANDOFF-p5-gha-kvm-2026-10-09.md](ops/HANDOFF-p5-gha-kvm-2026-10-09.md).

[.github/workflows/emulator-policy.yml](../.github/workflows/emulator-policy.yml) boots the AOSP ATD Android 15 emulator (`api-level 35`, `aosp_atd`, `x86_64`) on a free `ubuntu-latest` runner with KVM enabled by a udev rule. No self-hosted runner. [scripts/ci-emulator-policy.sh](../scripts/ci-emulator-policy.sh) runs [scripts/emulator-policy-restriction.sh](../scripts/emulator-policy-restriction.sh) as `absent` and `false` (exit 1 asserted), `true-then-false` (true applies `no_add_user`, a second check-in with `false` and no owner reset clears it; exit 0) and `true` (exit 0), then asserts the post-run state: device owner and `no_add_user` applied. Logs upload as the `emulator-policy-logs` artifact. Triggers are path-filtered `pull_request` / `push` to `main`, plus `workflow_dispatch`. The image is not GrapheneOS. Attestation is not asserted. Procedure: [docs/EMULATOR.md](EMULATOR.md#phase-5--github-hosted-kvm-runner).

`ef320ae` (`ef320ae6b973ca7bf03fbcd4dd94f2466c45669b`) is the last code SHA before Phase 6. The green emulator run on that SHA is https://github.com/themark-net/grapheneos-mdm/actions/runs/37976338590 (job `AOSP ATD emulator policy (disallowAddUser)`). Docs head `5a4e8f1` (`5a4e8f1a9f7417e208e579a079af4c893fa7ba59`) ran the same job at https://github.com/themark-net/grapheneos-mdm/actions/runs/37977122809. `pull_request` path filters match the whole PR diff, so a docs-only head still re-runs the job while the PR changes a listed path.

### Phase 6 — disallowFactoryReset on the same KVM job

**Done.** org-can-do. Issue #49, branch `build/p6-factory-reset`. Not Feature GO. Handoff: [docs/ops/HANDOFF-p6-factory-reset-2026-10-12.md](ops/HANDOFF-p6-factory-reset-2026-10-12.md).

The same workflow as Phase 5, [.github/workflows/emulator-policy.yml](../.github/workflows/emulator-policy.yml), on `ubuntu-latest` with KVM. No self-hosted runner. [scripts/ci-emulator-policy.sh](../scripts/ci-emulator-policy.sh) keeps the disallowAddUser legs, asserts device owner and `no_add_user`, then runs `RESTRICTION=disallowFactoryReset` on [scripts/emulator-policy-restriction.sh](../scripts/emulator-policy-restriction.sh). The dumpsys token is `no_factory_reset` (`UserManager.DISALLOW_FACTORY_RESET`). Absent and false FAIL at the restriction step (exit 1). `true-then-false` applies the restriction, then a second check-in with `false` and no owner reset clears it. Exit 0 only when the after-false `device_policy` dump is non-empty and contains `DevicePolicyEngine`, `UserRestrictionPolicyKey`, or a Device Owner line, and [server/policy_restriction.py](../server/policy_restriction.py) exits 1 and prints `restriction no_factory_reset is not applied`. Exit 2 (empty or unrecognised dumpsys) is a failed clear. Phase 7 replaces that marker rule on API 34 and above. `true` PASS (exit 0). The script does not factory-reset or wipe. The image is an AOSP ATD emulator. Attestation is not asserted.

`PolicyManager.userRestrictionUpdates` already maps `disallowFactoryReset` true to `addUserRestriction` and false to `clearUserRestriction`. The desired-state schema already has the flag. No app change.

The artifact excludes `fleet.sqlite*` (the WAL can hold an attestation chain) and certificate suffixes `.pem`, `.key`, `.p12`, `.crt`, `.der`, `.cer`, `.pfx`, `.jks`, `.keystore`, `.csr`, `.bks`. The clear leg requires that not-applied sentence and exit 1, not merely a non-zero exit.

`ef5b380` (`ef5b38089fcab96c616547adc18f58b879e66e62`) is the code SHA. The green emulator run on that SHA is https://github.com/themark-net/grapheneos-mdm/actions/runs/38287586817 (job `AOSP ATD emulator policy (disallowAddUser, disallowFactoryReset)`). The boot retry was skipped. The image is an AOSP ATD emulator, not GrapheneOS. Attestation was not asserted. `pull_request` path filters match the whole PR diff, so a docs-only head still re-runs the job. That later URL is not recorded in a follow-up commit.

### Phase 7 — CI hardening

**Done.** org-can-do. Issue #51. Pull request #52 merged to main at `8a7164c`. Not Feature GO. Handoff: [docs/ops/HANDOFF-p7-ci-hardening-2026-10-13.md](ops/HANDOFF-p7-ci-hardening-2026-10-13.md).

The same GitHub-hosted `ubuntu-latest` KVM job. No self-hosted runner. The operate script is [scripts/emulator-policy-restriction.sh](../scripts/emulator-policy-restriction.sh). It still covers `disallowAddUser` and `disallowFactoryReset`. On API 34 and above, a dumpsys counts only when `dumpsys device_policy` has an anchored `Local Policies:` or `Global Policies:` line and either `UserRestrictionPolicyKey` or a non-empty indented line under that header (a header alone does not count; a mid-line mention does not count; API 35 ATD dumps have no `DevicePolicyEngine` line) and `dumpsys user` has `UserInfo{` plus a restriction header (`Effective restrictions:`, `Device policy global restrictions:`, `Device policy local restrictions:`, or `Device policy restrictions:`). A capture that contains `*** SERVICE ... DUMP TIMEOUT` fails and names that marker. [server/policy_restriction.py](../server/policy_restriction.py) exits 2 for empty, unrecognised, timeout, a file it cannot read, or a missing API 34 marker, and exits 3 for an argparse usage error. Exit 2 and exit 3 are not a clear and are not "not applied".

`CLEAR_LEG_STUB` is [scripts/lib/clear-leg.sh](../scripts/lib/clear-leg.sh). The operate script sources it. Stub mode refuses to run when the caller set `SERIAL` or `ANDROID_SERIAL`, including a set-but-empty value.

The BouncyCastle keystore exclusion is the workflow line `!/tmp/mdm-ci/**/*.bks` in [.github/workflows/emulator-policy.yml](../.github/workflows/emulator-policy.yml). The cert guard lists `-name '*.bks'` in [scripts/lib/cert-guard.sh](../scripts/lib/cert-guard.sh).

JavaScript actions in `ci.yml` and `emulator-policy.yml` are pinned to Node 24 releases. `reactivecircus/android-emulator-runner` v2.38.0 was already Node 24. `PolicyRestrictionTest` compares restriction pairs as a map. The image is an AOSP ATD emulator. Attestation is not asserted.

Cursor Approval is not green. On PR #50 head `c9e646b` the check `Cursor Approval Agent: Pull Request Router and Approver` concluded `neutral` (`Approval Agent run encountered an error`, run `bc-9a8d6e3e`). The same check was `success` on `ef5b380`. Main `0c54704` has no Cursor Approval check. On `e852c6f` that check concluded `neutral`. #52 merged to main at `8a7164c`. The waiver is issue #53 and stays open. This commit does not close it.

emulator-policy ran on `e852c6f` and failed: https://github.com/themark-net/grapheneos-mdm/actions/runs/38441669873. That run is red. emulator-policy run 38446617330 (https://github.com/themark-net/grapheneos-mdm/actions/runs/38446617330) on 8744c58 is green. The image is an AOSP ATD emulator. Attestation is not asserted.

### Phase 7.1 — Hygiene

**In progress on this branch.** org-can-do. Issue #53. Not Feature GO. Decisions: [docs/ops/AUTONOMOUS-DECISIONS-2026-10-16.md](ops/AUTONOMOUS-DECISIONS-2026-10-16.md).

Six follow-ups from #52, in one pull request. The after-false `device_policy` dump must contain `UserRestrictionPolicyKey` or a non-empty indented line under an anchored `Local Policies:` or `Global Policies:` header. A header with no body is not a clear. `policy_restriction.py` exits 2 when it cannot read its input file. `CLEAR_LEG_STUB` refuses `SERIAL=` and `ANDROID_SERIAL=` when those variables are set, including set to empty. The image is an AOSP ATD emulator. Attestation is not asserted. Issue #53 stays open for the Cursor Approval waiver.

## Next slice

After this Phase 7.1 pull request lands, org-can-do work is exhausted. The next step is the founder-only Pixel/GrapheneOS stop. No remaining org-can-do slice moves the founder bar.

The founder bar is the same device-owner check-in loop on a Pixel running GrapheneOS, with `attestationStatus` `ok`. The AOSP ATD emulator does not meet that bar. Putting the Phase 3 same-database script on this runner records `chain_invalid`. That is a record, not attestation progress. Another user restriction does not move the bar. Pixel enroll, fleet CA material, the production control plane, and the license stay in [Founder-needed](#founder-needed). Do not start them from an org harness.

## Founder-needed

Not org slices. Do not start them from a cloud harness.

| Item | Why it waits |
| --- | --- |
| Pixel running GrapheneOS, ADB device owner, one real check-in | [docs/ENROLLMENT.md](ENROLLMENT.md). The founder holds the hardware. |
| Fleet CA / step-ca material in place of `gen-lab-certs.sh` | [docs/MTLS.md](MTLS.md). Keys and provisioner passwords stay out of this repo. |
| Production control plane | [DESIGN.md](../DESIGN.md) still leaves FastAPI/Go, real CA auth, and APK hosting external to the lab stub. |
| License | README: TBD (AGPL or Apache-2.0, currently all rights reserved). |
| QR download host trusted at setup | The lab CA is not in the device trust store during setup. Useful only after upstream ships a wizard that launches ManagedProvisioning. |

## Non-goals

- Reopen issue #8, or add a 6-tap scanner. That is GrapheneOS SetupWizard2 PR #40.
- Read an AOSP ATD session as GrapheneOS enrollment, verified boot, or attestation success.
- Bind `ui_server.py` off localhost, or accept phone traffic on the operator port.
- Build the production control plane inside `server/lab_checkin.py`.
- Download a GrapheneOS OTA. `minSecurityPatch` is a report. `check_os_update` opens system update settings.
- Factory-reset a physical device from an org harness.
- Edit, rebase, or merge founder draft PR #42.
