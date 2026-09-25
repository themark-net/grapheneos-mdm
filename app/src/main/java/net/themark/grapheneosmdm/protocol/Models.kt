package net.themark.grapheneosmdm.protocol

/**
 * Wire models for check-in protocol (issues #3 / #4).
 * Field names match protocol/ schema JSON files (Moshi, no renaming).
 */

data class PackageVersion(
    val packageName: String,
    val versionName: String = "",
    val versionCode: Long? = null,
)

/**
 * One position from the device. [provider] is `gps`, `fused`, or `network`.
 * [time] is when the provider produced the fix, not when the check-in ran.
 */
data class DeviceLocation(
    val latitude: Double,
    val longitude: Double,
    val accuracyMeters: Double? = null,
    val provider: String? = null,
    val time: String? = null,
)

/** One Android user this agent can see. [serial] is the stable user serial. */
data class DeviceUser(
    val serial: Long,
    val secondary: Boolean = false,
)

/** GrapheneOS System Updater (`app.seamlessupdate.client`) as installed on the device. */
data class OsUpdaterStatus(
    val packageName: String = "app.seamlessupdate.client",
    val installed: Boolean,
    val enabled: Boolean? = null,
    val versionName: String? = null,
)

/**
 * One persistent preferred activity. [activity] is the class name inside [packageName].
 */
data class PersistentPreferredActivity(
    val packageName: String,
    val activity: String,
    val action: String,
    val categories: List<String>? = null,
    val schemes: List<String>? = null,
    val mimeType: String? = null,
)

data class AttestationInfo(
    val format: String = "none",
    val payloadB64: String? = null,
    val verifiedBootState: String? = null,
)

data class InventoryReport(
    val schemaVersion: Int = 1,
    val deviceId: String,
    val osVersion: String,
    val securityPatch: String,
    val securityPatchOk: Boolean? = null,
    val installedPackages: List<PackageVersion>,
    val isDeviceOwner: Boolean? = null,
    val model: String? = null,
    val location: DeviceLocation? = null,
    val users: List<DeviceUser>? = null,
    val osUpdater: OsUpdaterStatus? = null,
    val attestation: AttestationInfo? = null,
    val reportedAt: String? = null,
)

/**
 * Desired package entry. [apkUrl] may point at the private mTLS catalog
 * (`/v1/catalog/...`) or any HTTPS URL returned in the check-in response.
 * When set, [sha256] must match the downloaded bytes before install.
 */
data class RequiredPackage(
    val packageName: String,
    val versionName: String? = null,
    val minVersionCode: Long? = null,
    val apkUrl: String? = null,
    val sha256: String? = null,
    val signingCertSha256: String? = null,
)

/**
 * One runtime-permission override for another app.
 * [state] is `granted`, `denied`, or `default`.
 */
data class PermissionGrant(
    val packageName: String,
    val permission: String,
    val state: String,
)

data class PolicyFlags(
    val disallowAddUser: Boolean? = null,
    val disallowFactoryReset: Boolean? = null,
    val disallowInstallUnknownSources: Boolean? = null,
    val cameraDisabled: Boolean? = null,
    val minSecurityPatch: String? = null,
    val passwordComplexity: String? = null,
    val maximumTimeToLockMs: Long? = null,
    val suspendedPackages: List<String>? = null,
    val hiddenPackages: List<String>? = null,
    val permissionGrants: List<PermissionGrant>? = null,
    val locationEnabled: Boolean? = null,
    val usbDataSignalingEnabled: Boolean? = null,
    val disallowConfigWifi: Boolean? = null,
    val disallowConfigMobileNetworks: Boolean? = null,
    val disallowUserSwitch: Boolean? = null,
    val persistentPreferredActivities: List<PersistentPreferredActivity>? = null,
    val lockTaskPackages: List<String>? = null,
)

data class Command(
    val type: String,
    val id: String? = null,
)

data class DesiredState(
    val schemaVersion: Int = 1,
    val requiredPackages: List<RequiredPackage> = emptyList(),
    val policyFlags: PolicyFlags = PolicyFlags(),
    val commands: List<Command>? = null,
)

data class CheckInRequest(
    val schemaVersion: Int = 1,
    val inventory: InventoryReport,
    val agentVersion: String? = null,
)

data class ShortLivedToken(
    val token: String,
    val expiresAt: String,
)

data class CheckInResponse(
    val schemaVersion: Int = 1,
    val status: String,
    val desiredState: DesiredState,
    val shortLivedToken: ShortLivedToken? = null,
    val attestationChallenge: String? = null,
    val message: String? = null,
)
