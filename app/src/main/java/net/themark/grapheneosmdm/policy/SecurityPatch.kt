package net.themark.grapheneosmdm.policy

/** GrapheneOS / AOSP security patch strings are `YYYY-MM-DD`. */
internal val SECURITY_PATCH_DATE = Regex("""\d{4}-\d{2}-\d{2}""")

/**
 * Whether [devicePatch] meets [minPatch].
 * A missing or malformed floor counts as compliant (nothing to enforce).
 * A malformed device patch fails a well-formed floor. Equal dates pass.
 */
internal fun securityPatchCompliant(devicePatch: String, minPatch: String?): Boolean {
    if (minPatch.isNullOrBlank() || !SECURITY_PATCH_DATE.matches(minPatch)) return true
    if (!SECURITY_PATCH_DATE.matches(devicePatch)) return false
    return devicePatch >= minPatch
}
