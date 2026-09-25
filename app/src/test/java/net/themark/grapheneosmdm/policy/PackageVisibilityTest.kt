package net.themark.grapheneosmdm.policy

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PackageVisibilityTest {

    @Test
    fun nullListLeavesDeviceAlone() {
        assertNull(packageSetChange(setOf("com.old"), null, "net.themark.grapheneosmdm"))
    }

    @Test
    fun reassertsDesiredAndTurnsOffDropped() {
        val change = packageSetChange(
            previous = setOf("com.old", "com.stay"),
            desired = listOf("com.stay", "com.new", "  com.new  "),
            selfPackage = "net.themark.grapheneosmdm",
        )!!
        assertEquals(listOf("com.new", "com.stay"), change.assertOn)
        assertEquals(listOf("com.old"), change.turnOff)
        assertEquals(setOf("com.new", "com.stay"), change.next)
    }

    @Test
    fun emptyListClearsPreviousAndSkipsSelf() {
        val change = packageSetChange(
            previous = setOf("com.old", "net.themark.grapheneosmdm"),
            desired = listOf("net.themark.grapheneosmdm"),
            selfPackage = "net.themark.grapheneosmdm",
        )!!
        assertEquals(emptyList<String>(), change.assertOn)
        assertEquals(listOf("com.old"), change.turnOff)
        assertEquals(emptySet<String>(), change.next)
    }

    @Test
    fun failedTurnOffStaysPersistedForRetry() {
        assertEquals(
            setOf("com.stay", "com.stuck"),
            persistedPackageSet(setOf("com.stay"), listOf("com.stuck")),
        )
        assertEquals(
            setOf("com.stay"),
            persistedPackageSet(setOf("com.stay"), emptyList()),
        )
    }
}
