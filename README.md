# grapheneos-mdm

Custom **Device Owner** MDM agent for managing a fleet of GrapheneOS devices.

Built with Kotlin. Uses the native AOSP `DevicePolicyManager` API.
No Google Play Services, no Android Enterprise / AMAPI dependency.
Designed to integrate with an existing certificate authority and Ansible-style workflows.

## Goals

- Ensure a desired set of applications is installed (and kept updated) across the fleet
- Enforce policies / configurations
- Remote lock, wipe, reboot
- Device inventory and status reporting
- Secure communication using mutual TLS (your CA)
- Work fully offline / air-gapped capable (local server)

## Current Status (2026-08-19)

This is an early scaffold. The agent can be built and set as Device Owner via ADB.
Core policy and silent app install paths are stubbed and ready for expansion.

**Enrollment today**: ADB `dpm set-device-owner` (QR / zero-touch not yet reliable on stock GrapheneOS SetupWizard).

Step-by-step (clean Pixel, ADB, QR investigation, golden-image notes, and safety): **[docs/ENROLLMENT.md](docs/ENROLLMENT.md)**.

See [DESIGN.md](DESIGN.md) for architecture and open design decisions.
See Issues for tracked work and known limitations.

## Building

Requirements:
- Android Studio (Ladybug / 2024.2+ recommended) or command-line SDK
- JDK 17+
- Target: GrapheneOS on Pixel (minSdk 31 / Android 12+)

```bash
./gradlew :app:assembleDebug
```

The debug APK will be at `app/build/outputs/apk/debug/app-debug.apk`.

## Enrollment (Device Owner)

Full procedure: [docs/ENROLLMENT.md](docs/ENROLLMENT.md).

On a factory-reset or clean GrapheneOS device with USB debugging enabled and **no accounts**:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell dpm set-device-owner net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
```

Verify:

```bash
adb shell dumpsys device_policy | grep -A 20 "Device Owner"
```

To remove (debug / `testOnly` APKs only; production Device Owner usually requires factory reset):

```bash
adb shell dpm remove-active-admin net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
```

**Important**: Once Device Owner is set, many restrictions become permanent until a factory reset (or, for debug builds, until the test-only admin is removed). Test carefully. See [docs/ENROLLMENT.md](docs/ENROLLMENT.md#safety-notes-read-before-you-set-device-owner).

## Architecture Overview

```
┌─────────────────┐       mTLS / HTTPS        ┌─────────────────┐
│  GrapheneOS     │ ◄───────────────────────► │  Your Server     │
│  Device         │                           │  (Ansible/CA)    │
│                 │                           │                  │
│  ┌───────────┐  │                           │  - Policy store  │
│  │ MDM Agent │  │  (Device Owner)           │  - App catalog   │
│  │ (this app)│  │                           │  - Inventory DB  │
│  └──────┬────┘  │                           └──────────────────┘
│        │        │
│  DevicePolicyManager + PackageInstaller
└─────────────────┘
```

The agent runs as Device Owner, periodically checks in (or receives commands), applies policies, and installs/updates apps from a private catalog (APKs signed by you or F-Droid style).

## License

TBD (likely AGPL or Apache-2.0 + strong copyleft for the agent to keep modifications open). Currently all rights reserved pending decision.
