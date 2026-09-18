# Check-in scheduling (issue #5)

## Problem

Early builds ran `MdmService` as a **sticky foreground service** with a tight
coroutine loop every 15 minutes. That keeps a permanent notification and fights
Doze / App Standby on GrapheneOS.

## Solution (WorkManager + hybrid)

| Path | Mechanism |
|------|-----------|
| Periodic check-in | `CheckInScheduler.schedulePeriodic` → unique periodic `CheckInWorker` |
| Force from UI | `MainActivity` → `CheckInScheduler.enqueueImmediate(reason=ui)` (expedited) |
| High-priority command | Desired-state `checkin_now` → follow-up immediate work (loop-guarded) |
| Boot / DO enable | Re-ensure periodic schedule + constrained / immediate pass |
| Long-running work | `CheckInWorker.setForeground` (dataSync) only while a check-in runs |
| Escape hatch | `MdmService` one-shot (no sticky loop) |

Shared check-in body: `CheckInRunner` → `PolicyManager` + `ApiClient` (issues #3 / #4).

## Configurable knobs (`SecureConfigStore`)

| Pref | Default | Notes |
|------|---------|-------|
| `checkInIntervalMinutes` | `15` | Clamped to WorkManager periodic min (15) … 24h |
| `requireNetworkConnected` | `true` | `NetworkType.CONNECTED` on periodic work |
| `requireBatteryNotLow` | `true` | Skips periodic work when battery is low |

Call `CheckInScheduler.rescheduleFromConfig(context)` after changing interval or
constraints so the unique periodic work is `UPDATE`d.

## Doze / App Standby on GrapheneOS

- Periodic work is backed by JobScheduler and **defers under deep Doze**; this is
  intentional and battery-friendly.
- Force / `checkin_now` uses **expedited** one-time work (`OutOfQuotaPolicy` falls
  back to normal work when quota is exhausted) and requires network but **not**
  battery-not-low.
- Device Owner does **not** automatically ignore battery optimizations. For lab
  fleets that need tighter than Doze flex windows, whitelist the DPC in
  **Settings → Battery** (or grant an exemption via the usual Android UX). Do not
  resurrect a perpetual foreground loop.
- `RECEIVE_BOOT_COMPLETED` re-asserts the schedule after reboot; WorkManager also
  persists periodic work across process death.

## Explicitly parked

- QR enrollment wizard / commercial MDM packaging (#8)
