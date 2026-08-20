package net.themark.grapheneosmdm.receiver

import android.app.admin.DeviceAdminReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.util.Log
import net.themark.grapheneosmdm.service.MdmService

/**
 * Device Admin / Device Owner receiver.
 *
 * Once set as Device Owner via:
 *   adb shell dpm set-device-owner net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
 * this component receives system callbacks and grants the app full DevicePolicyManager powers.
 */
class DeviceAdminReceiver : DeviceAdminReceiver() {

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.i(TAG, "Device admin enabled")
        startService(context)
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.w(TAG, "Device admin disabled")
    }

    override fun onProfileProvisioningComplete(context: Context, intent: Intent) {
        super.onProfileProvisioningComplete(context, intent)
        Log.i(TAG, "Profile provisioning complete — becoming Device Owner")
        // In a full QR / managed provisioning flow this is where we finish setup.
        startService(context)
    }

    private fun startService(context: Context) {
        val serviceIntent = Intent(context, MdmService::class.java)
        context.startForegroundService(serviceIntent)
    }

    companion object {
        private const val TAG = "DeviceAdminReceiver"

        fun getComponentName(context: Context): ComponentName =
            ComponentName(context.applicationContext, DeviceAdminReceiver::class.java)
    }
}
