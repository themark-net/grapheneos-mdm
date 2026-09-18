package net.themark.grapheneosmdm.apps

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class InstallRetryPolicyTest {

    @Test
    fun retriesTransientFailuresOnly() {
        assertTrue(InstallRetryPolicy.shouldRetry(InstallStatusCode.FAILURE))
        assertTrue(InstallRetryPolicy.shouldRetry(InstallStatusCode.FAILURE_STORAGE))
        assertTrue(InstallRetryPolicy.shouldRetry(InstallStatusCode.FAILURE_TIMEOUT))
        assertFalse(InstallRetryPolicy.shouldRetry(InstallStatusCode.SUCCESS))
        assertFalse(InstallRetryPolicy.shouldRetry(InstallStatusCode.FAILURE_CONFLICT))
        assertFalse(InstallRetryPolicy.shouldRetry(InstallStatusCode.FAILURE_ABORTED))
        assertFalse(InstallRetryPolicy.shouldRetry(InstallStatusCode.PENDING_USER_ACTION))
    }

    @Test
    fun backoffIncreases() {
        assertEquals(750L, InstallRetryPolicy.backoffMs(0))
        assertEquals(1500L, InstallRetryPolicy.backoffMs(1))
        assertEquals(3000L, InstallRetryPolicy.backoffMs(2))
    }

    @Test
    fun mapsPackageInstallerCodes() {
        // android.content.pm.PackageInstaller status constants (AOSP values)
        assertEquals(InstallStatusCode.SUCCESS, InstallStatusMapper.fromPackageInstallerExtra(0))
        assertEquals(InstallStatusCode.FAILURE, InstallStatusMapper.fromPackageInstallerExtra(1))
        assertEquals(InstallStatusCode.FAILURE_STORAGE, InstallStatusMapper.fromPackageInstallerExtra(6))
        assertEquals(InstallStatusCode.PENDING_USER_ACTION, InstallStatusMapper.fromPackageInstallerExtra(-1))
    }
}
