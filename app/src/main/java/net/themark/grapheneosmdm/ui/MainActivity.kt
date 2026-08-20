package net.themark.grapheneosmdm.ui

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import net.themark.grapheneosmdm.R
import net.themark.grapheneosmdm.policy.PolicyManager
import net.themark.grapheneosmdm.service.MdmService
import android.content.Intent

class MainActivity : AppCompatActivity() {

    private lateinit var policyManager: PolicyManager
    private lateinit var statusText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        policyManager = PolicyManager(this)
        statusText = findViewById(R.id.statusText)

        updateStatus()

        findViewById<Button>(R.id.btnCheckIn).setOnClickListener {
            // Trigger the service
            startForegroundService(Intent(this, MdmService::class.java))
            Toast.makeText(this, "Check-in requested", Toast.LENGTH_SHORT).show()
        }

        findViewById<Button>(R.id.btnSamplePolicy).setOnClickListener {
            if (policyManager.isDeviceOwner()) {
                policyManager.applySampleRestrictions()
                Toast.makeText(this, "Sample restrictions applied", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, "Not Device Owner", Toast.LENGTH_LONG).show()
            }
        }
    }

    override fun onResume() {
        super.onResume()
        updateStatus()
    }

    private fun updateStatus() {
        statusText.text = if (policyManager.isDeviceOwner()) {
            getString(R.string.status_device_owner)
        } else {
            getString(R.string.status_not_owner)
        }
    }
}
