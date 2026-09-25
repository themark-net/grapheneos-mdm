package net.themark.grapheneosmdm.policy

import android.app.admin.DevicePolicyManager

/**
 * Maps a desired-state passwordComplexity string to [DevicePolicyManager].
 * Null or blank leaves the device alone. "none" clears the requirement.
 * Unrecognized values return null so the caller can log and skip them.
 */
internal fun passwordComplexityConstant(raw: String?): Int? = when (raw?.trim()?.lowercase()) {
    null, "" -> null
    "none" -> DevicePolicyManager.PASSWORD_COMPLEXITY_NONE
    "low" -> DevicePolicyManager.PASSWORD_COMPLEXITY_LOW
    "medium" -> DevicePolicyManager.PASSWORD_COMPLEXITY_MEDIUM
    "high" -> DevicePolicyManager.PASSWORD_COMPLEXITY_HIGH
    else -> null
}

/** Null leaves the lock timeout alone. 0 clears it. Negative values are ignored. */
internal fun maximumTimeToLockMs(raw: Long?): Long? = when {
    raw == null || raw < 0L -> null
    else -> raw
}
