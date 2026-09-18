# Device Owner enrollment on GrapheneOS

This document is the enrollment guide for **this** agent:

- Package / applicationId: `net.themark.grapheneosmdm`
- Device admin receiver: `net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver`
- Declared in `app/src/main/AndroidManifest.xml` (`android:exported="true"`, `BIND_DEVICE_ADMIN`)

**Supported path today:** ADB `dpm set-device-owner` on a clean Pixel running GrapheneOS.
**Not supported today:** SetupWizard 6-tap QR / Managed Provisioning. Do not assume a QR code will enroll this app on stock GrapheneOS.

Read the [safety notes](#safety-notes-read-before-you-set-device-owner) before the last ADB command.

---

## 1. Supported path: clean Pixel + GrapheneOS + ADB

### 1.1 Install GrapheneOS

1. Use a supported Pixel. Follow the official installer: [https://grapheneos.org/install/](https://grapheneos.org/install/).
2. After GrapheneOS is installed, **relock the bootloader** if the official guide says to for your flow. Relocking is independent of Device Owner; it does not enroll MDM.
3. Boot GrapheneOS into the first-run SetupWizard.

### 1.2 Finish first boot *without* accounts

`dpm set-device-owner` is rejected if **any** `AccountManager` account exists on user 0.

1. Complete SetupWizard far enough to reach the home screen and Settings (USB debugging is not available from the welcome screen on stock GrapheneOS).
2. Skip adding accounts. Do not sign into sandboxed Google Play, a mail app, or any other account type.
3. You can set a PIN/password and continue through GrapheneOS-specific screens (network, location, etc.). Those are not Android accounts.
4. Do **not** restore a backup that would recreate accounts.

If `set-device-owner` later fails with a message about existing accounts, factory-reset and repeat this section. Removing accounts from Settings is not always enough.

### 1.3 Enable ADB

1. Settings → About phone → tap **Build number** seven times.
2. Settings → System → Developer options:
   - Enable **USB debugging**.
   - On GrapheneOS, also allow debugging for the connected computer when the prompt appears (and re-authorize if you change cables/ports).
3. On the host: `adb devices` should show the Pixel as `device` (not `unauthorized`).

### 1.4 Build and install this app

From a checkout of this repo:

```bash
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Use a **release** APK only when you intend production Device Owner (see [safety notes](#safety-notes-read-before-you-set-device-owner) on `testOnly`).

Confirm the package:

```bash
adb shell pm path net.themark.grapheneosmdm
```

### 1.5 Set Device Owner

The component name must match this app’s receiver (do not substitute another DPC class):

```bash
adb shell dpm set-device-owner net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
```

Success looks like: `Success: Device owner set to package net.themark.grapheneosmdm`.

Common failures:

| Symptom | Typical cause |
| --- | --- |
| Already some accounts | Finish setup with zero accounts, or factory-reset |
| Not allowed / not a device admin | Wrong component string, or APK not installed |
| Device owner is already set | Another DO/PO exists; factory-reset |
| `testOnly` / install failed | Mixing debug and release signatures; uninstall first if needed |

### 1.6 Verify

```bash
adb shell dumpsys device_policy | grep -A 20 "Device Owner"
```

You should see package `net.themark.grapheneosmdm` and admin `net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver`.

On device, open **GrapheneOS MDM**: the status line should report Device Owner. `DeviceAdminReceiver.onEnabled` schedules WorkManager check-ins (see [SCHEDULING.md](SCHEDULING.md)).

Optional: disable USB debugging after a successful, verified enrollment if the device will leave a trusted bench.

### 1.7 Removal (debug / testOnly only)

Android Gradle Plugin marks **debug** APKs `android:testOnly="true"`. For those, Device Owner can often be cleared without a wipe:

```bash
adb shell dpm remove-active-admin net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
```

This is **not** a reliable path for a release (non-`testOnly`) Device Owner. On current Android, `DevicePolicyManager.clearDeviceOwnerApp()` is deprecated and is a no-op for apps targeting API 26+. Treat production DO as **factory-reset to exit** unless you later add an explicit, tested offboarding API.

---

## 2. QR / 6-tap flow — investigation (does **not** work on stock GrapheneOS)

Stock GrapheneOS SetupWizard2 does **not** implement AOSP’s hidden 6-tap QR enrollment. Tapping the welcome screen six times will not open a provisioning scanner. That is an upstream gap, not a bug in this agent.

### Upstream status (as of 2026-08-23)

GrapheneOS maintainers have said MDM QR setup needs to live in [SetupWizard2](https://github.com/GrapheneOS/platform_packages_apps_SetupWizard2). Relevant PRs:

- [PR #40](https://github.com/GrapheneOS/platform_packages_apps_SetupWizard2/pull/40) — Headwind-origin QR provisioning, still open; GrapheneOS noted it needs major cleanup and a current-branch retarget (15-qpr2 branch deletion closed it temporarily; it was reopened against 16-qpr2 with merge conflicts remaining).
- [PR #48](https://github.com/GrapheneOS/platform_packages_apps_SetupWizard2/pull/48) — 16-qpr2 port; **closed** (not merged). Maintainers stated they will handle this task in-tree rather than accept that contribution.

Until a SetupWizard2 change **ships in a GrapheneOS release**, a custom DPC cannot make 6-tap work by changing only this app.

### Could this DPC use QR once a GrapheneOS PR lands?

**Probably yes as a Device Owner DPC, but not with the code as it exists today.**

AOSP QR provisioning (when the wizard actually launches it) typically:

1. User taps the welcome screen 6 times → scanner.
2. QR JSON names the DPC component, HTTPS APK URL, and signature checksum.
3. The wizard downloads the APK and starts `ACTION_PROVISION_MANAGED_DEVICE_FROM_TRUSTED_SOURCE`.
4. The DPC **must** handle `DevicePolicyManager.ACTION_GET_PROVISIONING_MODE` and `DevicePolicyManager.ACTION_ADMIN_POLICY_COMPLIANCE`. If those activities are missing, provisioning **fails** on modern Android.

This repo today:

- Receiver is correctly exported for `DEVICE_ADMIN_ENABLED` / `PROFILE_PROVISIONING_COMPLETE` / `DEVICE_OWNER_CHANGED`.
- `onProfileProvisioningComplete` schedules WorkManager check-ins (QR path still incomplete on stock GrapheneOS).
- There are **no** activities for `ACTION_GET_PROVISIONING_MODE` or `ACTION_ADMIN_POLICY_COMPLIANCE`.

So: after GrapheneOS ships a wizard that speaks standard Managed Provisioning, we can generate a QR that points at `net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver` — **but we still need a small DPC provisioning implementation first**. That is follow-up work, not enabled by documentation alone.

Illustrative QR JSON (do not treat as a working GrapheneOS payload today):

```json
{
  "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": "net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver",
  "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": "https://example.invalid/grapheneos-mdm.apk",
  "android.app.extra.PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM": "REPLACE_WITH_SHA256_OF_SIGNING_CERT_BYTES",
  "android.app.extra.PROVISIONING_LEAVE_ALL_SYSTEM_APPS_ENABLED": true
}
```

Checksum and extras must match AOSP’s current QR spec when we implement this. Do not print this QR expecting stock GrapheneOS to honor it.

---

## 3. Optional future path: platform-signed / system app (golden images)

For a fleet image (rebuild GrapheneOS, not sideload), this agent can be preinstalled instead of `adb install`:

1. Add `net.themark.grapheneosmdm` as a **privileged product/system app** in your GrapheneOS build (APK + `privapp-permissions` allowlist for any privileged permissions you actually need).
2. Sign that APK with the **platform key of that build** (or otherwise satisfy GrapheneOS/AOSP privileged-app policy). This is a full OS rebuild and key-management problem — this repo is not switching to platform signing.
3. First boot still must have **no accounts**. Then either:
   - run the same `dpm set-device-owner net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver`, or
   - use a build-time / first-boot mechanism if you add one later.

Privileged preinstall does **not** by itself make the app Device Owner. It only removes the sideload step and can make policy APIs more reliable. Still factory-reset to recover from a bad DO on a production image.

---

## 4. Safety notes (read before you set Device Owner)

Device Owner is a **device-wide, high-privilege** role. Once set:

- Many `UserManager.DISALLOW_*` restrictions and `DevicePolicyManager` policies persist across reboots.
- A **release** Device Owner is effectively **irreversible without a factory reset** (and a reset is blocked if you later set `DISALLOW_FACTORY_RESET`).
- This scaffold’s **Sample restrictions** button (`MainActivity` → `PolicyManager.applySampleRestrictions()`) can apply real restrictions immediately. Do not tap it on a daily-driver.
- `device_admin.xml` already declares wipe, lock, password, and camera policies. Silent install, hide/suspend, and further restrictions become available once DO is set even if the UI is still stubbed.
- GrapheneOS **duress PIN** remains an independent wipe path; it does not “undo” Device Owner, it wipes the device.
- Relocking the bootloader after GrapheneOS install does not protect you from a Device Owner you just set; conversely, unlocking later for a wipe may require your PIN and GrapheneOS’s install procedure.
- Enroll only on hardware you can afford to reset. Keep a non-DO test device until offboarding is implemented and verified.

Recommended order: enroll with a **debug** APK → confirm dumpsys and UI status → exercise policies on a spare Pixel → only then consider a release APK / golden image.
