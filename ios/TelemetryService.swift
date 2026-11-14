import Foundation
#if canImport(UIKit)
import UIKit
#endif
#if canImport(Network)
import Network
#endif

/// Pushes device telemetry + collected events to the GHOSTTRACE backend.
/// Register the device in the dashboard first (Devices page), then store the
/// one-time device key in Settings (or pass it to `init`).
///
/// Features:
/// - Offline queue: events that fail to send are persisted to disk and retried
///   on the next push (up to 500 queued events, oldest dropped first).
/// - Retry with exponential backoff (3 attempts: 1s, 2s, 4s).
/// - Battery/network/OS collection with proper availability checks.
final class TelemetryService {
    private let defaults = UserDefaults.standard
    private let baseUrlKey = "ghosttrace.baseURL"
    private let deviceKeyKey = "ghosttrace.deviceKey"
    private let queueKey = "ghosttrace.offlineQueue"

    private let fallbackBaseUrl: String
    private let fallbackDeviceKey: String

    private var batteryLevel: Int? = nil
    #if canImport(Network)
    private let monitor = NWPathMonitor()
    private var networkType: String? = nil
    #endif

    private let session = URLSession.shared
    private let queue = DispatchQueue(label: "com.ghosttrace.telemetry", qos: .utility)
    private let maxQueuedEvents = 500
    private let maxRetries = 3

    init(baseUrl: String = "http://127.0.0.1:8000", deviceKey: String = "") {
        self.fallbackBaseUrl = baseUrl
        self.fallbackDeviceKey = deviceKey
        if defaults.string(forKey: baseUrlKey) == nil {
            defaults.set(baseUrl, forKey: baseUrlKey)
        }
        if !deviceKey.isEmpty && defaults.string(forKey: deviceKeyKey) == nil {
            defaults.set(deviceKey, forKey: deviceKeyKey)
        }
        #if canImport(Network)
        monitor.pathUpdateHandler = { [weak self] path in
            guard let self else { return }
            self.networkType = path.usesInterfaceType(.wifi) ? "wifi"
                : path.usesInterfaceType(.cellular) ? "cellular" : "other"
        }
        monitor.start(queue: DispatchQueue.global(qos: .utility))
        #endif
    }

    var baseUrl: String {
        let value = defaults.string(forKey: baseUrlKey)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return value.isEmpty ? fallbackBaseUrl : value
    }

    var deviceKey: String {
        let value = defaults.string(forKey: deviceKeyKey)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return value.isEmpty ? fallbackDeviceKey : value
    }

    #if canImport(UIKit)
    func observeBattery() {
        UIDevice.current.isBatteryMonitoringEnabled = true
        updateBatteryLevel()
        NotificationCenter.default.addObserver(forName: UIDevice.batteryLevelDidChangeNotification,
                                               object: nil, queue: .main) { [weak self] _ in
            self?.updateBatteryLevel()
        }
        NotificationCenter.default.addObserver(forName: UIDevice.batteryStateDidChangeNotification,
                                               object: nil, queue: .main) { [weak self] _ in
            self?.updateBatteryLevel()
        }
    }

    private func updateBatteryLevel() {
        let level = UIDevice.current.batteryLevel
        if level >= 0 {
            batteryLevel = Int(level * 100)
        }
    }
    #endif

    /// Push events to the backend. Failed sends are queued for retry.
    func push(events: [[String: Any]]) {
        queue.async { [weak self] in
            guard let self else { return }
            self.flushQueue()
            if !events.isEmpty {
                self.sendWithRetry(events: events, attempt: 0)
            }
        }
    }

    // MARK: - Private

    private func buildPayload(events: [[String: Any]]) -> [String: Any] {
        var payload: [String: Any] = ["events": events]
        if let batteryLevel { payload["battery_level"] = batteryLevel }
        #if canImport(Network)
        if let networkType { payload["network_type"] = networkType }
        #endif
        #if canImport(UIKit)
        payload["os_version"] = UIDevice.current.systemVersion
        payload["app_version"] = (Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String) ?? "unknown"
        #endif
        return payload
    }

    private func sendWithRetry(events: [[String: Any]], attempt: Int) {
        let key = deviceKey
        let base = baseUrl
        guard !key.isEmpty, !base.isEmpty,
              let url = URL(string: "\(base)/api/v1/devices/telemetry") else {
            enqueue(events)
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(key, forHTTPHeaderField: "X-Device-Key")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: buildPayload(events: events))

        let semaphore = DispatchSemaphore(value: 0)
        var success = false
        var shouldRetry = false

        session.dataTask(with: request) { _, response, error in
            if let error {
                print("Telemetry error: \(error)")
                shouldRetry = true
            } else if let http = response as? HTTPURLResponse {
                if (200...299).contains(http.statusCode) {
                    success = true
                } else if http.statusCode >= 500 || http.statusCode == 429 {
                    shouldRetry = true
                    print("Telemetry HTTP \(http.statusCode)")
                } else {
                    print("Telemetry HTTP \(http.statusCode) (not retryable)")
                }
            }
            semaphore.signal()
        }.resume()

        semaphore.wait()

        if success {
            return
        }
        if shouldRetry && attempt < maxRetries - 1 {
            let delay = pow(2.0, Double(attempt))
            Thread.sleep(forTimeInterval: delay)
            sendWithRetry(events: events, attempt: attempt + 1)
        } else {
            enqueue(events)
        }
    }

    // MARK: - Offline queue

    private func enqueue(_ events: [[String: Any]]) {
        var queue = loadQueue()
        queue.append(contentsOf: events)
        if queue.count > maxQueuedEvents {
            queue = Array(queue.suffix(maxQueuedEvents))
        }
        saveQueue(queue)
    }

    private func flushQueue() {
        let queued = loadQueue()
        guard !queued.isEmpty else { return }
        saveQueue([])
        sendWithRetry(events: queued, attempt: 0)
    }

    private func loadQueue() -> [[String: Any]] {
        guard let data = defaults.data(forKey: queueKey),
              let arr = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            return []
        }
        return arr
    }

    private func saveQueue(_ events: [[String: Any]]) {
        if events.isEmpty {
            defaults.removeObject(forKey: queueKey)
            return
        }
        if let data = try? JSONSerialization.data(withJSONObject: events) {
            defaults.set(data, forKey: queueKey)
        }
    }
}