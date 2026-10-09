# Pending handoff

Continuation note for the next harness. Read [docs/ROADMAP.md](ROADMAP.md) for the next slice. Issue **#8** stays closed. Stock GrapheneOS SetupWizard branch 17 still has no 6-tap scanner. That gap is [SetupWizard2 PR #40](https://github.com/GrapheneOS/platform_packages_apps_SetupWizard2/pull/40).

Updated 2026-10-09 on `build/p5-gha-kvm` (Phase 5, issue #47). `main` is at `51c6c3b` (`51c6c3bd9e186a6879f9fb118e74d337ea477528`, PR #46, Phase 4). This file describes what the Phase 5 merge lands. Read `git rev-parse HEAD` on `main` for the merged tip.

## 1. Tip

| | |
| --- | --- |
| Branch before merge | `main` at `51c6c3b` (Phase 4, PR #46) |
| This change | Phase 5: the Phase 4 operate script on a GitHub-hosted KVM runner (issue #47) |
| Earlier tips | `4784a79` Phase 3 (#44), `ed62c4a` docs handoff (#43) |
| Ancestor feature | `b5fd229` (`b5fd229f86326b7c428365c8f49b6fb218a6d002`), Android emulator device-owner (#38) |

`49a16c8` is PR #34 (localhost fleet operator page). `ed62c4a` is PR #43 (this handoff's previous tip plus the Feature GO roadmap).

## 2. Shipped on this tip

### Host-only simulated check-in — issue #35, PR #37

Squash `38d12fa7aa806cba5c9b2e4e2733ae76b143f6ac`. Merged 2026-10-03.

`python3 lab_checkin.py --db fleet.sqlite --simulate` writes one inventory row and exits. No phone, no ADB, no emulator, no client certificate, and no listening port. The row is stored with `simulated=1`. `ui_server.py` on 127.0.0.1:8787 labels it simulated. Wipe copy is unchanged. The server does not seed a device at start. Mutual-TLS check-in on the listening server is unchanged.

### Android emulator device-owner — issue #36, PR #38

Squash `b5fd229f86326b7c428365c8f49b6fb218a6d002`. Merged 2026-10-03. Ancestor of the Phase 3 change. Not the tip after this merges.

The image is AOSP ATD `system-images;android-35;aosp_atd;x86_64`, fingerprint `Android/sdk_slim_x86_64/emu64x:15/AE3A.240806.019/12368160:userdebug/test-keys`, model `Android ATD built for x86_64`. It is not GrapheneOS and not a Pixel. It does not prove attestation, verified boot, or the 6-tap SetupWizard. Issue #8 stays closed.

Script: [scripts/emulator-device-owner.sh](../scripts/emulator-device-owner.sh). Procedure: [docs/EMULATOR.md](EMULATOR.md). Device owner is `net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver`. The guest reaches the lab mTLS port through `adb reverse` to `https://127.0.0.1:8443` (certificate SAN is `localhost` and `127.0.0.1` only). Debug-only `LabServerConfigReceiver` sets `serverBaseUrl`. Release builds omit it. Desired state for that run has an empty package list and no policy flags.

The operate script exited 0. The stored row was:

```
deviceId a7fdb4548155d650
clientCn lab-device-01
osVersion 15
model Android ATD built for x86_64
isDeviceOwner true
attestationStatus challenge_mismatch
verifiedBootState null
lastCheckinAt 2026-10-03T04:25:26Z
```

`challenge_mismatch` is not attestation success. The server compares a keymint chain to the challenge it stored on the previous check-in (`pending_challenge`), then issues a new nonce for the next inventory. That run used a new sqlite file. The app still held a nonce from an earlier probe, so the key did not match a challenge this database had issued. `verifiedBootState` is null. `ok` requires a chain to the vendored Google root in `server/attestation-roots.pem` and `verifiedBootState` `Verified`.

### Same-database emulator attestation — Phase 3

This branch. No new issue number. The operate script is [scripts/emulator-same-db-attestation.sh](../scripts/emulator-same-db-attestation.sh). Procedure: [docs/EMULATOR.md](EMULATOR.md).

How to run, from this repo, with the user-space SDK at `../android-sdk` (AVD `mdm36`, serial `emulator-5574`, `ANDROID_ADB_SERVER_PORT=5038`):

```bash
GRADLE_BIN=/path/to/gradle-8.9/bin/gradle scripts/emulator-same-db-attestation.sh
```

`OUT` defaults to `/tmp/mdm-phase3-attestation`. The script writes a new `fleet.sqlite` there. It removes the test-only device owner when one is set, `pm clear`s `net.themark.grapheneosmdm`, and exits if the challenge prefs or keystore alias `grapheneos_mdm_attest` remain. It pushes mTLS material, sets device owner again, `adb reverse`s `tcp:8443`, and broadcasts `LabServerConfigReceiver` twice. The receiver runs one check-in per broadcast (`allowFollowUpCheckIn=false`). Desired state is an empty package list, empty `policyFlags`, and a `noop` command.

The second `check-in deviceId=` line is the record. Exit is non-zero when that observation is missing or when `attestationStatus` is `challenge_mismatch`, `none`, `missing`, `parse_error`, or `unsupported`. The success line quotes the status and `verifiedBootState`. It says verified boot passed only when the status is `ok`.

On this `userdebug` / `test-keys` image the chain check runs before the boot check. `boot_unverified` would mean the chain passed and boot was not `Verified`. Null `verifiedBootState` can still appear. The image is not GrapheneOS. This phase is not Feature GO. A Pixel enroll stays founder-only.

Bench result, 2026-10-06, script exit 0. Fingerprint `Android/sdk_slim_x86_64/emu64x:15/AE3A.240806.019/12368160:userdebug/test-keys`. First lab line `attestation=none`. Second observation:

```
deviceId a7fdb4548155d650
clientCn lab-device-01
osVersion 15
attestationStatus chain_invalid
verifiedBootState null
lastCheckinAt 2026-10-06T17:40:49Z
```

The success line was `PASS: second check-in attestationStatus=chain_invalid verifiedBootState=null`. Verified boot was not passed. `chain_invalid` is not `ok`.

### Emulator policy on the operator page — Phase 4

Issue #45. Branch `build/p4-disallow-add-user`. Script: [scripts/emulator-policy-disallow-add-user.sh](../scripts/emulator-policy-disallow-add-user.sh). Procedure: [docs/EMULATOR.md](EMULATOR.md). Handoff: [docs/ops/HANDOFF-p4-disallow-add-user-2026-10-09.md](ops/HANDOFF-p4-disallow-add-user-2026-10-09.md).

One check-in. `DISALLOW_ADD_USER=true` (the default) sets `policyFlags.disallowAddUser`. The script then requires applied `no_add_user` and the device id on `ui_server.py` at 127.0.0.1:8787. `false` and `absent` are expected to fail at the restriction step. Bench 2026-10-09 on nimo: `absent` and `false` exited 1 with `FAIL: restriction no_add_user not applied`; `true` exited 0, `dumpsys user` showed `no_add_user` under `Effective restrictions:` and `dumpsys device_policy` showed `UserRestrictionPolicyKey userRestriction_no_add_user` resolved `true`, and `GET /api/devices` on 127.0.0.1:8787 listed `deviceId a7fdb4548155d650`. Full log in [docs/EMULATOR.md](EMULATOR.md#bench-log-2026-10-09). The row shows `attestationStatus none` (one check-in, new sqlite). This phase does not assert attestation. The image is an AOSP ATD emulator. Merged as PR #46 (squash `51c6c3b`).

### Operate script on a GitHub-hosted KVM runner — Phase 5

Issue #47. Branch `build/p5-gha-kvm`, based on `main` at `51c6c3b` (PR #46 merged). Handoff: [docs/ops/HANDOFF-p5-gha-kvm-2026-10-09.md](ops/HANDOFF-p5-gha-kvm-2026-10-09.md).

[.github/workflows/emulator-policy.yml](../.github/workflows/emulator-policy.yml) runs on `ubuntu-latest` (no self-hosted runner). It enables `/dev/kvm` with a udev rule, installs JDK 17, Gradle 8.9 and Python 3.12 with setup actions, and boots `system-images;android-35;aosp_atd;x86_64` with `reactivecircus/android-emulator-runner` v2.38.0 (pinned by SHA). [scripts/ci-emulator-policy.sh](../scripts/ci-emulator-policy.sh) runs the operate script four times and asserts each exit code: `absent` 1, `false` 1, `true-then-false` 0, `true` 0. It then asserts the post-run state: this app is device owner and `no_add_user` is applied. Triggers are `pull_request` and `push` to `main` filtered to the script, `server/**`, `app/**`, `protocol/**`, Gradle files and the workflow, plus `workflow_dispatch`. No cron. The image is an AOSP ATD emulator, not GrapheneOS. Attestation is not asserted.

`ef320ae` (`ef320ae6b973ca7bf03fbcd4dd94f2466c45669b`) is the last code SHA. Green emulator run on that SHA: https://github.com/themark-net/grapheneos-mdm/actions/runs/37976338590. Docs head `5a4e8f1` (`5a4e8f1a9f7417e208e579a079af4c893fa7ba59`) also ran it: https://github.com/themark-net/grapheneos-mdm/actions/runs/37977122809. `pull_request` path filters match the whole PR diff, so a docs-only head still re-runs the job while the PR changes a listed path.

### Earlier squash merges

One line each. Longer notes for these are in the commit subjects and the docs linked in section 5.

| Squash | PR | What |
| --- | --- | --- |
| `49a16c82964e4f35fdffd5c3cb7545728cdaa5cd` | #34 | Localhost operator page on 127.0.0.1:8787. Wipe is type-to-confirm. Empty DB stays empty. |
| `47523f98e81265603b095832891a7102262d128c` | #33 | `ansible/group_vars/<group>.json` applied with `ansible_sync.py`. Fixes #32. |
| `dbaa2d05e1b89db5a11679678e11d4da6cde4ff0` | #31 | Provisioning QR payload and `serverBaseUrl` from the QR. Fixes #30. |
| `5dc98c188cc9f06d5f828e497cb1b0dc72a6202d` | #29 | Fleet groups and key-attestation check. Fixes #28. |
| `cb09cfb9fdb8604772bbae19abd836a5c569a04c` | #27 | Attestation, preferred activities, profiles, updater check, QR handlers. Fixes #26. |
| `fba9f9f87089e0ede86b48390cb97910cf6c55d2` | #25 | GPS fix for lost-device recovery. Fixes #24. |
| `b0b79aeb1cabc1a41ebb53bcc41709a088688f03` | #22 | Runtime permission grants. Fixes #21. |
| `00283d27b036a5c531f00063225948e6364ad0aa` | #20 | Password rule, hide/suspend, uninstall of packages this agent installed. Fixes #18. |
| `aed4ece43119895c5cb91390f088aabb2b1a4b89` | #17 | `false` clears `disallowAddUser`, `disallowFactoryReset`, `disallowInstallUnknownSources`. Fixes #14. |
| `5e515ef603204b1e1f11cb1b8f7b41718ab29582` | #16 | Lab sqlite inventory and per-device desired state. Fixes #12. |
| `61685f827974275556cfa37531f5ed1e013acb19` | #15 | `minSecurityPatch` report. The agent does not drive the updater or wipe. Fixes #13. |
| `5ff09571dbf5127c0b5df04f0d5216d24a8025c0` | #11 | WorkManager check-in. Fixes #5. |
| `bf42e41a624b4971521c80e451a74acae40a4eb1` | #10 | Catalog install and desired-apps enforce. Fixes #4. |
| `c3641a7b5e42e7930b70132aed94e442cc3e0fd5` | #9 | mTLS `ApiClient` and lab check-in. Fixes #3. |
| `e78c0aa357acf8f9e3df062502ea0b4d73cd46cc` | #7 | Enrollment guide. |

## 3. Open posture

Feature GO, set by the founder on 2026-10-02. New slices are allowed. A device-demo path is allowed when the org can run it without the founder.

Host-only work and the AOSP emulator bench are org-can-do. A physical Pixel and real GrapheneOS enrollment stay founder-only. He holds the hardware.

Issue #8 stays closed. The wizard gap is upstream SetupWizard2 PR #40, unchanged. Enrollment until that lands is ADB `dpm set-device-owner`, documented in [docs/ENROLLMENT.md](ENROLLMENT.md).

Founder draft PR **#42** (`founder-build-babysit/2026-10-05`) is not the next slice. Leave it untouched.

Phase 5 (issue #47) runs the Phase 4 operate script on a GitHub-hosted KVM runner; see the Phase 5 section above. Phase 4 and Phase 5 are not Feature GO. The next slice after Phase 5 is in [docs/ROADMAP.md](ROADMAP.md).

## 4. Boundaries

These are the standing limits. Feature work and emulator demos are not frozen.

- Physical Pixel, real GrapheneOS, fleet CA credentials, license, and a production control plane are founder-needed.
- Issue #8 stays closed. Do not reopen it and do not implement the 6-tap scanner in this repo.
- Draft PR #42 stays as the founder left it.
- The operator page stays on localhost. The lab server stays the mTLS check-in path.
- An AOSP ATD result is not a GrapheneOS enroll and is not attestation success.

## 5. Docs that still apply

- [docs/ROADMAP.md](ROADMAP.md) — phases, the next slice, and its definition of done.
- [docs/ENROLLMENT.md](ENROLLMENT.md) — ADB Device Owner on a clean Pixel. QR needs a wizard that launches ManagedProvisioning.
- [docs/EMULATOR.md](EMULATOR.md) — AOSP ATD device-owner bench (#36 / #38), Phase 3 same-database attestation, and Phase 4 disallowAddUser (issue #45).
- [docs/ops/HANDOFF-p4-disallow-add-user-2026-10-09.md](ops/HANDOFF-p4-disallow-add-user-2026-10-09.md) — Phase 4 handoff.
- [docs/ops/HANDOFF-p5-gha-kvm-2026-10-09.md](ops/HANDOFF-p5-gha-kvm-2026-10-09.md) — Phase 5 handoff (GitHub-hosted KVM runner).
- [docs/MTLS.md](MTLS.md) — mTLS check-in, lab `--db`, fleet CA alignment.
- [docs/SCHEDULING.md](SCHEDULING.md) — WorkManager periodic check-in and `checkin_now`.
- [docs/design/](design/) — operator journey, wireframes, wipe gate.
- [DESIGN.md](../DESIGN.md) — architecture. Production control plane is still external.
- [server/README.md](../server/README.md) — lab check-in, `fleet_store.py`, operator page, `--simulate`.
- [protocol/](../protocol/) — desired-state and inventory schemas.

## 6. Dogfood

Use the procedures in those docs.

- Host lab loop: [server/README.md](../server/README.md).
- Simulated row (shipped #35/#37): `python3 lab_checkin.py --db fleet.sqlite --simulate`, then `ui_server.py` on 127.0.0.1:8787.
- Emulator device owner (#36/#38): [scripts/emulator-device-owner.sh](../scripts/emulator-device-owner.sh). One check-in. Read `challenge_mismatch` on that script as the Phase 2 caveat, not as a pass on attestation.
- Same-database attestation (Phase 3): [scripts/emulator-same-db-attestation.sh](../scripts/emulator-same-db-attestation.sh). Two check-ins, one new sqlite. Quote the second `attestationStatus`. `chain_invalid` on userdebug/test-keys is the expected record, not `ok`.
- disallowAddUser on the operator page (Phase 4, issue #45): [scripts/emulator-policy-disallow-add-user.sh](../scripts/emulator-policy-disallow-add-user.sh). One check-in. `DISALLOW_ADD_USER=false` and `absent` are expected to fail. Do not read the run as attestation success.
- Phase 5 on GitHub Actions (issue #47): [.github/workflows/emulator-policy.yml](../.github/workflows/emulator-policy.yml) runs [scripts/ci-emulator-policy.sh](../scripts/ci-emulator-policy.sh) on an AOSP ATD emulator. `workflow_dispatch` runs it by hand. Logs are the `emulator-policy-logs` artifact.
- Pixel enrollment, when the founder is at the hardware: [docs/ENROLLMENT.md](ENROLLMENT.md).
