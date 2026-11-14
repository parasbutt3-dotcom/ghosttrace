import SwiftUI

/// User-configurable backend URL + device key. Values are stored in
/// UserDefaults under `ghosttrace.baseURL` / `ghosttrace.deviceKey`, which
/// `TelemetryService` reads on every push.
struct SettingsView: View {
    @AppStorage("ghosttrace.baseURL") private var baseURL: String = "http://127.0.0.1:8000"
    @AppStorage("ghosttrace.deviceKey") private var deviceKey: String = ""
    @AppStorage("ghosttrace.motionEnabled") private var motionEnabled: Bool = true
    @AppStorage("ghosttrace.locationEnabled") private var locationEnabled: Bool = true

    var body: some View {
        NavigationStack {
            Form {
                Section("Backend") {
                    TextField("Base URL", text: $baseURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                    SecureField("Device key (gt_...)", text: $deviceKey)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }
                Section("Collection") {
                    Toggle("Location tracking", isOn: $locationEnabled)
                    Toggle("Motion activity", isOn: $motionEnabled)
                }
                Section {
                    Text("Register the device first: dashboard -> Devices -> Register iOS Device, then paste the one-time key here. Screen Time / app-usage data is not collected (Family Controls entitlement not enabled). Motion activity uses CoreMotion and is collected locally.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
        }
    }
}