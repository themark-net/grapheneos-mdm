package net.themark.grapheneosmdm.provision

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ProvisioningExtrasTest {

    @Test
    fun keepsHttpsAndDropsCleartext() {
        assertEquals(
            "https://mdm.example:8443",
            normalizeProvisioningServerUrl(" https://mdm.example:8443/ "),
        )
        assertNull(normalizeProvisioningServerUrl("http://mdm.example"))
        assertNull(normalizeProvisioningServerUrl("https://"))
        assertNull(normalizeProvisioningServerUrl(null))
    }
}
