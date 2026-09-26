# Pending handoff

Continuation note for the next harness. Issue **#28** is merged. Issue **#8** stays open because stock GrapheneOS still has no 6-tap wizard. There is no open client or server feature work on this tip beyond that park.

Written 2026-09-25. Issues #12, #13, #14, #18, #21, #24, #26, and #28 are closed.

## Shipped: issue #28 — PR #29

Squash `5dc98c188cc9f06d5f828e497cb1b0dc72a6202d` (was head `b333ff6`).

With `--db`, desired state for a device is its own override, else its group's desired state, else the `--desired` file.

`fleet_store.py` adds `set-group`, `clear-group`, `set-group-desired`, `clear-group-desired`, and `list-groups`. `list` and `show` include the group and the attestation status.

Each check-in response still carries `attestationChallenge`, and that nonce is stored for the device. On the next inventory:

- `format=none` and no prior challenge is `none`.
- `format=none` after a challenge was issued is `missing`.
- `keymint` must carry that challenge in the attestation extension and chain to a vendored Google attestation root. Expiry is not checked, because factory attestation keys that chain to that root stay trusted after `notAfter`.
- Status `ok` also requires `verifiedBootState` `Verified`. Other boot states are `boot_unverified`. A bad challenge is `challenge_mismatch`. A chain that does not sign to the Google root is `chain_invalid`.

The check-in still returns desired state when attestation fails. The result is on the device row. This PR does not change the agent.

## Shipped: issue #26 — PR #27

Squash `cb09cfb9fdb8604772bbae19abd836a5c569a04c` (was head `2212c55`).

Does not close #8. The provisioning activities are in place; stock GrapheneOS SetupWizard still has no 6-tap scanner.

- **Attestation.** Lab check-in may return `attestationChallenge` (32 random bytes, base64). The next inventory uses an Android Keystore key bound to that nonce: `attestation.format=keymint`, `payloadB64` is the concatenated DER chain (leaf first), and `verifiedBootState` is `Verified`, `SelfSigned`, `Unverified`, or `Failed` when the attestation extension contains root-of-trust. No challenge keeps `format=none`.
- **Preferred activities.** `persistentPreferredActivities` is the full set this agent manages. Omit leaves them alone. Empty clears only packages this agent previously set.
- **Profiles.** Inventory `users` lists the calling user serial and `getSecondaryUsers` serials. `disallowUserSwitch` uses the same true/false/omit rule as the other restrictions. This does not create or delete users. Silent install stays on the system user.
- **Updater.** Inventory `osUpdater` reports `app.seamlessupdate.client`. Command `check_os_update` unhides that package and starts `android.settings.SYSTEM_UPDATE_SETTINGS`. The updater service is not exported, and its settings activity requires a signature permission, so this agent does not download the OTA itself.
- **QR handlers.** `GET_PROVISIONING_MODE` returns fully-managed when that mode is allowed, and cancels when the wizard offers only a work profile. `ADMIN_POLICY_COMPLIANCE` returns OK.

## Shipped: issue #24 — PR #25

Squash `fba9f9f87089e0ede86b48390cb97910cf6c55d2` (was head `7b71755`).

`policyFlags.locationEnabled` turns the location radio on and the next inventory includes a location fix. The agent grants itself coarse, fine, and background location. While the radio is on it also grants GrapheneOS `android.permission.OTHER_SENSORS` when that permission exists. A fresh GNSS fix beats a fresh network fix; a fresh network fix beats a stale GNSS pin; otherwise wait up to 8s for one GPS update, then newest cached. `false` turns the radio off and stops reporting. Omit leaves the radio alone. `usbDataSignalingEnabled`, `disallowConfigWifi`, and `disallowConfigMobileNetworks` use the same add/clear/omit rule as other flags.

## Shipped: issue #21

`policyFlags.permissionGrants` is the full set of runtime permission overrides for other apps (`granted` / `denied` / `default`). Omit the list to leave grants alone. An entry that drops off is reset to `default`. A reset that fails stays recorded so the next check-in retries it. The agent package is ignored.

## Shipped: PR #20 — Fixes #18

Password complexity, lock timeout, suspend/hide, and uninstall of packages this agent installed.

- `setRequiredPasswordComplexity(complexity)` is the API 31 method. It takes the complexity int only. `setMaximumTimeToLock(admin, lockMs)` still takes the admin component.
- A package that fails to unsuspend or unhide stays in the persisted set so the next check-in retries it.
- The agent package is never suspended, hidden, or uninstalled. Uninstall runs only for packages this agent installed, after the PackageInstaller result.

