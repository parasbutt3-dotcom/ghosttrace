# GHOSTTRACE Android Companion (optional)

Minimal companion app that registers a device and pushes telemetry to the GHOSTTRACE backend.

## API contract

1. Register device (from backend dashboard) -> returns `device_key` (shown once).
2. Store `device_key` in the app (Android Keystore recommended).
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
    {"application": "Chrome", "event_type": "app.usage", "description": "browsing", "metadata": {"duration_sec": 120}}
  ]
}
```

## Required Android permissions

- `PACKAGE_USAGE_STATS` (user must grant in Settings -> Usage access) for app usage stats.
- `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION` for location (optional, explicit consent).
- `BATTERY_STATS` not required; battery via `BatteryManager`.

## Notes

- No stealth tracking. The app must be visibly installed and authorized by the user.
- Do not collect passwords or session cookies.
- Location is only reported if the user grants permission.

## Build

This directory contains a reference Kotlin snippet. A full Gradle project can be generated with Android Studio using the snippet in `TelemetryWorker.kt`.
