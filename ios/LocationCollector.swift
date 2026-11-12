import Foundation
import CoreLocation

/// Streams significant location changes + periodic full fixes to GHOSTTRACE
/// as `location.point` events. Requires NSLocationWhenInUseUsageDescription
/// (and NSLocationAlwaysAndWhenInUseUsageDescription + background mode "location"
/// for continuous tracking) in Info.plist.
final class LocationCollector: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private let telemetry: TelemetryService
    private var lastReport: Date? = nil
    private let minInterval: TimeInterval = 300 // 5 min between pushes

    init(telemetry: TelemetryService) {
        self.telemetry = telemetry
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        manager.activityType = .otherNavigation
    }

    func start() {
        manager.requestWhenInUseAuthorization()
        manager.startMonitoringSignificantLocationChanges()
    }

    private func emit(_ location: CLLocation, label: String) {
        let now = Date()
        if let last = lastReport, now.timeIntervalSince(last) < minInterval { return }
        lastReport = now
        let event: [String: Any] = [
            "application": "iOS Location",
            "event_type": "location.point",
            "category": "location",
            "timestamp": ISO8601DateFormatter().string(from: now),
            "description": "\(label) \(location.coordinate.latitude), \(location.coordinate.longitude)",
            "metadata": [
                "latitude": location.coordinate.latitude,
                "longitude": location.coordinate.longitude,
                "accuracy_m": location.horizontalAccuracy,
                "speed_mps": location.speed >= 0 ? location.speed : NSNull(),
                "source": "ios_companion",
            ],
            "dedup_key": "ios:loc:\(Int(now.timeIntervalSince1970 / 60))",
        ]
        telemetry.push(events: [event])
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        if let loc = locations.last { emit(loc, label: "Position") }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        if manager.authorizationStatus == .authorizedAlways || manager.authorizationStatus == .authorizedWhenInUse {
            manager.startUpdatingLocation()
        }
    }
}