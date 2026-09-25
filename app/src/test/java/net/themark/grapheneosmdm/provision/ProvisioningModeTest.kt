package net.themark.grapheneosmdm.provision

import android.app.admin.DevicePolicyManager
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ProvisioningModeTest {

    @Test
    fun offersFullyManagedWhenTheWizardDoesNotConstrainModes() {
        val fully = DevicePolicyManager.PROVISIONING_MODE_FULLY_MANAGED_DEVICE
        assertEquals(fully, selectFullyManagedMode(null))
        assertEquals(fully, selectFullyManagedMode(intArrayOf()))
    }

    @Test
    fun refusesAProfileOnlyAllowList() {
        val profile = DevicePolicyManager.PROVISIONING_MODE_MANAGED_PROFILE
        val fully = DevicePolicyManager.PROVISIONING_MODE_FULLY_MANAGED_DEVICE
        assertNull(selectFullyManagedMode(intArrayOf(profile)))
        assertEquals(fully, selectFullyManagedMode(intArrayOf(profile, fully)))
    }
}
