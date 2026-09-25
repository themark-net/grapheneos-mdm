package net.themark.grapheneosmdm.provision

import android.app.admin.DevicePolicyManager

/**
 * This DPC is a device owner, not a work profile.
 * When the wizard sends no allow-list, fully managed is the only mode we offer.
 */
internal fun selectFullyManagedMode(allowed: IntArray?): Int? {
    val fully = DevicePolicyManager.PROVISIONING_MODE_FULLY_MANAGED_DEVICE
    if (allowed == null || allowed.isEmpty()) return fully
    return if (fully in allowed) fully else null
}
