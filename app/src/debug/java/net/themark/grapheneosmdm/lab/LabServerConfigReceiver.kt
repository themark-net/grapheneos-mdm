package net.themark.grapheneosmdm.lab

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.util.Log
import net.themark.grapheneosmdm.network.ApiClient
import net.themark.grapheneosmdm.provision.normalizeProvisioningServerUrl
import net.themark.grapheneosmdm.security.SecureConfigStore
import net.themark.grapheneosmdm.service.CheckInRunner

/**
 * Debug-only lab hook for a headless emulator (issue #36).
 *
 * [SecureConfigStore.serverBaseUrl] lives in encrypted prefs. The existing
 * Check-in button does not set it, and `adb shell am` cannot pass the
 * provisioning PersistableBundle. This receiver is not a screen. Release
 * builds do not include it. The sender must hold [android.permission.DUMP]
 * (adb shell does; a normal app does not).
 *
 * The URL is written on the same [SecureConfigStore] instance the check-in
 * reads. [android.content.SharedPreferences.Editor.apply] updates that
 * instance immediately, but a second EncryptedSharedPreferences object can
 * still see the old value.
 */
class LabServerConfigReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != ACTION) return
        val flags = context.applicationInfo.flags
        if (flags and ApplicationInfo.FLAG_DEBUGGABLE == 0) {
            Log.w(TAG, "ignored: process is not debuggable")
            return
        }
        val url = normalizeProvisioningServerUrl(intent.getStringExtra(EXTRA_URL))
        if (url == null) {
            Log.w(TAG, "ignored: serverBaseUrl missing or not https")
            return
        }
        val appContext = context.applicationContext
        // adb shell am broadcast is not ordered. setResultCode throws
        // "Call while result is not pending" and kills the process first.
        val pending = goAsync()
        Thread {
            try {
                val store = SecureConfigStore.create(appContext)
                store.serverBaseUrl = url
                Log.i(TAG, "lab server base URL saved")
                val outcome = CheckInRunner(
                    appContext,
                    apiClient = ApiClient(appContext, config = store),
                ).run(allowFollowUpCheckIn = false)
                Log.i(TAG, "lab-checkin outcome=$outcome")
            } catch (e: Exception) {
                Log.e(TAG, "lab-checkin failed: ${e.message}", e)
            } finally {
                pending.finish()
            }
        }.start()
    }

    companion object {
        const val ACTION = "net.themark.grapheneosmdm.action.SET_LAB_SERVER"
        const val EXTRA_URL = "serverBaseUrl"
        private const val TAG = "LabServerConfig"
    }
}
