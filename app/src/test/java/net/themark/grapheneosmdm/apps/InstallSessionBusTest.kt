package net.themark.grapheneosmdm.apps

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class InstallSessionBusTest {

    @Test
    fun packageWaiterCompletes() {
        val name = "com.example.bus.${System.nanoTime()}"
        InstallSessionBus.registerPackage(name)
        Thread {
            InstallSessionBus.completePackage(
                name,
                InstallStatus(InstallStatusCode.SUCCESS),
            )
        }.start()
        val status = InstallSessionBus.awaitPackage(name, 2_000)
        assertTrue(status.isSuccess)
        assertEquals(InstallStatusCode.SUCCESS, status.code)
    }
}