Omit `passwordComplexity`, `maximumTimeToLockMs`, `suspendedPackages`, or `hiddenPackages` to leave that device setting alone. `passwordComplexity` is `none` / `low` / `medium` / `high`. `none` clears the requirement. `maximumTimeToLockMs` of `0` clears the timeout.

## 1. Tip

| | |
| --- | --- |
| Branch | `main` |
| SHA | `5dc98c1` |
| Subject | Fleet groups and key-attestation check (#29) |

## 2. What shipped

Recent squash merges on this tip, oldest first in the earlier stack, then #21/#24/#26/#28.

### PR #17 — clear user restrictions — Fixes #14

Squash `aed4ece43119895c5cb91390f088aabb2b1a4b89`.

For `disallowAddUser`, `disallowFactoryReset`, and `disallowInstallUnknownSources`: `true` adds the user restriction, `false` clears it, and a null or omitted flag leaves the device setting alone.

### PR #16 — persist lab inventory and per-device desired state — Fixes #12

Squash `5e515ef603204b1e1f11cb1b8f7b41718ab29582`.

Optional `--db` sqlite on the lab check-in server stores the last inventory per device and serves a per-device desired-state override. Without `--db`, every device still receives the default desired-state file and inventory is only logged. The operator CLI is `server/fleet_store.py` (`list`, `show`, `set-desired`, `clear-desired`), already shown in [server/README.md](../server/README.md).

### PR #15 — minimum security-patch floor — Fixes #13

Squash `61685f827974275556cfa37531f5ed1e013acb19`.

Desired state may set `policyFlags.minSecurityPatch` as `YYYY-MM-DD`. The agent compares that date to `Build.VERSION.SECURITY_PATCH`, logs when the device patch is older, and reports `securityPatchOk` on the next inventory. It does not drive the GrapheneOS updater and it does not wipe the device. Schema fields live in [protocol/desired-state.schema.json](../protocol/desired-state.schema.json) and [protocol/inventory-report.schema.json](../protocol/inventory-report.schema.json).

### PR #22 — permission grants — Fixes #21

Squash `b0b79aeb1cabc1a41ebb53bcc41709a088688f03`.

### PR #25 — lost-device GPS — Fixes #24

Squash `fba9f9f87089e0ede86b48390cb97910cf6c55d2`.

### PR #27 — attestation / preferred activities / profiles / updater / QR — Fixes #26

Squash `cb09cfb9fdb8604772bbae19abd836a5c569a04c`.

### PR #29 — fleet groups + key-attestation check — Fixes #28

Squash `5dc98c188cc9f06d5f828e497cb1b0dc72a6202d`.

Earlier commits still on this tip, outside this stack: WorkManager scheduling (#11, issue #5), desired-apps enforce (#10, issue #4), mTLS check-in (#9, issue #3), and the enrollment guide (#7).

## 3. Open posture

GrapheneOS MDM stays **software-only**. There is no device-demo park unless the founder says otherwise.

[#8](https://github.com/themark-net/grapheneos-mdm/issues/8) (DPC provisioning-mode activities after the GrapheneOS QR wizard ships) stays parked in [docs/ENROLLMENT.md](ENROLLMENT.md), [docs/MTLS.md](MTLS.md), and [docs/SCHEDULING.md](SCHEDULING.md).

## 4. Freezes

- Device demo work is frozen.
- A new feature release stays frozen until the founder asks for one.

## 5. Docs that still apply

- [docs/ENROLLMENT.md](ENROLLMENT.md) — ADB Device Owner enrollment on a clean Pixel, including safety notes. QR / Managed Provisioning is not a supported path.
- [docs/MTLS.md](MTLS.md) — mTLS check-in, lab `--db`, and fleet CA alignment.
- [docs/SCHEDULING.md](SCHEDULING.md) — WorkManager periodic check-in and the force / `checkin_now` path.
- [DESIGN.md](../DESIGN.md) — architecture. Lab `--db` and `minSecurityPatch` reporting are already noted there.
- [server/README.md](../server/README.md) — lab check-in quick start and `fleet_store.py`.
- [protocol/](../protocol/) — desired-state and inventory JSON schemas.

## 6. Dogfood

Use the procedures already written in those docs. This note does not add device steps.

- Host lab loop: [server/README.md](../server/README.md) (`gen-lab-certs.sh`, `lab_checkin.py --db`, `fleet_store.py`, curl smoke against `/v1/checkin`).
- Agent certificates and server base URL: [docs/MTLS.md](MTLS.md).
- Enrollment on a device that is already in an approved lab: [docs/ENROLLMENT.md](ENROLLMENT.md) only.
