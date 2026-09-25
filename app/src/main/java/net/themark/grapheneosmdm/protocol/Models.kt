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
    val message: String? = null,
)
