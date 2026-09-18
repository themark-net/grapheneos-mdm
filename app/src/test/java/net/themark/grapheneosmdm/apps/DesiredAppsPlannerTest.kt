package net.themark.grapheneosmdm.apps

import net.themark.grapheneosmdm.protocol.RequiredPackage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DesiredAppsPlannerTest {

    @Test
    fun freshInstallWhenMissing() {
        val desired = listOf(
            RequiredPackage(
                packageName = "com.example.app",
                minVersionCode = 2,
                apkUrl = "/v1/catalog/app.apk",
                sha256 = "a".repeat(64),
            ),
        )
        val plan = DesiredAppsPlanner.plan(desired, installedVersionCodes = emptyMap())
        assertEquals(1, plan.size)
        val action = plan[0] as DesiredAppAction.NeedsInstall
        assertEquals(InstallKind.FRESH, action.kind)
    }

    @Test
    fun updateWhenBelowMinVersion() {
        val desired = listOf(
            RequiredPackage(
                packageName = "com.example.app",
                minVersionCode = 5,
                apkUrl = "https://mdm.example/v1/catalog/app.apk",
                sha256 = "b".repeat(64),
            ),
        )
        val plan = DesiredAppsPlanner.plan(desired, mapOf("com.example.app" to 3L))
        val action = plan[0] as DesiredAppAction.NeedsInstall
        assertEquals(InstallKind.UPDATE, action.kind)
    }

    @Test
    fun satisfiedWhenAtOrAboveMin() {
        val desired = listOf(
            RequiredPackage(packageName = "com.example.app", minVersionCode = 5),
        )
        val plan = DesiredAppsPlanner.plan(desired, mapOf("com.example.app" to 5L))
        assertTrue(plan[0] is DesiredAppAction.AlreadySatisfied)
    }

    @Test
    fun refusesDownloadWithoutSha256() {
        val desired = listOf(
            RequiredPackage(
                packageName = "com.example.app",
                apkUrl = "/v1/catalog/app.apk",
            ),
        )
        val plan = DesiredAppsPlanner.plan(desired, emptyMap())
        val action = plan[0] as DesiredAppAction.MissingArtifact
        assertTrue(action.reason.contains("sha256"))
    }
}
