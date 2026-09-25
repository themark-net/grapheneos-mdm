package net.themark.grapheneosmdm.policy

import org.junit.Assert.assertEquals
import org.junit.Test

class DeviceUsersTest {

    @Test
    fun callingUserIsFirstAndDuplicatesAreDropped() {
        val users = deviceUsers(callingSerial = 0, secondarySerials = listOf(10, 0, -1, 10, 12))
        assertEquals(listOf(0L, 10L, 12L), users.map { it.serial })
        assertEquals(listOf(false, true, true), users.map { it.secondary })
    }
}
