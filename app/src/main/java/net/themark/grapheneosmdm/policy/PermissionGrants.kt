package net.themark.grapheneosmdm.policy

import android.app.admin.DevicePolicyManager
import net.themark.grapheneosmdm.protocol.PermissionGrant

internal data class PermissionApply(
    val packageName: String,
    val permission: String,
    val grantState: Int,
)

/**
 * Difference between permission overrides this agent last applied and the
 * desired list. A null [desired] list means leave the device alone.
 * The agent package is never included. Unknown states are skipped.
 * [turnOff] entries are reset to the platform default.
 */
internal data class PermissionGrantChange(
    val assertOn: List<PermissionApply>,
    val turnOff: List<PermissionApply>,
    val next: Set<String>,
)

internal fun permissionKey(packageName: String, permission: String): String =
    "$packageName\u0000$permission"

internal fun permissionGrantConstant(state: String?): Int? = when (state?.trim()?.lowercase()) {
    "granted" -> DevicePolicyManager.PERMISSION_GRANT_STATE_GRANTED
    "denied" -> DevicePolicyManager.PERMISSION_GRANT_STATE_DENIED
    "default" -> DevicePolicyManager.PERMISSION_GRANT_STATE_DEFAULT
    else -> null
}

internal fun permissionGrantChange(
    previous: Set<String>,
    desired: List<PermissionGrant>?,
    selfPackage: String,
): PermissionGrantChange? {
    if (desired == null) return null
    val byKey = linkedMapOf<String, PermissionApply>()
    for (spec in desired) {
        val pkg = spec.packageName.trim()
        val perm = spec.permission.trim()
        if (pkg.isEmpty() || perm.isEmpty() || pkg == selfPackage) continue
        val state = permissionGrantConstant(spec.state) ?: continue
        byKey[permissionKey(pkg, perm)] = PermissionApply(pkg, perm, state)
    }
    val turnOff = previous.mapNotNull { key ->
        val parts = key.split('\u0000', limit = 2)
        if (parts.size != 2) return@mapNotNull null
        val pkg = parts[0]
        val perm = parts[1]
        if (pkg.isEmpty() || perm.isEmpty() || pkg == selfPackage || key in byKey) {
            null
        } else {
            PermissionApply(pkg, perm, DevicePolicyManager.PERMISSION_GRANT_STATE_DEFAULT)
        }
    }.sortedWith(compareBy({ it.packageName }, { it.permission }))
    val assertOn = byKey.values.sortedWith(compareBy({ it.packageName }, { it.permission }))
    return PermissionGrantChange(
        assertOn = assertOn,
        turnOff = turnOff,
        next = byKey.keys.toSet(),
    )
}
