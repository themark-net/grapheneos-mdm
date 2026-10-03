# Device Owner enrollment on GrapheneOS

This document is the enrollment guide for **this** agent:

- Package / applicationId: `net.themark.grapheneosmdm`
- Device admin receiver: `net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver`
- Declared in `app/src/main/AndroidManifest.xml` (`android:exported="true"`, `BIND_DEVICE_ADMIN`)

**Supported path today:** ADB `dpm set-device-owner` on a clean Pixel running GrapheneOS.
**Android emulator (not GrapheneOS):** [EMULATOR.md](EMULATOR.md) is a separate bench. The image is AOSP ATD (Android 15), not a GrapheneOS build. It does not prove attestation, verified boot, or the 6-tap SetupWizard. Issue #8 stays closed.
**QR payload:** [section 2](#2-qr-provisioning) builds a standards provisioning QR and the agent applies `serverBaseUrl` from it. Stock GrapheneOS SetupWizard still does not open a scanner.

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

## 2. QR provisioning

The agent side is ready. Stock GrapheneOS is not.

Checked 2026-09-27 against [SetupWizard2 branch 17](https://github.com/GrapheneOS/platform_packages_apps_SetupWizard2/tree/17) (same commit as `16-qpr2`). `WelcomeActivity` has no tap counter and no call into ManagedProvisioning. Six taps on the welcome screen do nothing. [SetupWizard2 PR #40](https://github.com/GrapheneOS/platform_packages_apps_SetupWizard2/pull/40) is still open. This app cannot add that scanner.

When a wizard does launch ManagedProvisioning, this DPC:

- answers `GET_PROVISIONING_MODE` with fully managed device
- answers `ADMIN_POLICY_COMPLIANCE` with success
- reads `serverBaseUrl` from `PROVISIONING_ADMIN_EXTRAS_BUNDLE` and saves it as the check-in base URL

### 2.1 Build the QR

The download URL must be **https** and signed by a CA the phone already trusts during setup. The lab CA from `gen-lab-certs.sh` is not in that trust store, so a self-signed `--publish-port` URL will fail in the wizard. Put the APK behind a certificate the device trusts (a public host, or a tunnel in front of the publish port), and point `--server-url` at the mTLS check-in origin the agent should call after it is device owner.

```bash
./gradlew :app:assembleDebug
python3 server/provisioning_qr.py \
  --apk app/build/outputs/apk/debug/app-debug.apk \
  --apk-url https://YOUR_HOST/dpc.apk \
  --server-url https://YOUR_CHECKIN_HOST:8443 \
  --wifi-ssid YOUR_SSID --wifi-password YOUR_PASSWORD \
  --out provisioning.json --png provisioning.png
```

`--png` needs `qrencode`. Without it, the JSON is still written. Display `provisioning.png` on another screen.

Optional lab download port, still using the lab certificate (wizard will reject it unless something else terminates TLS):

```bash
python3 server/lab_checkin.py --certs server/lab-certs --publish-apk app/build/outputs/apk/debug/app-debug.apk --publish-port 8444
```

That serves `https://HOST:8444/dpc.apk` with no client certificate. Check-in on 8443 stays mTLS.

### 2.2 What you can test on a stock GrapheneOS phone today

Factory-reset, finish SetupWizard with **no accounts**, then use section 1 (`adb install` and `dpm set-device-owner`). Set the server URL in the app or in `SecureConfigStore` the same way a QR extra would. Do not factory-reset expecting six taps to open a camera.

On a phone whose setup wizard does scan provisioning QR codes (stock Pixel OS, or a GrapheneOS build with PR #40), scan `provisioning.png` from the welcome screen before any account exists. The wizard downloads the APK, checks the signature checksum, and this agent becomes device owner with `serverBaseUrl` already set.

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
