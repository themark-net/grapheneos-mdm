package net.themark.grapheneosmdm.policy

import android.app.admin.DevicePolicyManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.UserManager
import android.util.Log
import net.themark.grapheneosmdm.protocol.AttestationInfo
import net.themark.grapheneosmdm.protocol.DesiredState
import net.themark.grapheneosmdm.protocol.InventoryReport
import net.themark.grapheneosmdm.protocol.PackageVersion
import net.themark.grapheneosmdm.protocol.PolicyFlags
import net.themark.grapheneosmdm.receiver.DeviceAdminReceiver
import java.time.Instant

/**
 * Collects inventory and applies a subset of [DesiredState] policy flags.
 * Full AppManager catalog install path is issue #4 — not implemented here.
 */
class PolicyManager(private val context: Context) {

    private val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    private val admin = DeviceAdminReceiver.getComponentName(context)

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
            installedPackages = packages,
            isDeviceOwner = isDeviceOwner(),
            model = Build.MODEL,
            attestation = AttestationInfo(format = "none"),
            reportedAt = Instant.now().toString(),
        )
    }

    /**
     * Apply policy flags from desired state. Package install/update is deferred to #4.
     */
    fun applyDesiredState(state: DesiredState) {
        if (!isDeviceOwner()) {
            Log.w(TAG, "Not device owner — skipping policy apply")
            return
        }
        val flags: PolicyFlags = state.policyFlags
        if (flags.disallowAddUser == true) {
            dpm.addUserRestriction(admin, UserManager.DISALLOW_ADD_USER)
        }
        if (flags.disallowFactoryReset == true) {
            dpm.addUserRestriction(admin, UserManager.DISALLOW_FACTORY_RESET)
        }
        if (flags.disallowInstallUnknownSources == true) {
            dpm.addUserRestriction(admin, UserManager.DISALLOW_INSTALL_UNKNOWN_SOURCES)
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
                "noop", "checkin_now" -> Log.d(TAG, "command ${cmd.type} id=${cmd.id}")
                else -> Log.w(TAG, "unknown command ${cmd.type}")
            }
        }
        if (state.requiredPackages.isNotEmpty()) {
            Log.i(
                TAG,
                "Desired requiredPackages=${state.requiredPackages.size} (install path = issue #4)",
            )
        }
        Log.i(TAG, "Desired state policy flags applied")
    }

    fun applySampleRestrictions() {
        if (!isDeviceOwner()) {
            Log.w(TAG, "Not device owner — cannot apply restrictions")
            return
        }
        dpm.addUserRestriction(admin, UserManager.DISALLOW_ADD_USER)
        dpm.addUserRestriction(admin, UserManager.DISALLOW_FACTORY_RESET)
        Log.i(TAG, "Sample restrictions applied")
    }

    fun lockNow() {
        if (isDeviceOwner()) dpm.lockNow()
    }

    fun wipeData() {
        if (isDeviceOwner()) dpm.wipeData(0)
    }

    companion object {
        private const val TAG = "PolicyManager"
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
