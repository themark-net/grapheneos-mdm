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

Script: [scripts/emulator-policy-disallow-add-user.sh](../scripts/emulator-policy-disallow-add-user.sh). One check-in on the AOSP ATD bench. `DISALLOW_ADD_USER` selects `policyFlags.disallowAddUser` (`true`, `false`, or absent). The desired state names no catalog APK. After check-in, [server/policy_restriction.py](../server/policy_restriction.py) reads `dumpsys device_policy` and `dumpsys user` for an applied `no_add_user`. `ui_server.py` on 127.0.0.1:8787 lists that device id. The script log order is enroll, check-in, restriction, operator list. `false` and `absent` are expected to fail at the restriction step. No wipe. The image is an AOSP ATD emulator. Attestation is not asserted.

Bench result (2026-10-09, nimo): `false` and `absent` FAIL at the restriction step, `true` PASSes with `no_add_user` applied and the device id listed on 127.0.0.1:8787. Log: [docs/EMULATOR.md](EMULATOR.md#bench-log-2026-10-09).

### Phase 5 — Run the operate script on a GitHub-hosted KVM runner

**org-can-do.** Issue #47, branch `build/p5-gha-kvm`. Not Feature GO. Handoff: [docs/ops/HANDOFF-p5-gha-kvm-2026-10-09.md](ops/HANDOFF-p5-gha-kvm-2026-10-09.md).

[.github/workflows/emulator-policy.yml](../.github/workflows/emulator-policy.yml) boots the AOSP ATD Android 15 emulator (`api-level 35`, `aosp_atd`, `x86_64`) on a free `ubuntu-latest` runner with KVM enabled by a udev rule. No self-hosted runner. [scripts/ci-emulator-policy.sh](../scripts/ci-emulator-policy.sh) runs [scripts/emulator-policy-disallow-add-user.sh](../scripts/emulator-policy-disallow-add-user.sh) as `absent` and `false` (exit 1 asserted), `true-then-false` (true applies `no_add_user`, a second check-in with `false` and no owner reset clears it; exit 0) and `true` (exit 0), then asserts the post-run state: device owner and `no_add_user` applied. Logs upload as the `emulator-policy-logs` artifact. Triggers are path-filtered `pull_request` / `push` to `main`, plus `workflow_dispatch`. The image is not GrapheneOS. Attestation is not asserted. Procedure: [docs/EMULATOR.md](EMULATOR.md#phase-5--github-hosted-kvm-runner).

`ef320ae` (`ef320ae6b973ca7bf03fbcd4dd94f2466c45669b`) is the last code SHA. The green emulator run on that SHA is https://github.com/themark-net/grapheneos-mdm/actions/runs/37976338590 (job `AOSP ATD emulator policy (disallowAddUser)`). Docs head `5a4e8f1` (`5a4e8f1a9f7417e208e579a079af4c893fa7ba59`) ran the same job at https://github.com/themark-net/grapheneos-mdm/actions/runs/37977122809. `pull_request` path filters match the whole PR diff, so a docs-only head still re-runs the job while the PR changes a listed path.

## Next slice

Not chosen yet. Candidates that stay org-can-do: gate one more `policyFlags` restriction in the same CI job, or put the Phase 3 same-database script on the same runner (it records `chain_invalid`; that is a record, not attestation success). Pick one with the founder before starting.

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
