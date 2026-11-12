package com.ghosttrace.companion

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {

    private val locationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { /* result handled implicitly; collection checks permissions at runtime */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val baseUrlInput = findViewById<EditText>(R.id.baseUrlInput)
        val deviceKeyInput = findViewById<EditText>(R.id.deviceKeyInput)
        val consentCheckbox = findViewById<CheckBox>(R.id.consentCheckbox)
        val saveButton = findViewById<Button>(R.id.saveButton)
        val stopButton = findViewById<Button>(R.id.stopButton)
        val statusText = findViewById<TextView>(R.id.statusText)

        // Prefill from secure store
        SecureStore.baseUrl(this)?.let { baseUrlInput.setText(it) }
        SecureStore.deviceKey(this)?.let { deviceKeyInput.setText(it) }
        consentCheckbox.isChecked = SecureStore.consentGranted(this)

        statusText.text = if (SecureStore.consentGranted(this)) "Tracking active" else "Not configured"

        saveButton.setOnClickListener {
            val baseUrl = baseUrlInput.text.toString().trim()
            val deviceKey = deviceKeyInput.text.toString().trim()
            if (baseUrl.isBlank() || deviceKey.isBlank()) {
                Toast.makeText(this, "Base URL and device key are required", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            if (!consentCheckbox.isChecked) {
                Toast.makeText(this, "Consent is required", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            SecureStore.setBaseUrl(this, baseUrl)
            SecureStore.setDeviceKey(this, deviceKey)
            SecureStore.setConsentGranted(this, true)

            requestLocationPermissionIfNeeded()
            scheduleWork(baseUrl, deviceKey)
            TrackingNotification.show(this, "Tracking active")
            statusText.text = "Tracking active"
            Toast.makeText(this, "Saved", Toast.LENGTH_SHORT).show()
        }

        stopButton.setOnClickListener {
            WorkManager.getInstance(this).cancelUniqueWork(WORK_NAME)
            TrackingNotification.cancel(this)
            SecureStore.setConsentGranted(this, false)
            statusText.text = "Tracking stopped"
            Toast.makeText(this, "Stopped", Toast.LENGTH_SHORT).show()
        }
    }

    private fun requestLocationPermissionIfNeeded() {
        val perms = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            perms.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        val needs = perms.any { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (needs) {
            locationPermissionLauncher.launch(perms.toTypedArray())
        }
    }

    private fun scheduleWork(baseUrl: String, deviceKey: String) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val request = PeriodicWorkRequestBuilder<TelemetryWorker>(15, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .setInputData(
                androidx.work.Data.Builder()
                    .putString("base_url", baseUrl)
                    .putString("device_key", deviceKey)
                    .build(),
            )
            .build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            WORK_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,
            request,
        )
    }

    companion object {
        const val WORK_NAME = "ghosttrace_telemetry"
    }
}