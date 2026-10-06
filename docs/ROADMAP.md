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

Out of this phase, still: operator page, policy flags, CI, GrapheneOS, issue #8.

## Next slice — Phase 4 — Emulator policy on the operator page

**org-can-do.** Assumes Phase 3 has landed, so a later log is not another `challenge_mismatch` row from a fresh sqlite.

`scripts/emulator-device-owner.sh` serves `policyFlags: {}` and a `noop` command, and it does not start `ui_server.py`. The Phase 3 script does the same. The agent already applies `policyFlags.disallowAddUser` through `UserManager.DISALLOW_ADD_USER`.

Definition of done: one script, same AOSP ATD bench, exits non-zero on a missing step. Desired state sets `disallowAddUser` true and does not name a catalog APK (the example APK is a placeholder and a hash mismatch looks like an install failure). After check-in, `dumpsys device_policy` shows that restriction. `ui_server.py` on 127.0.0.1:8787 against that sqlite lists the device id. The script log is the walkthrough record (enroll, check-in, operator list, restriction). No wipe command. No claim that the image is GrapheneOS.

## Later

### Phase 5 — Run the operate script on a KVM runner

**org-can-do**, after Phase 4's script is the thing worth gating.

`.github/workflows/ci.yml` installs platform 35 and build-tools. It does not install `emulator` or `system-images;android-35;aosp_atd;x86_64`. The bench script expects a local SDK (`ANDROID_HOME`), AVD `mdm36`, and `adb` ports 5574/5575. A CI job has to provide that image and KVM. Until a runner has both, the gate stays a documented script that fails locally, which Phase 2 already has for device-owner plus a single check-in.

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
