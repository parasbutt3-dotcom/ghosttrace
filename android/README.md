# GHOSTTRACE Android Companion

Optional companion app that registers a device and pushes telemetry to the GHOSTTRACE backend.

## API contract

1. Register device (from backend dashboard) -> returns `device_key` (shown once).
2. Store `device_key` in the app (Android Keystore-backed `EncryptedSharedPreferences`).
3. Push telemetry:

```
POST /api/v1/devices/telemetry
Header: X-Device-Key: <device_key>
Content-Type: application/json

{
  "battery_level": 85,
  "network_type": "wifi",
  "os_version": "14",
  "app_version": "1.0.0",
  "location": {"lat": 0.0, "lon": 0.0, "accuracy": 10},
  "events": [
    {"application": "com.example.app", "event_type": "app.usage", "description": "foreground usage", "metadata": {"duration_sec": 120}}
  ]
}
```

## Collected data

- Battery level via `BatteryManager`.
- Network type via `ConnectivityManager`.
- OS version (`Build.VERSION.RELEASE`) and app version.
- App usage statistics via `UsageStatsManager` (requires `PACKAGE_USAGE_STATS` grant) -> `app.usage` events.
- Optional location via Fused Location Provider, only when permission granted and consent given.

## Required Android permissions

- `INTERNET`, `ACCESS_NETWORK_STATE`
- `PACKAGE_USAGE_STATS` (user must grant in Settings -> Apps -> Special access -> Usage access) for app usage stats.
- `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION` for location (optional, explicit consent).
- `POST_NOTIFICATIONS` (Android 13+) for the tracking notification.

`BATTERY_STATS` is not required; battery is read via `BatteryManager`.

## Privacy / no-stealth rule

- The app is visibly installed and authorized by the user.
- A persistent "GHOSTTRACE tracking active" notification is shown while tracking is enabled.
- No passwords or session cookies are collected.
- Location is reported only if the user grants permission and consents.
- `device_key` is stored in `EncryptedSharedPreferences` (Android Keystore-backed), never in plaintext.

## First-run consent

On first launch `MainActivity` shows a consent screen. The user must enter the backend base URL and device key, check the consent box, and tap "Save & Start Tracking". Tracking and the periodic WorkManager job are not scheduled until consent is granted. "Stop Tracking" cancels the job and removes the notification.

## Build

This is a full Gradle project. From `android/`:

```
./gradlew assembleDebug
```

Requirements: JDK 17, Android SDK 34 (compileSdk). The wrapper downloads Gradle 8.9. No Android SDK is required to inspect the sources; building requires a local SDK (set `ANDROID_HOME` / `sdk.dir` in `local.properties`).

## CI

`assembleDebug` is intended to run on an ubuntu runner with the Android SDK installed (Phase 2.6). APKs can be attached to releases.
