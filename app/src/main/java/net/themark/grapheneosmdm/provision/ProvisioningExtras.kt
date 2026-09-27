package net.themark.grapheneosmdm.provision

import android.content.Context
import android.content.Intent
import android.os.PersistableBundle
import android.util.Log
import net.themark.grapheneosmdm.security.SecureConfigStore
import net.themark.grapheneosmdm.service.CheckInScheduler

internal const val PROVISIONING_SERVER_URL = "serverBaseUrl"

/** https URL from the QR extras, or null when the value is missing or not https. */
internal fun normalizeProvisioningServerUrl(raw: String?): String? {
    val url = raw?.trim()?.trimEnd('/') ?: return null
    if (!url.startsWith("https://") || url.length <= "https://".length) return null
    return url
}

/**
 * Persist the check-in URL carried in the provisioning QR and start a check-in.
 * Safe to call from every provisioning activity; a missing extra is a no-op.
 */
fun applyProvisioningExtras(context: Context, intent: Intent?) {
    val raw = readServerUrl(intent) ?: return
    val url = normalizeProvisioningServerUrl(raw) ?: run {
        Log.w(TAG, "ignoring provisioning server URL")
        return
    }
    SecureConfigStore.create(context).serverBaseUrl = url
    Log.i(TAG, "provisioning set server base URL")
    CheckInScheduler.ensureScheduled(context)
    CheckInScheduler.enqueueImmediate(context, reason = "qr_provision")
}

private fun readServerUrl(intent: Intent?): String? {
    if (intent == null) return null
    @Suppress("DEPRECATION")
    val extras = intent.getParcelableExtra<PersistableBundle>(
        android.app.admin.DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE,
    )
    return extras?.getString(PROVISIONING_SERVER_URL)
}

private const val TAG = "ProvisioningExtras"
