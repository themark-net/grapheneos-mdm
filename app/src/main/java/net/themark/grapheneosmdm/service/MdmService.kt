package net.themark.grapheneosmdm.service

import android.app.Notification
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import net.themark.grapheneosmdm.GrapheneMdmApp
import net.themark.grapheneosmdm.R
import net.themark.grapheneosmdm.network.ApiClient
import net.themark.grapheneosmdm.policy.PolicyManager
import kotlinx.coroutines.*

/**
 * Lightweight foreground service that keeps the agent alive and performs periodic check-ins.
 * Later this can be replaced / supplemented by WorkManager for better battery behaviour.
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

    private suspend fun performCheckIn() {
        Log.d(TAG, "Performing check-in…")
        // 1. Collect inventory
        // 2. POST to server
        // 3. Receive desired state / commands
        // 4. Apply via PolicyManager + AppManager
        val inventory = policyManager.collectInventory()
        val response = apiClient.checkIn(inventory)
        // TODO: apply response.policies and response.apps
        Log.d(TAG, "Check-in complete (stub). Server response: $response")
    }

    private fun buildNotification(): Notification {
        return NotificationCompat.Builder(this, GrapheneMdmApp.CHANNEL_MDM)
            .setContentTitle("GrapheneOS MDM")
            .setContentText("Device management active")
            .setSmallIcon(android.R.drawable.ic_lock_lock) // replace with proper icon later
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
        private const val CHECK_IN_INTERVAL_MS = 15 * 60 * 1000L // 15 min for early testing
    }
}
