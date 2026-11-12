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
final class TelemetryService {
    private let defaults = UserDefaults.standard
    private let baseUrlKey = "ghosttrace.baseURL"
    private let deviceKeyKey = "ghosttrace.deviceKey"

    private let fallbackBaseUrl: String
    private let fallbackDeviceKey: String

    private var batteryLevel: Int? = nil
    #if canImport(Network)
    private let monitor = NWPathMonitor()
    private var networkType: String? = nil
    #endif

    private let session = URLSession.shared

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

    func push(events: [[String: Any]]) {
        let key = deviceKey
        let base = baseUrl
        guard !key.isEmpty, !base.isEmpty,
              let url = URL(string: "\(base)/api/v1/devices/telemetry") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(key, forHTTPHeaderField: "X-Device-Key")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var payload: [String: Any] = ["events": events]
        if let batteryLevel { payload["battery_level"] = batteryLevel }
        #if canImport(Network)
        if let networkType { payload["network_type"] = networkType }
        #endif
        #if canImport(UIKit)
        payload["os_version"] = UIDevice.current.systemVersion
        payload["app_version"] = (Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String) ?? "unknown"
        #endif

        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        session.dataTask(with: request) { _, response, error in
            if let error { print("Telemetry error: \(error)") }
            if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
                print("Telemetry HTTP \(http.statusCode)")
            }
        }.resume()
    }
}