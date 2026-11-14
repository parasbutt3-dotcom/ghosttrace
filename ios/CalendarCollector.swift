import Foundation
import EventKit

/// Reads the phone's own calendars (all accounts — Google, iCloud, Exchange)
/// and pushes today's + next-24h events to GHOSTTRACE as `calendar.event`.
/// Requires NSCalendarsFullAccessUsageDescription in Info.plist.
final class CalendarCollector {
    private let store = EKEventStore()
    private let telemetry: TelemetryService
    private var isAuthorized = false

    init(telemetry: TelemetryService) {
        self.telemetry = telemetry
    }

    @available(iOS 17.0, macOS 14.0, *)
    func start(completion: ((Bool) -> Void)? = nil) {
        store.requestFullAccessToEvents { [weak self] granted, error in
            DispatchQueue.main.async {
                self?.isAuthorized = granted
                if let error { print("Calendar access error: \(error.localizedDescription)") }
                completion?(granted)
            }
        }
    }

    func syncNow() {
        guard isAuthorized else {
            print("Calendar access not granted — skipping sync")
            return
        }
        let now = Date()
        guard let to = Calendar.current.date(byAdding: .hour, value: 24, to: now) else { return }
        let predicate = store.predicateForEvents(withStart: now, end: to, calendars: nil)
        let events = store.events(matching: predicate)
        let payload: [[String: Any]] = events.map { ev in
            let fmt = ISO8601DateFormatter()
            return [
                "application": ev.calendar.title ?? "Calendar",
                "event_type": "calendar.event",
                "category": "calendar",
                "timestamp": fmt.string(from: ev.startDate),
                "description": "Event: \(ev.title ?? "Untitled")",
                "metadata": [
                    "title": ev.title ?? "",
                    "start": fmt.string(from: ev.startDate),
                    "end": fmt.string(from: ev.endDate),
                    "location": ev.location ?? NSNull(),
                    "calendar": ev.calendar.title ?? "",
                    "source": "ios_companion",
                ],
                "dedup_key": "ios:cal:\(ev.eventIdentifier ?? UUID().uuidString)",
            ]
        }
        if !payload.isEmpty { telemetry.push(events: payload) }
    }
}