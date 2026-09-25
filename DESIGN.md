# Design Document - GrapheneOS MDM

## 1. Why a custom agent?

Existing options:

- **GemiGuard / ShieldMDM**: Commercial, GrapheneOS-aware, Device Owner based. Good but closed and paid.
- **Headwind MDM**: Open-source core, works as Device Owner, but community edition has feature limits and the agent is a full launcher. We want a lighter, Ansible-native feel.
- **myMDM / AFM / Android Management API**: Depend on Google services -> incompatible with GrapheneOS.

We need full control, mutual TLS with our existing CA, and the ability to treat phones more like managed Linux hosts.

## 2. Core Capabilities (Device Owner)

Device Owner (via `DevicePolicyManager`) gives us:

- Silent install / update / uninstall of APKs (`PackageInstaller` sessions)
- User restrictions (`UserManager.DISALLOW_*`)
- Force lock, wipe, reboot
- Password / lock-screen policies
- Camera / sensor / USB / network controls (to varying degrees)
- Hide / suspend apps
- Grant runtime permissions to other apps
- Set preferred activities / lock-task (kiosk) packages

GrapheneOS preserves the AOSP Device Owner framework. Sandboxed Google Play does **not** grant enterprise privileges.

## 3. Enrollment Paths

Operator-facing steps, QR investigation, golden-image notes, and safety: **[docs/ENROLLMENT.md](docs/ENROLLMENT.md)**.

### Current (supported)

1. Factory reset GrapheneOS on a Pixel (no accounts).
2. Skip all accounts / setup where possible; enable developer options + USB debugging.
3. `adb install` + `adb shell dpm set-device-owner net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver`

### Desired (future - not available on stock GrapheneOS today)

- QR-code provisioning during SetupWizard. GrapheneOS SetupWizard2 still lacks a shipped 6-tap / Managed Provisioning path. Upstream work lives in [SetupWizard2 PR #40](https://github.com/GrapheneOS/platform_packages_apps_SetupWizard2/pull/40) (open, needs cleanup / current-branch work) and [PR #48](https://github.com/GrapheneOS/platform_packages_apps_SetupWizard2/pull/48) (closed, not merged). When a release actually lands, this DPC will still need `ACTION_GET_PROVISIONING_MODE` and `ACTION_ADMIN_POLICY_COMPLIANCE` handlers before a custom QR can succeed.
- Platform-signed / privileged preinstall for golden images (OS rebuild; does not by itself set Device Owner). See [docs/ENROLLMENT.md](docs/ENROLLMENT.md).

## 4. Agent Components

| Component | Responsibility |
|-----------|----------------|
| `DeviceAdminReceiver` | Receives system callbacks (enabled, disabled, password changed, etc.) |
| `CheckInScheduler` / `CheckInWorker` | WorkManager periodic + expedited check-in (issue #5) |
| `MdmService` | Optional one-shot foreground escape hatch (no sticky loop) |
| `PolicyManager` | Translates server policy JSON -> `DevicePolicyManager` / `UserManager` calls |
| `AppManager` | Download (or receive) APKs, create `PackageInstaller` sessions, commit silently |
| `ApiClient` | mTLS HTTPS client to server; inventory report + command poll |
| `MainActivity` | Status UI, manual trigger, "is Device Owner?" indicator |

## 5. Server Side

**Lab (in-repo):** [`server/lab_checkin.py`](server/lab_checkin.py) - thin mTLS
`POST /v1/checkin` stub that returns desired-state JSON for spare-device loops.
Optional `--db` sqlite keeps the last inventory per device and a per-device
desired-state override (otherwise every device gets the default file).
See [docs/MTLS.md](docs/MTLS.md).

**Production (still external):** a FastAPI / Go control plane that:

- Authenticates devices via client certificates issued by the existing CA / step-ca
- Stores desired state (apps + versions + policies) per device or group
- Serves signed APKs or redirects to a private F-Droid / Accrescent-style repo
- Accepts inventory reports

Later: Ansible modules or a Terraform-like provider that talks to the same API.

## 6. Security Notes

- Agent should only accept commands over mutual TLS.
- Prefer short-lived tokens or certificate-bound sessions.
- Wipe / lock commands must be authenticated strongly.
- GrapheneOS duress PIN remains independent and can still wipe the device.
- Never store long-lived private keys in plaintext on the device beyond what the Keystore provides.
- Setting Device Owner is high-impact; see [docs/ENROLLMENT.md](docs/ENROLLMENT.md#safety-notes-read-before-you-set-device-owner).

## 7. Open Questions / TODOs

- Exact policy schema (YAML/JSON) that maps cleanly to Ansible inventory / group_vars.
- How to handle GrapheneOS multi-user / profiles.
- Whether to implement a minimal launcher or stay invisible.
- OTA / OS update enforcement (GrapheneOS has its own updater; we can at least report version and block if too old).
- Battery / network efficiency: addressed by WorkManager constraints (see docs/SCHEDULING.md).
- After SetupWizard2 QR lands: add provisioning-mode / policy-compliance activities for this DPC.
