package net.themark.grapheneosmdm.network

import android.content.Context
import android.util.Log
import net.themark.grapheneosmdm.protocol.CheckInRequest
import net.themark.grapheneosmdm.protocol.CheckInResponse
import net.themark.grapheneosmdm.protocol.DesiredState
import net.themark.grapheneosmdm.protocol.InventoryReport
import net.themark.grapheneosmdm.protocol.ProtocolJson
import net.themark.grapheneosmdm.security.DefaultMtlsMaterialLoader
import net.themark.grapheneosmdm.security.MtlsMaterialLoader
import net.themark.grapheneosmdm.security.SecureConfigStore
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.time.Instant
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext

/**
 * Mutual-TLS HTTPS client for inventory check-in (issue #3).
 *
 * Loads client cert + key + CA via [MtlsMaterialLoader], posts
 * [CheckInRequest] to `{baseUrl}/v1/checkin`, stores any short-lived token
 * from the response in [SecureConfigStore].
 */
class ApiClient(
    private val context: Context,
    private val config: SecureConfigStore = SecureConfigStore.create(context),
    private val materialLoader: MtlsMaterialLoader = DefaultMtlsMaterialLoader(context),
    private val agentVersion: String = "0.1.0-alpha",
) {
    @Volatile
    private var client: OkHttpClient? = null

    private fun httpClient(): OkHttpClient {
        client?.let { return it }
        synchronized(this) {
            client?.let { return it }
            val built = buildClient()
            client = built
            return built
        }
    }

    private fun buildClient(): OkHttpClient {
        val builder = OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)

        val material = materialLoader.load()
        if (material != null) {
            val ssl = SSLContext.getInstance("TLS")
            ssl.init(material.keyManagers, arrayOf(material.trustManager), null)
            builder.sslSocketFactory(ssl.socketFactory, material.trustManager)
            Log.i(TAG, "OkHttp mTLS configured from ${material.source}")
        } else {
            Log.w(TAG, "mTLS material missing — HTTPS without client cert (lab enroll incomplete)")
        }
        return builder.build()
    }

    /**
     * POST inventory; returns parsed desired-state response.
     * @throws ApiException on HTTP or parse failure
     */
    fun checkIn(inventory: InventoryReport): CheckInResponse {
        val base = config.serverBaseUrl
            ?: error("server base URL not configured (SecureConfigStore)")
        val url = base.trimEnd('/') + CHECKIN_PATH
        val requestBody = CheckInRequest(
            inventory = inventory,
            agentVersion = agentVersion,
        )
        val json = ProtocolJson.encodeRequest(requestBody)
        val httpReq = Request.Builder()
            .url(url)
            .post(json.toRequestBody(JSON_MEDIA))
            .header("Accept", "application/json")
            .header("Content-Type", "application/json")
            .apply {
                if (config.hasUsableToken()) {
                    header("Authorization", "Bearer ${config.shortLivedToken}")
                }
            }
            .build()

        httpClient().newCall(httpReq).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) {
                throw ApiException("check-in HTTP ${resp.code}: ${body.take(200)}")
            }
            val parsed = ProtocolJson.decodeResponse(body)
            persistToken(parsed)
            return parsed
        }
    }

    /** Convenience: legacy stub signature used by MdmService. */
    fun checkInLegacyJson(inventory: InventoryReport): String {
        val response = checkIn(inventory)
        return ProtocolJson.checkInResponseAdapter.toJson(response)
    }

    private fun persistToken(response: CheckInResponse) {
        val t = response.shortLivedToken ?: return
        config.shortLivedToken = t.token
        config.tokenExpiresAtEpochMs = try {
            Instant.parse(t.expiresAt).toEpochMilli()
        } catch (_: Exception) {
            0L
        }
    }

    fun setServerBaseUrl(url: String) {
        config.serverBaseUrl = url
        client = null // rebuild if URL/certs change later
    }

    companion object {
        private const val TAG = "ApiClient"
        const val CHECKIN_PATH = "/v1/checkin"
        private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()
    }
}

class ApiException(message: String, cause: Throwable? = null) : Exception(message, cause)

/** Empty desired state for offline / failed parse fallbacks. */
fun emptyDesiredState(): DesiredState = DesiredState()
