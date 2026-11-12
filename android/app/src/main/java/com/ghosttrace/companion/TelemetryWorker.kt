package com.ghosttrace.companion

import android.app.AppOpsManager
import android.content.Context
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.os.Process
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.Tasks
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class TelemetryWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val context = applicationContext
        val baseUrl = SecureStore.baseUrl(context) ?: inputData.getString("base_url")
        val deviceKey = SecureStore.deviceKey(context) ?: inputData.getString("device_key")
        if (baseUrl.isNullOrBlank() || deviceKey.isNullOrBlank()) return@withContext Result.failure()

        val battery = readBattery(context)
        val networkType = readNetworkType(context)
        val osVersion = Build.VERSION.RELEASE
        val appVersion = readAppVersion(context)

        val events = JSONArray()
        // Usage stats (PACKAGE_USAGE_STATS)
        if (hasUsageStatsPermission(context)) {
            readUsageEvents(context).forEach { events.put(it) }
        }
        // Location (optional, permission-gated)
        val locationJson = readLocation(context) // may be null

        val payload = JSONObject().apply {
            put("battery_level", battery)
            put("network_type", networkType)
            put("os_version", osVersion)
            put("app_version", appVersion)
            if (locationJson != null) put("location", locationJson)
            put("events", events)
        }

        return@withContext try {
            val client = OkHttpClient.Builder().connectTimeout(30, TimeUnit.SECONDS).build()
            val req = Request.Builder()
                .url("${baseUrl.trimEnd('/')}/api/v1/devices/telemetry")
                .addHeader("X-Device-Key", deviceKey)
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    TrackingNotification.show(context, "Last sync OK")
                    Result.success()
                } else {
                    Result.retry()
                }
            }
        } catch (t: Throwable) {
            Result.retry()
        }
    }

    private fun readBattery(context: Context): Int {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY).coerceIn(0, 100)
    }

    private fun readNetworkType(context: Context): String {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return "none"
        val caps = cm.getNetworkCapabilities(network) ?: return "none"
        return when {
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            else -> "unknown"
        }
    }

    private fun readAppVersion(context: Context): String {
        return try {
            val pi = context.packageManager.getPackageInfo(context.packageName, 0)
            pi.versionName ?: "1.0.0"
        } catch (e: PackageManager.NameNotFoundException) {
            "1.0.0"
        }
    }

    private fun hasUsageStatsPermission(context: Context): Boolean {
        val appOps = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            appOps.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName)
        } else {
            appOps.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName)
        }
        return mode == AppOpsManager.MODE_ALLOWED
    }

    private fun readUsageEvents(context: Context): List<JSONObject> {
        val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as android.app.usage.UsageStatsManager
        val end = System.currentTimeMillis()
        val start = end - TimeUnit.HOURS.toMillis(24)
        val stats = usm.queryUsageStats(android.app.usage.UsageStatsManager.INTERVAL_DAILY, start, end) ?: emptyList()
        val out = mutableListOf<JSONObject>()
        for (s in stats) {
            val total = s.totalTimeInForeground
            if (total <= 0) continue
            val ev = JSONObject().apply {
                put("application", s.packageName)
                put("event_type", "app.usage")
                put("category", "activity")
                put("description", "foreground usage")
                put("metadata", JSONObject().apply {
                    put("duration_sec", total / 1000)
                    put("last_used", s.lastTimeUsed)
                })
                put("collection_method", "usage_stats_manager")
                put("permission_status", "authorized")
                put("confidence", 1.0)
                put("dedup_key", "android:usage:${s.packageName}:${start / 86400000}")
            }
            out.add(ev)
        }
        return out
    }

    private fun readLocation(context: Context): JSONObject? {
        // Permission check
        val fine = context.checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarse = context.checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (!fine && !coarse) return null
        return try {
            val client = LocationServices.getFusedLocationProviderClient(context)
            val task = client.getCurrentLocation(Priority.PRIORITY_BALANCED_POWER_ACCURACY, null)
            val loc = Tasks.await(task, 10, TimeUnit.SECONDS) ?: client.lastLocation.let { Tasks.await(it, 10, TimeUnit.SECONDS) }
            if (loc != null) {
                JSONObject().apply {
                    put("lat", loc.latitude)
                    put("lon", loc.longitude)
                    put("accuracy", loc.accuracy.toDouble())
                }
            } else null
        } catch (t: Throwable) {
            null
        }
    }
}