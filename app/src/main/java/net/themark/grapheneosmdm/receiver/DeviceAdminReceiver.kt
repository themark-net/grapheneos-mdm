package net.themark.grapheneosmdm.receiver

import android.app.admin.DeviceAdminReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.util.Log
import net.themark.grapheneosmdm.provision.applyProvisioningExtras
import net.themark.grapheneosmdm.service.CheckInScheduler

/**
 * Device Admin / Device Owner receiver.
 *
 * Enrollment (ADB today; QR is not available on stock GrapheneOS): docs/ENROLLMENT.md
 *
 * Once set as Device Owner via:
 *   adb shell dpm set-device-owner net.themark.grapheneosmdm/.receiver.DeviceAdminReceiver
 * this component receives system callbacks and grants the app full DevicePolicyManager powers.
 *
 * Manifest: exported=true + BIND_DEVICE_ADMIN (required for the system to bind this receiver).
 */
class DeviceAdminReceiver : DeviceAdminReceiver() {

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.i(TAG, "Device admin enabled")
        scheduleCheckIns(context, reason = "admin_enabled")
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.w(TAG, "Device admin disabled")
        CheckInScheduler.cancelAll(context)
    }

    override fun onProfileProvisioningComplete(context: Context, intent: Intent) {
        super.onProfileProvisioningComplete(context, intent)
        Log.i(TAG, "Profile provisioning complete — becoming Device Owner")
        applyProvisioningExtras(context, intent)
        scheduleCheckIns(context, reason = "provisioning_complete")
    }

    private fun scheduleCheckIns(context: Context, reason: String) {
        CheckInScheduler.ensureScheduled(context)
        CheckInScheduler.enqueueImmediate(context, reason = reason)
    }

    companion object {
        private const val TAG = "DeviceAdminReceiver"

        fun getComponentName(context: Context): ComponentName =
            // The android.app.admin.DeviceAdminReceiver import shadows this
            // class. DeviceAdminReceiver::class in the companion is the
            // framework class, and DevicePolicyManager rejects that admin.
            ComponentName(
                context.applicationContext,
                net.themark.grapheneosmdm.receiver.DeviceAdminReceiver::class.java,
            )
    }
}
