import Foundation
#if canImport(CoreMotion)
import CoreMotion
#endif

/// Collects motion-activity transitions (walking, running, cycling, driving,
/// stationary) via CoreMotion and pushes them as `motion.activity` events.
/// Requires `NSMotionUsageDescription` in Info.plist.
/// Note: CoreMotion activity data is not the same as Screen Time / app usage
/// (which requires the Family Controls entitlement — not enabled here).
final class MotionActivityCollector {
    #if canImport(CoreMotion)
    private let manager = CMMotionActivityManager()
    #endif
    private let telemetry: TelemetryService
    private var lastActivity: String? = nil
    private let minInterval: TimeInterval = 60 // 1 min between pushes

    init(telemetry: TelemetryService) {
        self.telemetry = telemetry
    }

    func start() {
        #if canImport(CoreMotion)
        guard CMMotionActivityManager.isActivityAvailable() else {
            print("Motion activity not available on this device")
            return
        }
        manager.startActivityUpdates(to: .main) { [weak self] activity in
            guard let self, let activity else { return }
            self.handle(activity)
        }
        #endif
    }

    func stop() {
        #if canImport(CoreMotion)
        manager.stopActivityUpdates()
        #endif
    }

    #if canImport(CoreMotion)
    private func handle(_ activity: CMMotionActivity) {
        let type: String
        if activity.walking { type = "walking" }
        else if activity.running { type = "running" }
        else if activity.cycling { type = "cycling" }
        else if activity.automotive { type = "driving" }
        else if activity.stationary { type = "stationary" }
        else { type = "unknown" }

        guard type != lastActivity else { return }
        lastActivity = type

        let event: [String: Any] = [
            "application": "iOS Motion",
            "event_type": "motion.activity",
            "category": "activity",
            "timestamp": ISO8601DateFormatter().string(from: activity.startDate),
            "description": "Activity changed to \(type)",
            "metadata": [
                "activity_type": type,
                "confidence": activity.confidence.rawValue,
                "start_date": ISO8601DateFormatter().string(from: activity.startDate),
                "source": "ios_companion",
            ],
            "dedup_key": "ios:motion:\(Int(activity.startDate.timeIntervalSince1970 / 60))",
        ]
        telemetry.push(events: [event])
    }
    #endif
}