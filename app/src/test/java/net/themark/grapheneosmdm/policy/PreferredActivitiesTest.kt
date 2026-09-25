package net.themark.grapheneosmdm.policy

import net.themark.grapheneosmdm.protocol.PersistentPreferredActivity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PreferredActivitiesTest {

    @Test
    fun nullLeavesExistingActivitiesAlone() {
        assertNull(preferredActivityPlan(setOf("com.old"), null))
    }

    @Test
    fun emptyClearsOnlyWhatThisAgentSet() {
        val plan = preferredActivityPlan(setOf("com.old"), emptyList())!!
        assertEquals(setOf("com.old"), plan.clearPackages)
        assertTrue(plan.add.isEmpty())
        assertTrue(plan.nextPackages.isEmpty())
    }

    @Test
    fun dropsBlankEntriesAndClearsThePreviousPackage() {
        val plan = preferredActivityPlan(
            setOf("com.old"),
            listOf(
                PersistentPreferredActivity("com.browser", ".Main", "android.intent.action.VIEW"),
                PersistentPreferredActivity("", ".Main", "android.intent.action.VIEW"),
            ),
        )!!
        assertEquals(setOf("com.old", "com.browser"), plan.clearPackages)
        assertEquals(listOf("com.browser"), plan.add.map { it.packageName })
        assertEquals(setOf("com.browser"), plan.nextPackages)
    }
}
