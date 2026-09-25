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

    @Test
    fun uninstallsOnlyPackagesTheAgentInstalled() {
        val plan = DesiredAppsPlanner.plan(
            desired = listOf(RequiredPackage("com.keep")),
            installedVersionCodes = mapOf(
                "com.keep" to 1L,
                "com.user.app" to 1L,
                "com.we.installed" to 2L,
            ),
            installedByAgent = setOf("com.we.installed", "com.keep"),
            selfPackage = "net.themark.grapheneosmdm",
        )
        val uninstalls = plan.filterIsInstance<DesiredAppAction.NeedsUninstall>()
        assertEquals(listOf("com.we.installed"), uninstalls.map { it.packageName })
    }

    @Test
    fun doesNotUninstallSelfEvenIfTracked() {
        val plan = DesiredAppsPlanner.plan(
            desired = emptyList(),
            installedVersionCodes = emptyMap(),
            installedByAgent = setOf("net.themark.grapheneosmdm", "com.we.installed"),
            selfPackage = "net.themark.grapheneosmdm",
        )
        assertEquals(
            listOf(DesiredAppAction.NeedsUninstall("com.we.installed")),
            plan,
        )
    }
}
