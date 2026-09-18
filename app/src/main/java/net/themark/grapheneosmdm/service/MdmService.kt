package net.themark.grapheneosmdm.service

import android.app.Notification
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import net.themark.grapheneosmdm.GrapheneMdmApp

/**
 * Optional one-shot foreground helper for a single check-in.
 *
 * Issue #5 replaces the old sticky 15-minute loop with WorkManager
 * ([CheckInScheduler] / [CheckInWorker]). This service remains as a hybrid
 * escape hatch (e.g. callers that already hold a foreground context) and
 * simply runs [CheckInRunner] once, then stops. Prefer
 * [CheckInScheduler.enqueueImmediate] for UI / boot / DO paths.
 */
class MdmService : Service() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = buildNotification()
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        val reason = intent?.getStringExtra(EXTRA_REASON) ?: "service"
        scope.launch {
            try {
                Log.i(TAG, "One-shot check-in via MdmService reason=$reason")
                CheckInRunner(applicationContext).run()
            } catch (e: Exception) {
                Log.e(TAG, "One-shot check-in failed", e)
            } finally {
                stopSelf(startId)
            }
        }
        return START_NOT_STICKY
    }

    private fun buildNotification(): Notification {
        return NotificationCompat.Builder(this, GrapheneMdmApp.CHANNEL_MDM)
            .setContentTitle("GrapheneOS MDM")
            .setContentText("Checking in with management server…")
            .setSmallIcon(android.R.drawable.ic_lock_lock)
            .setOngoing(true)
            .build()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        private const val TAG = "MdmService"
        private const val NOTIFICATION_ID = 1002
        const val EXTRA_REASON = "reason"

        /** Legacy helper — prefer [CheckInScheduler.enqueueImmediate]. */
        fun startOneShot(context: Context, reason: String = "legacy") {
            val intent = Intent(context, MdmService::class.java).putExtra(EXTRA_REASON, reason)
            ContextCompat.startForegroundService(context, intent)
        }
    }
}
