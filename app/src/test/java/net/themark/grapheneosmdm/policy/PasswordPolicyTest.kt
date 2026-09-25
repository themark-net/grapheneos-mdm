package net.themark.grapheneosmdm.policy

import android.app.admin.DevicePolicyManager
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PasswordPolicyTest {

    @Test
    fun mapsKnownComplexities() {
        assertEquals(
            DevicePolicyManager.PASSWORD_COMPLEXITY_NONE,
            passwordComplexityConstant("none"),
        )
        assertEquals(
            DevicePolicyManager.PASSWORD_COMPLEXITY_LOW,
            passwordComplexityConstant(" LOW "),
        )
        assertEquals(
            DevicePolicyManager.PASSWORD_COMPLEXITY_MEDIUM,
            passwordComplexityConstant("medium"),
        )
        assertEquals(
            DevicePolicyManager.PASSWORD_COMPLEXITY_HIGH,
            passwordComplexityConstant("high"),
        )
    }

    @Test
    fun blankOrUnknownLeavesDeviceAlone() {
        assertNull(passwordComplexityConstant(null))
        assertNull(passwordComplexityConstant(""))
        assertNull(passwordComplexityConstant("complex"))
    }

    @Test
    fun lockTimeoutZeroClearsAndNegativeIsIgnored() {
        assertEquals(0L, maximumTimeToLockMs(0L))
        assertEquals(30_000L, maximumTimeToLockMs(30_000L))
        assertNull(maximumTimeToLockMs(null))
        assertNull(maximumTimeToLockMs(-1L))
    }
}
