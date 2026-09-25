package net.themark.grapheneosmdm.service

import android.app.Notification
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import net.themark.grapheneosmdm.GrapheneMdmApp

/**
 * WorkManager worker that runs one mTLS check-in.
 *
 * Uses a short-lived foreground notification while active (hybrid with the old
 * sticky [MdmService] loop) so lengthy catalog downloads from #4 are less likely
 * to be killed mid-flight under Doze.
 */
class CheckInWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun getForegroundInfo(): ForegroundInfo = buildForegroundInfo()

    override suspend fun doWork(): Result {
        val reason = inputData.getString(KEY_REASON) ?: "unspecified"
        val fromCheckInNow = inputData.getBoolean(KEY_FROM_CHECKIN_NOW, false)
        Log.i(TAG, "CheckInWorker start reason=$reason fromCheckInNow=$fromCheckInNow")

        try {
            setForeground(buildForegroundInfo())
        } catch (e: Exception) {
            // Foreground promotion can fail in unit tests / restricted contexts.
            Log.w(TAG, "setForeground skipped: ${e.message}")
        }

        val outcome = CheckInRunner(applicationContext).run(
            allowFollowUpCheckIn = !fromCheckInNow,
        )
        return when (outcome) {
            CheckInRunner.Outcome.SUCCESS,
            CheckInRunner.Outcome.SKIPPED_NOT_CONFIGURED,
            -> Result.success()
            CheckInRunner.Outcome.TRANSIENT_FAILURE -> Result.retry()
            CheckInRunner.Outcome.FAILURE -> Result.failure()
        }
    }

    private fun buildForegroundInfo(): ForegroundInfo {
        val notification: Notification = NotificationCompat.Builder(
            applicationContext,
            GrapheneMdmApp.CHANNEL_MDM,
        )
            .setContentTitle("GrapheneOS MDM")
            .setContentText("Checking in with management server…")
            .setSmallIcon(android.R.drawable.ic_lock_lock)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

        return if (Build.VERSION.SDK_INT >= 29) {
            ForegroundInfo(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC or
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION,
            )
        } else {
            ForegroundInfo(NOTIFICATION_ID, notification)
        }
    }

    companion object {
        private const val TAG = "CheckInWorker"
        private const val NOTIFICATION_ID = 1001
        const val KEY_REASON = "reason"
        const val KEY_FROM_CHECKIN_NOW = "from_checkin_now"
    }
}
