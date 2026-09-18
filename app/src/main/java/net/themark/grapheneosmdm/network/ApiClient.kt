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
import okio.buffer
import okio.sink
import java.io.File
import java.time.Instant
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext

/**
 * Mutual-TLS HTTPS client for inventory check-in and private catalog APK download.
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
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)

        val material = materialLoader.load()
        if (material != null) {
            val ssl = SSLContext.getInstance("TLS")
            ssl.init(material.keyManagers, arrayOf(material.trustManager), null)
            builder.sslSocketFactory(ssl.socketFactory, material.trustManager)
            Log.i(TAG, "OkHttp mTLS configured from ${material.source}")
        } else {
            Log.w(TAG, "mTLS material missing - HTTPS without client cert (lab enroll incomplete)")
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

    /**
     * Download an APK from the private catalog (or any absolute HTTPS URL from check-in).
     * Relative paths like `/v1/catalog/foo.apk` are resolved against [SecureConfigStore.serverBaseUrl].
     */
    fun downloadApk(apkUrl: String, dest: File) {
        val resolved = resolveUrl(apkUrl)
        val httpReq = Request.Builder()
            .url(resolved)
            .get()
            .header("Accept", "application/vnd.android.package-archive, application/octet-stream, */*")
            .apply {
                if (config.hasUsableToken()) {
                    header("Authorization", "Bearer ${config.shortLivedToken}")
                }
            }
            .build()
        httpClient().newCall(httpReq).execute().use { resp ->
            if (!resp.isSuccessful) {
                throw ApiException("APK download HTTP ${resp.code} for $resolved")
            }
            val body = resp.body ?: throw ApiException("APK download empty body")
            dest.parentFile?.mkdirs()
            dest.sink().buffer().use { sink ->
                sink.writeAll(body.source())
            }
            Log.i(TAG, "Downloaded APK ${dest.length()} bytes -> ${dest.name}")
        }
    }

    private fun resolveUrl(apkUrl: String): String {
        if (apkUrl.startsWith("https://", ignoreCase = true) ||
            apkUrl.startsWith("http://", ignoreCase = true)
        ) {
            return apkUrl
        }
        val base = config.serverBaseUrl
            ?: error("server base URL not configured for relative catalog URL")
        return base.trimEnd('/') + "/" + apkUrl.trimStart('/')
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
        const val CATALOG_PATH_PREFIX = "/v1/catalog/"
        private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()
    }
}

class ApiException(message: String, cause: Throwable? = null) : Exception(message, cause)

/** Empty desired state for offline / failed parse fallbacks. */
fun emptyDesiredState(): DesiredState = DesiredState()
