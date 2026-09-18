package net.themark.grapheneosmdm.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import net.themark.grapheneosmdm.service.CheckInScheduler

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED ||
            intent?.action == Intent.ACTION_LOCKED_BOOT_COMPLETED
        ) {
            Log.i(TAG, "Boot completed — ensuring WorkManager check-in schedule")
            // WorkManager persists periodic work across reboot; KEEP avoids
            // resetting the next-run window unnecessarily. Also enqueue a
            // constrained immediate pass so we do not wait a full period.
            CheckInScheduler.ensureScheduled(context)
            CheckInScheduler.enqueueImmediate(
                context,
                reason = "boot",
                requireConstraints = true,
            )
        }
    }

    companion object {
        private const val TAG = "BootReceiver"
    }
}
