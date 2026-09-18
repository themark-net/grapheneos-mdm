package net.themark.grapheneosmdm.service

import android.content.Context
import android.util.Log
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import net.themark.grapheneosmdm.security.SecureConfigStore
import java.util.concurrent.TimeUnit

/**
 * WorkManager scheduling for MDM check-ins (issue #5).
 *
 * Periodic work respects Doze / App Standby via the platform JobScheduler
 * backend. Immediate / high-priority work uses an expedited one-time request
 * (falls back to normal when quota is exhausted).
 *
 * GrapheneOS notes: Device Owner agents are not a full battery-exemption, but
 * WorkManager + connected-network / not-low-battery constraints matches AOSP
 * guidance better than a sticky 15-minute foreground loop. Operators who need
 * tighter than Doze flex windows should whitelist the DPC in battery settings
 * (or rely on DO privilege + user exemption).
 */
object CheckInScheduler {

    const val UNIQUE_PERIODIC = "mdm_checkin_periodic"
    const val UNIQUE_IMMEDIATE = "mdm_checkin_immediate"

    /** Platform minimum for [androidx.work.PeriodicWorkRequest]. */
    const val MIN_PERIODIC_INTERVAL_MINUTES = 15L
    const val DEFAULT_INTERVAL_MINUTES = 15L
    const val MAX_INTERVAL_MINUTES = 24L * 60L

    fun ensureScheduled(context: Context) {
        schedulePeriodic(context, ExistingPeriodicWorkPolicy.KEEP)
    }

    fun rescheduleFromConfig(context: Context) {
        schedulePeriodic(context, ExistingPeriodicWorkPolicy.UPDATE)
    }

    fun schedulePeriodic(
        context: Context,
        policy: ExistingPeriodicWorkPolicy = ExistingPeriodicWorkPolicy.KEEP,
    ) {
        val store = SecureConfigStore.create(context)
        val minutes = clampIntervalMinutes(store.checkInIntervalMinutes)
        val constraints = buildConstraints(store)
        val request = PeriodicWorkRequestBuilder<CheckInWorker>(minutes, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .setInputData(
                workDataOf(
                    CheckInWorker.KEY_REASON to "periodic",
                    CheckInWorker.KEY_FROM_CHECKIN_NOW to false,
                ),
            )
            .addTag(TAG_CHECKIN)
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            UNIQUE_PERIODIC,
            policy,
            request,
        )
        Log.i(
            TAG,
            "Periodic check-in scheduled interval=${minutes}m " +
                "network=${store.requireNetworkConnected} batteryNotLow=${store.requireBatteryNotLow}",
        )
    }

    /**
     * Force an immediate check-in from UI or a high-priority `checkin_now` command.
     * Uses expedited work when possible so Doze does not delay it unduly.
     */
    fun enqueueImmediate(
        context: Context,
        reason: String = "ui",
        fromCheckInNow: Boolean = false,
        requireConstraints: Boolean = false,
    ) {
        val store = SecureConfigStore.create(context)
        val builder = OneTimeWorkRequestBuilder<CheckInWorker>()
            .setInputData(
                workDataOf(
                    CheckInWorker.KEY_REASON to reason,
                    CheckInWorker.KEY_FROM_CHECKIN_NOW to fromCheckInNow,
                ),
            )
            .addTag(TAG_CHECKIN)
            .addTag(TAG_IMMEDIATE)

        if (requireConstraints) {
            builder.setConstraints(buildConstraints(store))
        } else {
            // Force path: still require network so we do not burn retries offline,
            // but do not wait on battery-not-low.
            builder.setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build(),
            )
        }

        try {
            builder.setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
        } catch (_: Exception) {
            // Older test fakes / stubs may not implement expedited.
        }

        WorkManager.getInstance(context).enqueueUniqueWork(
            UNIQUE_IMMEDIATE,
            ExistingWorkPolicy.REPLACE,
            builder.build(),
        )
        Log.i(TAG, "Immediate check-in enqueued reason=$reason fromCheckInNow=$fromCheckInNow")
    }

    fun cancelAll(context: Context) {
        val wm = WorkManager.getInstance(context)
        wm.cancelUniqueWork(UNIQUE_PERIODIC)
        wm.cancelUniqueWork(UNIQUE_IMMEDIATE)
        wm.cancelAllWorkByTag(TAG_CHECKIN)
        Log.i(TAG, "All check-in work cancelled")
    }

    fun buildConstraints(store: SecureConfigStore): Constraints {
        val b = Constraints.Builder()
        if (store.requireNetworkConnected) {
            b.setRequiredNetworkType(NetworkType.CONNECTED)
        } else {
            b.setRequiredNetworkType(NetworkType.NOT_REQUIRED)
        }
        b.setRequiresBatteryNotLow(store.requireBatteryNotLow)
        // Do not require device idle — MDM check-ins should run when the user
        // is active too; WorkManager still defers under deep Doze as needed.
        b.setRequiresDeviceIdle(false)
        b.setRequiresCharging(false)
        b.setRequiresStorageNotLow(true)
        return b.build()
    }

    /** Clamp to WorkManager periodic bounds. */
    fun clampIntervalMinutes(requested: Long): Long =
        requested.coerceIn(MIN_PERIODIC_INTERVAL_MINUTES, MAX_INTERVAL_MINUTES)

    const val TAG_CHECKIN = "mdm_checkin"
    const val TAG_IMMEDIATE = "mdm_checkin_immediate"
    private const val TAG = "CheckInScheduler"
}
