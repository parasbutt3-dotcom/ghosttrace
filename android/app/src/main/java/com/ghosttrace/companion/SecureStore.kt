package com.ghosttrace.companion

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

object SecureStore {
    private const val PREFS = "ghosttrace_secure"
    private const val KEY_DEVICE = "device_key"
    private const val KEY_BASE_URL = "base_url"
    private const val KEY_CONSENT = "consent_granted"

    private fun prefs(context: Context): android.content.SharedPreferences {
        val masterKey = MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
        return EncryptedSharedPreferences.create(
            context,
            PREFS,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    fun deviceKey(context: Context): String? = prefs(context).getString(KEY_DEVICE, null)
    fun setDeviceKey(context: Context, value: String) {
        prefs(context).edit().putString(KEY_DEVICE, value).apply()
    }

    fun baseUrl(context: Context): String? = prefs(context).getString(KEY_BASE_URL, null)
    fun setBaseUrl(context: Context, value: String) {
        prefs(context).edit().putString(KEY_BASE_URL, value).apply()
    }

    fun consentGranted(context: Context): Boolean = prefs(context).getBoolean(KEY_CONSENT, false)
    fun setConsentGranted(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_CONSENT, value).apply()
    }

    fun clear(context: Context) {
        prefs(context).edit().clear().apply()
    }
}