package net.themark.grapheneosmdm

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import net.themark.grapheneosmdm.service.CheckInScheduler

class GrapheneMdmApp : Application() {
    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        // WorkManager survives process death; KEEP avoids resetting the cadence
        // on every cold start while still repairing a missing schedule.
        CheckInScheduler.ensureScheduled(this)
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_MDM,
                "MDM check-in",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shown briefly while a management check-in is in progress"
            }
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(channel)
        }
    }

    companion object {
        const val CHANNEL_MDM = "mdm_service"
    }
}
