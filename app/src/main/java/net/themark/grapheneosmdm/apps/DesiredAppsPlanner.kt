package net.themark.grapheneosmdm.apps

import net.themark.grapheneosmdm.protocol.RequiredPackage

/**
 * Pure planner: given desired packages + installed version codes, decide actions.
 * Enforced on every check-in (issue #4).
 */
sealed class DesiredAppAction {
    data class AlreadySatisfied(val packageName: String) : DesiredAppAction()
    data class NeedsInstall(
        val required: RequiredPackage,
        val kind: InstallKind,
    ) : DesiredAppAction()
    data class MissingArtifact(
        val packageName: String,
        val reason: String,
    ) : DesiredAppAction()
}

object DesiredAppsPlanner {
    fun plan(
        desired: List<RequiredPackage>,
        installedVersionCodes: Map<String, Long>,
    ): List<DesiredAppAction> {
        return desired.map { req ->
            val current = installedVersionCodes[req.packageName]
            val satisfied = when {
                current == null -> false
                req.minVersionCode != null -> current >= req.minVersionCode
                else -> true // present and no minVersionCode -> satisfied
            }
            if (satisfied) {
                DesiredAppAction.AlreadySatisfied(req.packageName)
            } else {
                val kind = if (current == null) InstallKind.FRESH else InstallKind.UPDATE
                if (req.apkUrl.isNullOrBlank()) {
                    DesiredAppAction.MissingArtifact(
                        req.packageName,
                        reason = "no apkUrl in desired-state / catalog entry",
                    )
                } else if (req.sha256.isNullOrBlank()) {
                    DesiredAppAction.MissingArtifact(
                        req.packageName,
                        reason = "apkUrl present but sha256 missing - refuse download",
                    )
                } else {
                    DesiredAppAction.NeedsInstall(req, kind)
                }
            }
        }
    }
}
