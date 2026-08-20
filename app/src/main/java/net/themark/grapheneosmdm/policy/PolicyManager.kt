package net.themark.grapheneosmdm.policy

import android.app.admin.DevicePolicyManager
import android.content.Context
import android.os.UserManager
import android.util.Log
import net.themark.grapheneosmdm.receiver.DeviceAdminReceiver

data class DeviceInventory(
    val deviceId: String,
    val isDeviceOwner: Boolean,
    val androidVersion: String,
    val securityPatch: String,
    val installedPackages: List<String>,
    // expand later: battery, storage, attestation, etc.
)

class PolicyManager(private val context: Context) {

    private val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    private val admin = DeviceAdminReceiver.getComponentName(context)

    fun isDeviceOwner(): Boolean = dpm.isDeviceOwnerApp(context.packageName)

    fun collectInventory(): DeviceInventory {
        val pm = context.packageManager
        val packages = pm.getInstalledPackages(0).map { it.packageName }.sorted()
        return DeviceInventory(
            deviceId = android.provider.Settings.Secure.getString(
                context.contentResolver,
                android.provider.Settings.Secure.ANDROID_ID
            ) ?: "unknown",
            isDeviceOwner = isDeviceOwner(),
            androidVersion = android.os.Build.VERSION.RELEASE,
            securityPatch = android.os.Build.VERSION.SECURITY_PATCH,
            installedPackages = packages
        )
    }

    /**
     * Example restrictions useful for a managed fleet.
     * Call only when isDeviceOwner() == true.
     */
    fun applySampleRestrictions() {
        if (!isDeviceOwner()) {
            Log.w(TAG, "Not device owner — cannot apply restrictions")
            return
        }
        // Prevent adding new users / accounts that could escape management
        dpm.addUserRestriction(admin, UserManager.DISALLOW_ADD_USER)
        dpm.addUserRestriction(admin, UserManager.DISALLOW_FACTORY_RESET)
        // Optional: dpm.addUserRestriction(admin, UserManager.DISALLOW_INSTALL_UNKNOWN_SOURCES)
        // (careful — we ourselves need to install APKs)

        Log.i(TAG, "Sample restrictions applied")
    }

    fun lockNow() {
        if (isDeviceOwner()) {
            dpm.lockNow()
        }
    }

    fun wipeData() {
        if (isDeviceOwner()) {
            // FLAG_WIPE_EXTERNAL_STORAGE | FLAG_WIPE_RESET_PROTECTION_DATA etc. as needed
            dpm.wipeData(0)
        }
    }

    companion object {
        private const val TAG = "PolicyManager"
    }
}
