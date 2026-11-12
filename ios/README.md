# GHOSTTRACE iOS Companion

Swift companion that registers a device and pushes telemetry to the GHOSTTRACE backend.

## Files
- `TelemetryService.swift` — HTTP push + battery/network/OS collection.
- `LocationCollector.swift` — significant location changes → `location.point` events.
- `CalendarCollector.swift` — phone calendars (all accounts) → `calendar.event` events.

## Wiring (AppDelegate)
```swift
let telemetry = TelemetryService(baseUrl: "http://YOUR_HOST:8000", deviceKey: "gt_XXXX")
telemetry.observeBattery()
let location = LocationCollector(telemetry: telemetry)
let calendar = CalendarCollector(telemetry: telemetry)

func application(_ application: UIApplication, didFinishLaunchingWithOptions: ...) -> Bool {
    location.start()
    calendar.start { _ in calendar.syncNow() }
    Timer.scheduledTimer(withTimeInterval: 900, repeats: true) { _ in calendar.syncNow() }
    return true
}
```
Register the device first: dashboard → Devices → Register iOS Device, copy the one-time key.

## Info.plist keys
- `NSLocationWhenInUseUsageDescription` — "See where your day happened on your timeline."
- `NSLocationAlwaysAndWhenInUseUsageDescription` — for continuous tracking (also enable Background Modes → Location).
- `NSCalendarsFullAccessUsageDescription` — "Import your meetings into your activity timeline."

## API contract
`POST /api/v1/devices/telemetry` with `X-Device-Key` header; body validated by `TelemetryIn`
(battery 0–100, events array with `event_type`, optional `dedup_key`).

## Notes
- No stealth tracking; app must be visibly installed and authorized.
- Screen Time / app-usage data requires Apple's Family Controls entitlement — not enabled here.
- HealthKit data is never auto-collected; each type requires explicit permission.
- These files are ready-to-drop-in sources; compile in Xcode (not built in this repo's CI).