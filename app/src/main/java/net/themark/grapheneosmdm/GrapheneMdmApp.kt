package net.themark.grapheneosmdm

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class GrapheneMdmApp : Application() {
    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_MDM,
                "MDM Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Background device management and check-in"
            }
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(channel)
        }
    }

    companion object {
        const val CHANNEL_MDM = "mdm_service"
    }
}
