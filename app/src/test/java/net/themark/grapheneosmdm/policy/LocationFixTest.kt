package net.themark.grapheneosmdm.policy

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LocationFixTest {

    private val now = 1_700_000_000_000L

    @Test
    fun freshGpsBeatsFreshNetwork() {
        val picked = pickRecoveryFix(
            listOf(
                fix("network", ageMs = 60_000),
                fix("gps", ageMs = 30_000),
            ),
            now,
        )
        assertEquals("gps", picked!!.provider)
    }

    @Test
    fun freshNetworkBeatsStaleGps() {
        val picked = pickRecoveryFix(
            listOf(
                fix("gps", ageMs = 2 * 60 * 60 * 1000L),
                fix("network", ageMs = 10_000),
            ),
            now,
        )
        assertEquals("network", picked!!.provider)
    }

    @Test
    fun staleFixesKeepTheNewest() {
        val older = fix("gps", ageMs = 3 * 60 * 60 * 1000L)
        val newer = fix("network", ageMs = 2 * 60 * 60 * 1000L)
        val picked = pickRecoveryFix(listOf(older, newer), now)
        assertEquals(newer.timeEpochMs, picked!!.timeEpochMs)
    }

    @Test
    fun rejectsOutOfRangeAndEmpty() {
        val bad = CandidateFix(91.0, 0.0, 5f, "gps", now)
        assertNull(pickRecoveryFix(listOf(bad), now))
        assertNull(pickRecoveryFix(emptyList(), now))
        assertFalse(validCoordinates(Double.NaN, 0.0))
    }

    @Test
    fun waitsForGpsOnlyWhenNothingIsFresh() {
        assertTrue(shouldWaitForGps(null, now))
        assertFalse(shouldWaitForGps(fix("network", ageMs = 5_000), now))
        assertTrue(shouldWaitForGps(fix("gps", ageMs = 2 * 60 * 60 * 1000L), now))
    }

    private fun fix(provider: String, ageMs: Long) = CandidateFix(
        latitude = 37.4,
        longitude = -122.1,
        accuracyMeters = 8f,
        provider = provider,
        timeEpochMs = now - ageMs,
    )
}
