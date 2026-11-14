# GHOSTTRACE iOS Companion

Swift companion that registers a device and pushes telemetry to the GHOSTTRACE backend.

## Files
- `project.yml` — XcodeGen spec. Generate the Xcode project with `xcodegen generate`.
- `Info.plist` — bundle + permission + background-mode configuration.
- `TelemetryService.swift` — HTTP push + battery (UIDevice) + network (NWPathMonitor) + OS/app version collection. Includes offline event queue (persisted to UserDefaults, up to 500 events) and retry with exponential backoff (3 attempts).
- `LocationCollector.swift` — significant location changes → `location.point` events. Handles authorization states (notDetermined/authorized/denied) properly.
- `CalendarCollector.swift` — phone calendars (all accounts) → `calendar.event` events. Checks authorization before syncing.
- `MotionActivityCollector.swift` — CoreMotion activity transitions (walking/running/cycling/driving/stationary) → `motion.activity` events.
- `SettingsView.swift` — SwiftUI settings for base URL + device key + collection toggles.
- `GhostTraceApp.swift` — app entry point, background refresh scheduling, collector wiring, motion activity.

## Build (XcodeGen)
```sh
brew install xcodegen   # or: mint install yonaskolb/XcodeGen
cd ios
xcodegen generate
open GhostTrace.xcodeproj
```
No checked-in `.xcodeproj`; `project.yml` is the source of truth.

## Wiring (AppDelegate / SwiftUI)
The app entry point in `GhostTraceApp.swift` already wires collectors:
```swift
let telemetry = TelemetryService()   // reads base URL + device key from Settings
telemetry.observeBattery()
let location = LocationCollector(telemetry: telemetry)
let calendar = CalendarCollector(telemetry: telemetry)
let motion = MotionActivityCollector(telemetry: telemetry)
location.start()
motion.start()
// calendar permission + sync on iOS 17+
```
Register the device first: dashboard → Devices → Register iOS Device, copy the one-time key, then paste it in Settings.

## Settings
`SettingsView` stores:
- `ghosttrace.baseURL` (default `http://127.0.0.1:8000`)
- `ghosttrace.deviceKey` (the `gt_...` key from device registration)

`TelemetryService` reads both on every push, so changes take effect without restart.

## Info.plist keys
- `NSLocationWhenInUseUsageDescription` — "See where your day happened on your timeline."
- `NSLocationAlwaysAndWhenInUseUsageDescription` — for continuous tracking (also enable Background Modes → Location).
- `NSCalendarsFullAccessUsageDescription` — "Import your meetings into your activity timeline."
- `NSCalendarsUsageDescription` — fallback for pre-iOS 17.
- `UIBackgroundModes` — `fetch`, `processing`, `location`.
- `BGTaskSchedulerPermittedIdentifiers` — `com.ghosttrace.companion.refresh`.

## Background modes
Background refresh is scheduled via `BGTaskScheduler` (identifier `com.ghosttrace.companion.refresh`) for periodic telemetry pushes. Location background mode supports continuous tracking when the user grants "Always" authorization.

## API contract
`POST /api/v1/devices/telemetry` with `X-Device-Key` header; body validated by `TelemetryIn`
(battery 0–100, events array with `event_type`, optional `dedup_key`).

## Notes
- No stealth tracking; app must be visibly installed and authorized.
- Screen Time / app-usage data requires Apple's Family Controls entitlement — **not enabled here**; capability stays `false` (see backend `ios` integration).
- Motion activity (CoreMotion) is now collected → `motion.activity` events; capability set to `true`.
- HealthKit data is never auto-collected; each type requires explicit permission.
- Offline queue: failed pushes are persisted to UserDefaults and retried on the next push (up to 500 events, oldest dropped first).
- USB fallback (no app install): `tools/ios_inspector.py` (pymobiledevice3). Use `--dry-run` to print the payload without connecting.
- These files are ready-to-build sources; compile in Xcode (not built in this repo's CI beyond `swiftc -typecheck`).