package net.themark.grapheneosmdm.protocol

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory

/**
 * Shared Moshi instance for check-in encode/decode.
 * Keep adapters aligned with protocol/ schema JSON files.
 */
object ProtocolJson {
    val moshi: Moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    val inventoryAdapter = moshi.adapter(InventoryReport::class.java)
    val desiredStateAdapter = moshi.adapter(DesiredState::class.java)
    val checkInRequestAdapter = moshi.adapter(CheckInRequest::class.java)
    val checkInResponseAdapter = moshi.adapter(CheckInResponse::class.java)

    fun encodeRequest(request: CheckInRequest): String =
        checkInRequestAdapter.toJson(request)

    fun decodeResponse(json: String): CheckInResponse =
        checkInResponseAdapter.fromJson(json)
            ?: error("empty or invalid check-in response JSON")
}
