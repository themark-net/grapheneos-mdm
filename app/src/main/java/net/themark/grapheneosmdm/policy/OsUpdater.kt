package net.themark.grapheneosmdm.policy

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.util.Log
import net.themark.grapheneosmdm.protocol.OsUpdaterStatus

/**
 * GrapheneOS System Updater (`app.seamlessupdate.client`).
 * Its check service is not exported, and its settings activity requires a
 * signature permission, so a device-owner agent cannot download an OTA itself.
 * [requestCheck] unhides the package and opens the system update screen.
 */
internal object OsUpdater {
    const val PACKAGE = "app.seamlessupdate.client"
    private const val TAG = "OsUpdater"

    fun describe(context: Context): OsUpdaterStatus {
        return try {
            val info = context.packageManager.getPackageInfo(PACKAGE, 0)
            val enabled = context.packageManager.getApplicationEnabledSetting(PACKAGE)
            OsUpdaterStatus(
                packageName = PACKAGE,
                installed = true,
                enabled = enabled != PackageManager.COMPONENT_ENABLED_STATE_DISABLED &&
                    enabled != PackageManager.COMPONENT_ENABLED_STATE_DISABLED_USER,
                versionName = info.versionName,
            )
        } catch (_: PackageManager.NameNotFoundException) {
            OsUpdaterStatus(packageName = PACKAGE, installed = false, enabled = false)
        }
    }

    fun requestCheck(
        context: Context,
        dpm: DevicePolicyManager,
        admin: ComponentName,
    ): Boolean {
        try {
            dpm.setApplicationHidden(admin, PACKAGE, false)
            dpm.setPackagesSuspended(admin, arrayOf(PACKAGE), false)
        } catch (e: RuntimeException) {
            Log.w(TAG, "could not unhide updater", e)
        }
        val intent = Intent("android.settings.SYSTEM_UPDATE_SETTINGS")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            true
        } catch (e: RuntimeException) {
            Log.w(TAG, "system update settings not available", e)
            false
        }
    }
}
