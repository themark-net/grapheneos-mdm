package net.themark.grapheneosmdm.policy

/**
 * Difference between the packages this agent last hid or suspended and the
 * desired set. A null [desired] list means leave the device alone.
 * The agent package is never included.
 */
internal data class PackageSetChange(
    val assertOn: List<String>,
    val turnOff: List<String>,
    val next: Set<String>,
)

internal fun packageSetChange(
    previous: Set<String>,
    desired: List<String>?,
    selfPackage: String,
): PackageSetChange? {
    if (desired == null) return null
    val next = desired
        .map { it.trim() }
        .filter { it.isNotEmpty() && it != selfPackage }
        .toSet()
    val prev = previous.filter { it.isNotEmpty() && it != selfPackage }.toSet()
    return PackageSetChange(
        assertOn = next.sorted(),
        turnOff = (prev - next).sorted(),
        next = next,
    )
}

/**
 * Stored set after an apply. Failed turn-offs stay so the next check-in retries them.
 * Packages that turned off successfully are absent from [next] and are not kept.
 */
internal fun persistedPackageSet(next: Set<String>, failedTurnOff: Collection<String>): Set<String> =
    next + failedTurnOff
