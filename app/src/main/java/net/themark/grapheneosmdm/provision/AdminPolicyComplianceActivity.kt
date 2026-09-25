package net.themark.grapheneosmdm.provision

import android.app.Activity
import android.os.Bundle

/**
 * Tells Managed Provisioning that device-owner policy is in place.
 * There is nothing further to block on; check-in starts from the admin receiver.
 */
class AdminPolicyComplianceActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setResult(RESULT_OK)
        finish()
    }
}
