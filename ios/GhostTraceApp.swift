import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gear") }
        }
    }
}

#if os(iOS)
import UIKit
import BackgroundTasks
import CoreLocation

@main
struct GhostTraceApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    let telemetry = TelemetryService()
    lazy var locationCollector = LocationCollector(telemetry: telemetry)
    lazy var calendarCollector = CalendarCollector(telemetry: telemetry)
    lazy var motionCollector = MotionActivityCollector(telemetry: telemetry)

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        telemetry.observeBattery()
        locationCollector.start()
        if #available(iOS 17.0, *) {
            calendarCollector.start { _ in self.calendarCollector.syncNow() }
        }
        motionCollector.start()
        let timer = Timer.scheduledTimer(withTimeInterval: 900, repeats: true) { [weak self] _ in
            guard let self else { return }
            if #available(iOS 17.0, *) { self.calendarCollector.syncNow() }
        }
        RunLoop.main.add(timer, forMode: .common)
        BackgroundScheduler.register(telemetry: telemetry)
        BackgroundScheduler.schedule(telemetry: telemetry)
        return true
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        BackgroundScheduler.schedule(telemetry: telemetry)
    }

    func applicationWillTerminate(_ application: UIApplication) {
        locationCollector.stop()
        motionCollector.stop()
    }
}

enum BackgroundScheduler {
    static let refreshIdentifier = "com.ghosttrace.companion.refresh"

    static func register(telemetry: TelemetryService) {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: refreshIdentifier, using: nil) { task in
            guard let refreshTask = task as? BGAppRefreshTask else { return }
            handle(refreshTask, telemetry: telemetry)
        }
    }

    private static func handle(_ task: BGAppRefreshTask, telemetry: TelemetryService) {
        task.expirationHandler = { task.setTaskCompleted(success: false) }
        // Push a heartbeat; the offline queue flushes automatically on next push.
        telemetry.push(events: [])
        schedule(telemetry: telemetry)
        // Give the network request a brief window to start before completing.
        DispatchQueue.global().asyncAfter(deadline: .now() + 2) {
            task.setTaskCompleted(success: true)
        }
    }

    static func schedule(telemetry: TelemetryService) {
        let request = BGAppRefreshTaskRequest(identifier: refreshIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)
        do {
            try BGTaskScheduler.shared.submit(request)
        } catch {
            print("Failed to schedule background refresh: \(error)")
        }
    }
}
#else
@main
struct GhostTraceApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
#endif