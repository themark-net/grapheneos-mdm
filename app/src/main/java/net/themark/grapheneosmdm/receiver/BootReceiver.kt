package net.themark.grapheneosmdm.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import net.themark.grapheneosmdm.service.MdmService

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED ||
            intent?.action == Intent.ACTION_LOCKED_BOOT_COMPLETED
        ) {
            Log.i(TAG, "Boot completed — starting MDM service")
            val serviceIntent = Intent(context, MdmService::class.java)
            context.startForegroundService(serviceIntent)
        }
    }

    companion object {
        private const val TAG = "BootReceiver"
    }
}
