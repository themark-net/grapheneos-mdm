package net.themark.grapheneosmdm.policy

import android.os.UserManager
import net.themark.grapheneosmdm.protocol.PolicyFlags
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PolicyRestrictionTest {

    @Test
    fun trueFlagsAddRestrictions() {
        val updates = userRestrictionUpdates(
            PolicyFlags(
                disallowAddUser = true,
                disallowFactoryReset = true,
                disallowInstallUnknownSources = true,
            ),
        )
        assertEquals(
            listOf(
                UserManager.DISALLOW_ADD_USER to true,
                UserManager.DISALLOW_FACTORY_RESET to true,
                UserManager.DISALLOW_INSTALL_UNKNOWN_SOURCES to true,
            ),
            updates,
        )
    }

    @Test
    fun falseFlagsClearRestrictions() {
        val updates = userRestrictionUpdates(
            PolicyFlags(
                disallowAddUser = false,
                disallowFactoryReset = false,
                disallowInstallUnknownSources = false,
            ),
        )
        assertTrue(updates.all { !it.second })
        assertEquals(3, updates.size)
    }

    @Test
    fun nullFlagsLeaveDeviceAlone() {
        assertTrue(userRestrictionUpdates(PolicyFlags()).isEmpty())
        val onlyCamera = userRestrictionUpdates(PolicyFlags(cameraDisabled = false))
        assertTrue(onlyCamera.isEmpty())
    }
}
