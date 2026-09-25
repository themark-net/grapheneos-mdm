# Pending handoff

Continuation note for the next harness. Issue **#21** is merged. The open work is issue **#24**, lost-device GPS, on `feat/issue-24-location`.

Written 2026-09-25. Issues #12, #13, #14, #18, and #21 are closed.

## Open: issue #24

`policyFlags.locationEnabled` turns the location radio on and the next inventory includes a GNSS fix (`location`). The agent grants itself coarse, fine, and background location. While the radio is on it also grants GrapheneOS `android.permission.OTHER_SENSORS` when that permission exists. `usbDataSignalingEnabled`, `disallowConfigWifi`, and `disallowConfigMobileNetworks` are the USB and network controls that were missing from the client. Omit a flag to leave that setting alone.

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
| SHA | `03e0743` |
| Subject | docs: AGENTS.md Testing standing rule (Trophy / no tautology) |

## 2. What shipped

These three squash merges are the stack on that tip, oldest first.

### PR #17 — clear user restrictions — Fixes #14

Squash `aed4ece43119895c5cb91390f088aabb2b1a4b89`.

For `disallowAddUser`, `disallowFactoryReset`, and `disallowInstallUnknownSources`: `true` adds the user restriction, `false` clears it, and a null or omitted flag leaves the device setting alone.

### PR #16 — persist lab inventory and per-device desired state — Fixes #12

Squash `5e515ef603204b1e1f11cb1b8f7b41718ab29582`.

Optional `--db` sqlite on the lab check-in server stores the last inventory per device and serves a per-device desired-state override. Without `--db`, every device still receives the default desired-state file and inventory is only logged. The operator CLI is `server/fleet_store.py` (`list`, `show`, `set-desired`, `clear-desired`), already shown in [server/README.md](../server/README.md).

### PR #15 — minimum security-patch floor — Fixes #13

Squash `61685f827974275556cfa37531f5ed1e013acb19` (this tip).

Desired state may set `policyFlags.minSecurityPatch` as `YYYY-MM-DD`. The agent compares that date to `Build.VERSION.SECURITY_PATCH`, logs when the device patch is older, and reports `securityPatchOk` on the next inventory. It does not drive the GrapheneOS updater and it does not wipe the device. Schema fields live in [protocol/desired-state.schema.json](../protocol/desired-state.schema.json) and [protocol/inventory-report.schema.json](../protocol/inventory-report.schema.json).

Earlier commits still on this tip, outside this stack: WorkManager scheduling (#11, issue #5), desired-apps enforce (#10, issue #4), mTLS check-in (#9, issue #3), and the enrollment guide (#7).

## 3. Open posture

GrapheneOS MDM stays **software-only**. There is no device-demo park unless the founder says otherwise.

[#18](https://github.com/themark-net/grapheneos-mdm/issues/18) is the open PR #20 above. [#8](https://github.com/themark-net/grapheneos-mdm/issues/8) (DPC provisioning-mode activities after the GrapheneOS QR wizard ships) stays parked in [docs/ENROLLMENT.md](ENROLLMENT.md), [docs/MTLS.md](MTLS.md), and [docs/SCHEDULING.md](SCHEDULING.md).

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
