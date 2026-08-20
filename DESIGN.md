# Design Document — GrapheneOS MDM

## 1. Why a custom agent?

Existing options:

- **GemiGuard / ShieldMDM**: Commercial, GrapheneOS-aware, Device Owner based. Good but closed and paid.
- **Headwind MDM**: Open-source core, works as Device Owner, but community edition has feature limits and the agent is a full launcher. We want a lighter, Ansible-native feel.
- **myMDM / AFM / Android Management API**: Depend on Google services → incompatible with GrapheneOS.

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

### Current (supported)

1. Factory reset GrapheneOS
2. Skip all accounts / setup where possible
3. Enable developer options + USB debugging
4. `adb install` + `adb shell dpm set-device-owner ...`

### Desired (future)

- QR-code provisioning during SetupWizard (GrapheneOS has an open PR for Managed Provisioning support: https://github.com/GrapheneOS/platform_packages_apps_SetupWizard2/pull/40 and follow-ups). When upstream lands, we can generate QR codes pointing at our agent APK + extras.
- Platform-signed / system-app preinstall for golden images (more involved).

## 4. Agent Components

| Component | Responsibility |
|-----------|----------------|
| `DeviceAdminReceiver` | Receives system callbacks (enabled, disabled, password changed, etc.) |
| `MdmService` | Foreground or WorkManager periodic check-in, command execution |
| `PolicyManager` | Translates server policy JSON → `DevicePolicyManager` / `UserManager` calls |
| `AppManager` | Download (or receive) APKs, create `PackageInstaller` sessions, commit silently |
| `ApiClient` | mTLS HTTPS client to server; inventory report + command poll |
| `MainActivity` | Status UI, manual trigger, “is Device Owner?” indicator |

## 5. Server Side (out of scope for this repo initially)

A simple FastAPI / Go service that:

- Authenticates devices via client certificates issued by the existing CA
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

## 7. Open Questions / TODOs

- Exact policy schema (YAML/JSON) that maps cleanly to Ansible inventory / group_vars.
- How to handle GrapheneOS multi-user / profiles.
- Whether to implement a minimal launcher or stay invisible.
- OTA / OS update enforcement (GrapheneOS has its own updater; we can at least report version and block if too old).
- Battery / network efficiency of the check-in loop.
