import Foundation
#if canImport(UIKit)
import UIKit
#endif
#if canImport(Network)
import Network
#endif

/// Pushes device telemetry + collected events to the GHOSTTRACE backend.
/// Register the device in the dashboard first (Devices page), then pass the
/// one-time device key into `init`.
final class TelemetryService {
    let baseUrl: String
    let deviceKey: String
    private let session = URLSession.shared
    private var batteryLevel: Int? = nil
    #if canImport(Network)
    private let monitor = NWPathMonitor()
    private var networkType: String? = nil
    #endif

    init(baseUrl: String, deviceKey: String) {
        self.baseUrl = baseUrl
        self.deviceKey = deviceKey
        #if canImport(Network)
        monitor.pathUpdateHandler = { [weak self] path in
            guard let self else { return }
            self.networkType = path.usesInterfaceType(.wifi) ? "wifi"
                : path.usesInterfaceType(.cellular) ? "cellular" : "other"
        }
        monitor.start(queue: DispatchQueue.global(qos: .utility))
        #endif
    }

    #if canImport(UIKit)
    func observeBattery() {
        UIDevice.current.isBatteryMonitoringEnabled = true
        batteryLevel = Int(UIDevice.current.batteryLevel * 100)
        NotificationCenter.default.addObserver(forName: UIDevice.batteryLevelDidChangeNotification,
                                               object: nil, queue: .main) { [weak self] _ in
            guard let self, UIDevice.current.batteryLevel >= 0 else { return }
            self.batteryLevel = Int(UIDevice.current.batteryLevel * 100)
        }
    }
    #endif

    func push(events: [[String: Any]]) {
        guard let url = URL(string: "\(baseUrl)/api/v1/devices/telemetry") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(deviceKey, forHTTPHeaderField: "X-Device-Key")
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