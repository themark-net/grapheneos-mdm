package net.themark.grapheneosmdm.policy

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SecurityPatchTest {

    @Test
    fun missingFloorIsCompliant() {
        assertTrue(securityPatchCompliant("2026-09-01", null))
        assertTrue(securityPatchCompliant("2026-09-01", ""))
        assertTrue(securityPatchCompliant("2026-09-01", "September"))
    }

    @Test
    fun equalOrNewerPasses() {
        assertTrue(securityPatchCompliant("2026-09-01", "2026-09-01"))
        assertTrue(securityPatchCompliant("2026-10-05", "2026-09-01"))
    }

    @Test
    fun olderFails() {
        assertFalse(securityPatchCompliant("2026-08-01", "2026-09-01"))
    }

    @Test
    fun malformedDevicePatchFailsARealFloor() {
        assertFalse(securityPatchCompliant("unknown", "2026-09-01"))
    }
}
