package net.themark.grapheneosmdm.network

import android.content.Context
import android.util.Log
import net.themark.grapheneosmdm.policy.DeviceInventory
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * Placeholder HTTP client.
 * Later: load client certificate + CA from Android Keystore or a secure location,
 * configure OkHttp with mutual TLS, and talk to the control plane.
 */
class ApiClient(private val context: Context) {

    // TODO: replace with mTLS-configured client that uses the fleet CA
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    // Placeholder base URL — will come from a config file or QR extras later
    private val baseUrl = "https://mdm.example.invalid/api/v1"

    fun checkIn(inventory: DeviceInventory): String {
        // Stub: just log and return a dummy response
        Log.d(TAG, "Would check in inventory: deviceId=${inventory.deviceId}, " +
                "packages=${inventory.installedPackages.size}, isDO=${inventory.isDeviceOwner}")

        // Real implementation sketch:
        // val json = moshi.adapter(DeviceInventory::class.java).toJson(inventory)
        // val body = json.toRequestBody("application/json".toMediaType())
        // val request = Request.Builder().url("$baseUrl/checkin").post(body).build()
        // client.newCall(request).execute().use { ... }

        return "{\"status\":\"ok\",\"policies\":[],\"apps\":[]}"
    }

    companion object {
        private const val TAG = "ApiClient"
    }
}
