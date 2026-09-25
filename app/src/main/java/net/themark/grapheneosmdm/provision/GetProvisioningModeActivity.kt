package net.themark.grapheneosmdm.provision

import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.Intent
import android.os.Bundle

/**
 * Answers Managed Provisioning with fully-managed mode.
 * Stock GrapheneOS SetupWizard does not launch this yet. See docs/ENROLLMENT.md.
 */
class GetProvisioningModeActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val allowed = intent
            .getIntegerArrayListExtra(DevicePolicyManager.EXTRA_PROVISIONING_ALLOWED_PROVISIONING_MODES)
            ?.map { it.toInt() }
            ?.toIntArray()
        val mode = selectFullyManagedMode(allowed)
        if (mode == null) {
            setResult(RESULT_CANCELED)
        } else {
            setResult(
                RESULT_OK,
                Intent().putExtra(DevicePolicyManager.EXTRA_PROVISIONING_MODE, mode),
            )
        }
        finish()
    }
}
