package net.themark.grapheneosmdm.policy

import net.themark.grapheneosmdm.protocol.PersistentPreferredActivity

internal data class PreferredActivityPlan(
    val clearPackages: Set<String>,
    val add: List<PersistentPreferredActivity>,
    val nextPackages: Set<String>,
)

/** Null [desired] means leave persistent preferred activities alone. */
internal fun preferredActivityPlan(
    previousPackages: Set<String>,
    desired: List<PersistentPreferredActivity>?,
): PreferredActivityPlan? {
    if (desired == null) return null
    val add = desired.filter {
        it.packageName.isNotBlank() && it.activity.isNotBlank() && it.action.isNotBlank()
    }
    val next = add.map { it.packageName }.toSet()
    val clear = (previousPackages + next).filter { it.isNotBlank() }.toSet()
    return PreferredActivityPlan(clearPackages = clear, add = add, nextPackages = next)
}
