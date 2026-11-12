package com.ghosttrace.companion

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

class TelemetryWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val baseUrl = inputData.getString("base_url") ?: return@withContext Result.failure()
        val deviceKey = inputData.getString("device_key") ?: return@withContext Result.failure()

        val battery = 80
        val payload = JSONObject().apply {
            put("battery_level", battery)
            put("network_type", "wifi")
            put("os_version", android.os.Build.VERSION.RELEASE)
            put("events", JSONArray())
        }

        val client = OkHttpClient()
        val req = Request.Builder()
            .url("$baseUrl/api/v1/devices/telemetry")
            .addHeader("X-Device-Key", deviceKey)
            .post(payload.toString().toRequestBody("application/json".toMediaType()))
            .build()
        client.newCall(req).execute().use { resp ->
            if (resp.isSuccessful) Result.success() else Result.retry()
        }
    }
}
