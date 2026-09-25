# Check-in protocol (issue #3)

Minimal JSON schemas shared by the Android agent and the lab check-in server.

| Schema | Role |
|--------|------|
| `inventory-report.schema.json` | Device → server inventory body |
| `desired-state.schema.json` | Server desired packages + policy flags |
| `checkin-request.schema.json` | `POST /v1/checkin` request envelope |
| `checkin-response.schema.json` | Response envelope (desired state + optional short-lived token) |

Wire format is JSON over HTTPS with **mutual TLS** (fleet/lab CA). See [docs/MTLS.md](../docs/MTLS.md).

Kotlin models live in `app/.../protocol/` and must stay field-compatible with these schemas.

Lock-screen and visibility flags on `policyFlags`: `passwordComplexity` (`none` / `low` / `medium` / `high`), `maximumTimeToLockMs`, `suspendedPackages`, `hiddenPackages`. Omit a flag to leave that device setting alone. Packages this agent itself installed are uninstalled when they leave `requiredPackages`. Other installed apps are not.

`permissionGrants` is the full set of runtime permission overrides for other apps (`granted` / `denied` / `default`). Omit it to leave grants alone. An entry that drops off is reset to `default`. The agent package is ignored.

`locationEnabled` turns the location radio on or off. When it is on, the next inventory may include `location` (GNSS preferred). The agent grants itself coarse, fine, and background location, and on GrapheneOS `android.permission.OTHER_SENSORS` while the radio is on. `usbDataSignalingEnabled` controls USB data. `disallowConfigWifi` and `disallowConfigMobileNetworks` block the user from changing those radios. Omit any of these to leave the device alone.
