package net.themark.grapheneosmdm.policy

import net.themark.grapheneosmdm.protocol.DeviceLocation

internal const val GRAPHENE_OTHER_SENSORS = "android.permission.OTHER_SENSORS"

internal const val LOCATION_FIX_MAX_AGE_MS = 15L * 60L * 1000L

internal const val GPS_WAIT_MS = 8_000L

/** Lower is better. GNSS first, then fused, then network. */
internal fun locationProviderRank(provider: String?): Int = when (provider) {
    "gps" -> 0
    "fused" -> 1
    "network" -> 2
    else -> 3
}

internal data class CandidateFix(
    val latitude: Double,
    val longitude: Double,
    val accuracyMeters: Float,
    val provider: String?,
    val timeEpochMs: Long,
)

internal fun validCoordinates(latitude: Double, longitude: Double): Boolean {
    if (latitude.isNaN() || longitude.isNaN()) return false
    return latitude in -90.0..90.0 && longitude in -180.0..180.0
}

/** A missing timestamp or a fix older than [maxAgeMs] should not be the only attempt. */
internal fun fixIsStale(timeEpochMs: Long, nowEpochMs: Long, maxAgeMs: Long = LOCATION_FIX_MAX_AGE_MS): Boolean {
    if (timeEpochMs <= 0L) return true
    return nowEpochMs - timeEpochMs > maxAgeMs
}

/**
 * Pick the fix to upload. Fresh GNSS beats a fresh network fix. A fresh network
 * fix beats a stale GNSS pin, which would send the server to yesterday's place.
 * When every fix is stale, the newest valid one is kept so the timestamp is visible.
 */
internal fun pickRecoveryFix(
    candidates: List<CandidateFix>,
    nowEpochMs: Long,
    maxAgeMs: Long = LOCATION_FIX_MAX_AGE_MS,
): CandidateFix? {
    val valid = candidates.filter { validCoordinates(it.latitude, it.longitude) }
    if (valid.isEmpty()) return null
    val fresh = valid.filter { !fixIsStale(it.timeEpochMs, nowEpochMs, maxAgeMs) }
    val pool = if (fresh.isNotEmpty()) {
        fresh.sortedWith(
            compareBy<CandidateFix> { locationProviderRank(it.provider) }
                .thenByDescending { it.timeEpochMs },
        )
    } else {
        valid.sortedByDescending { it.timeEpochMs }
    }
    return pool.first()
}

/** Wait for a satellite update only when we have nothing fresh to send. */
internal fun shouldWaitForGps(chosen: CandidateFix?, nowEpochMs: Long): Boolean {
    if (chosen == null) return true
    return fixIsStale(chosen.timeEpochMs, nowEpochMs)
}

internal fun toDeviceLocation(fix: CandidateFix): DeviceLocation {
    return DeviceLocation(
        latitude = fix.latitude,
        longitude = fix.longitude,
        accuracyMeters = fix.accuracyMeters.takeIf { it > 0f }?.toDouble(),
        provider = fix.provider,
        time = if (fix.timeEpochMs > 0L) {
            java.time.Instant.ofEpochMilli(fix.timeEpochMs).toString()
        } else {
            null
        },
    )
}
