package net.themark.grapheneosmdm.service

import android.app.Notification
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import net.themark.grapheneosmdm.GrapheneMdmApp
import net.themark.grapheneosmdm.network.ApiClient
import net.themark.grapheneosmdm.network.ApiException
import net.themark.grapheneosmdm.policy.PolicyManager

/**
 * Lightweight foreground service that performs periodic mTLS check-ins.
 * WorkManager migration is issue #5 — parked; this loop is enough for lab.
 */
class MdmService : Service() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private lateinit var apiClient: ApiClient
    private lateinit var policyManager: PolicyManager

    override fun onCreate() {
        super.onCreate()
        apiClient = ApiClient(this)
        policyManager = PolicyManager(this)
        startForeground(NOTIFICATION_ID, buildNotification())
        Log.i(TAG, "MdmService started")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        scope.launch {
            while (isActive) {
                try {
                    performCheckIn()
                } catch (e: Exception) {
                    Log.e(TAG, "Check-in failed", e)
                }
                delay(CHECK_IN_INTERVAL_MS)
            }
        }
        return START_STICKY
    }

    private fun performCheckIn() {
        Log.d(TAG, "Performing check-in…")
        val inventory = policyManager.collectInventory()
        try {
            val response = apiClient.checkIn(inventory)
            if (response.status == "ok") {
                policyManager.applyDesiredState(response.desiredState)
            } else {
                Log.w(TAG, "Server status=${response.status} msg=${response.message}")
            }
            Log.d(TAG, "Check-in complete status=${response.status}")
        } catch (e: IllegalStateException) {
            // Base URL not configured yet — expected before lab enroll.
            Log.i(TAG, "Check-in skipped: ${e.message}")
        } catch (e: ApiException) {
            Log.e(TAG, "Check-in API error: ${e.message}")
        }
    }

    private fun buildNotification(): Notification {
        return NotificationCompat.Builder(this, GrapheneMdmApp.CHANNEL_MDM)
            .setContentTitle("GrapheneOS MDM")
            .setContentText("Device management active")
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
        private const val NOTIFICATION_ID = 1001
        private const val CHECK_IN_INTERVAL_MS = 15 * 60 * 1000L
    }
}
