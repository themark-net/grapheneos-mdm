package net.themark.grapheneosmdm.policy

import android.app.admin.DevicePolicyManager
import android.content.Context
import android.os.Build
import android.os.UserManager
import android.util.Log
import net.themark.grapheneosmdm.apps.DesiredAppsEnforcer
import net.themark.grapheneosmdm.protocol.AttestationInfo
import net.themark.grapheneosmdm.protocol.DesiredState
import net.themark.grapheneosmdm.protocol.InventoryReport
import net.themark.grapheneosmdm.protocol.PackageVersion
import net.themark.grapheneosmdm.protocol.PolicyFlags
import net.themark.grapheneosmdm.receiver.DeviceAdminReceiver
import java.time.Instant

/**
 * True adds the user restriction, false clears it. A null flag is omitted so the
 * device setting is left alone.
 */
internal fun userRestrictionUpdates(flags: PolicyFlags): List<Pair<String, Boolean>> {
    return listOfNotNull(
        flags.disallowAddUser?.let { UserManager.DISALLOW_ADD_USER to it },
        flags.disallowFactoryReset?.let { UserManager.DISALLOW_FACTORY_RESET to it },
        flags.disallowInstallUnknownSources?.let { UserManager.DISALLOW_INSTALL_UNKNOWN_SOURCES to it },
    )
}

/**
 * Collects inventory and applies [DesiredState] policy flags + desired-apps
 * enforcement on every check-in (issue #4 closes packages-logged residual from #3).
 */
class PolicyManager(
    private val context: Context,
    private val desiredAppsEnforcer: DesiredAppsEnforcer = DesiredAppsEnforcer(context),
) {

    private val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    private val admin = DeviceAdminReceiver.getComponentName(context)
    private val compliancePrefs = context.getSharedPreferences(COMPLIANCE_PREFS, Context.MODE_PRIVATE)

    fun isDeviceOwner(): Boolean = dpm.isDeviceOwnerApp(context.packageName)

    fun collectInventory(): InventoryReport {
        val pm = context.packageManager
        val packages = pm.getInstalledPackages(0).map { pi ->
            @Suppress("DEPRECATION")
            val code = if (Build.VERSION.SDK_INT >= 28) {
                pi.longVersionCode
            } else {
                pi.versionCode.toLong()
            }
            PackageVersion(
                packageName = pi.packageName,
                versionName = pi.versionName.orEmpty(),
                versionCode = code,
            )
        }.sortedBy { it.packageName }

        return InventoryReport(
            deviceId = android.provider.Settings.Secure.getString(
                context.contentResolver,
                android.provider.Settings.Secure.ANDROID_ID,
            ) ?: "unknown",
            osVersion = Build.VERSION.RELEASE,
            securityPatch = Build.VERSION.SECURITY_PATCH,
            securityPatchOk = storedSecurityPatchOk(),
            installedPackages = packages,
            isDeviceOwner = isDeviceOwner(),
            model = Build.MODEL,
            attestation = AttestationInfo(format = "none"),
            reportedAt = Instant.now().toString(),
        )
    }

    /**
     * Apply policy flags, then persist + enforce the desired-apps list.
     */
    fun applyDesiredState(state: DesiredState) {
        recordSecurityPatchFloor(state.policyFlags.minSecurityPatch)
        if (!isDeviceOwner()) {
            Log.w(TAG, "Not device owner - skipping policy apply")
            // Still persist desired list for when DO is granted.
            desiredAppsEnforcer.persistAndEnforce(state.requiredPackages)
            return
        }
        val flags: PolicyFlags = state.policyFlags
        for ((restriction, disallow) in userRestrictionUpdates(flags)) {
            if (disallow) {
                // Unknown-sources restriction blocks user sideload; Device Owner
                // PackageInstaller sessions still work.
                dpm.addUserRestriction(admin, restriction)
            } else {
                dpm.clearUserRestriction(admin, restriction)
            }
        }
        if (flags.cameraDisabled == true) {
            dpm.setCameraDisabled(admin, true)
        } else if (flags.cameraDisabled == false) {
            dpm.setCameraDisabled(admin, false)
        }
        flags.lockTaskPackages?.let { pkgs ->
            dpm.setLockTaskPackages(admin, pkgs.toTypedArray())
        }
        state.commands.orEmpty().forEach { cmd ->
            when (cmd.type) {
                "lock" -> lockNow()
                "wipe" -> wipeData()
                "reboot" -> {
                    if (Build.VERSION.SDK_INT >= 24) {
                        dpm.reboot(admin)
                    }
                }
                "noop" -> Log.d(TAG, "command noop id=${cmd.id}")
                // Immediate follow-up is enqueued by CheckInRunner after apply.
                "checkin_now" -> Log.d(TAG, "command checkin_now id=${cmd.id} (scheduler follow-up)")
                else -> Log.w(TAG, "unknown command ${cmd.type}")
            }
        }

        val report = desiredAppsEnforcer.persistAndEnforce(state.requiredPackages)
        Log.i(
            TAG,
            "Desired apps enforced: ok=${report.installedOk.size} " +
                "failed=${report.failed.size} skipped=${report.skipped.size}",
        )
        Log.i(TAG, "Desired state policy flags applied")
    }

    fun applySampleRestrictions() {
        if (!isDeviceOwner()) {
            Log.w(TAG, "Not device owner - cannot apply restrictions")
            return
        }
        dpm.addUserRestriction(admin, UserManager.DISALLOW_ADD_USER)
        dpm.addUserRestriction(admin, UserManager.DISALLOW_FACTORY_RESET)
        Log.i(TAG, "Sample restrictions applied")
    }

    private fun recordSecurityPatchFloor(minPatch: String?) {
        val edit = compliancePrefs.edit()
        if (minPatch.isNullOrBlank() || !SECURITY_PATCH_DATE.matches(minPatch)) {
            edit.remove(KEY_SECURITY_PATCH_OK).apply()
            return
        }
        val patch = Build.VERSION.SECURITY_PATCH.orEmpty()
        val ok = securityPatchCompliant(patch, minPatch)
        if (!ok) {
            Log.w(TAG, "security patch $patch is older than $minPatch")
        }
        edit.putBoolean(KEY_SECURITY_PATCH_OK, ok).apply()
    }

    private fun storedSecurityPatchOk(): Boolean? {
        if (!compliancePrefs.contains(KEY_SECURITY_PATCH_OK)) return null
        return compliancePrefs.getBoolean(KEY_SECURITY_PATCH_OK, true)
    }

    fun lockNow() {
        if (isDeviceOwner()) dpm.lockNow()
    }

    fun wipeData() {
        if (isDeviceOwner()) dpm.wipeData(0)
    }

    companion object {
        private const val TAG = "PolicyManager"
        private const val COMPLIANCE_PREFS = "policy_compliance"
        private const val KEY_SECURITY_PATCH_OK = "security_patch_ok"
    }
}

/** @deprecated Use [InventoryReport] from protocol package. Kept for any external refs. */
@Deprecated("Use protocol.InventoryReport", ReplaceWith("net.themark.grapheneosmdm.protocol.InventoryReport"))
data class DeviceInventory(
    val deviceId: String,
    val isDeviceOwner: Boolean,
    val androidVersion: String,
    val securityPatch: String,
    val installedPackages: List<String>,
)
