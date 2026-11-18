import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
    // Nhiệt độ máy (bộ điều tốc hiệu năng) + thông tin máy (báo cáo benchmark); thang nhiệt quy về thang Android
    guard let registrar = engineBridge.pluginRegistry.registrar(forPlugin: "AdasDevice") else { return }
    let channel = FlutterMethodChannel(name: "vn.adas/device", binaryMessenger: registrar.messenger())
    channel.setMethodCallHandler { call, result in
      switch call.method {
      case "thermal":
        let status: Int
        switch ProcessInfo.processInfo.thermalState {
        case .nominal: status = 0
        case .fair: status = 1
        case .serious: status = 3
        case .critical: status = 4
        @unknown default: status = -1
        }
        result(["status": status])
      case "info":
        var sys = utsname()
        uname(&sys)
        let machine = withUnsafePointer(to: &sys.machine) {
          $0.withMemoryRebound(to: CChar.self, capacity: 1) { String(cString: $0) }
        }
        result([
          "model": "Apple \(machine)",
          "soc": machine,
          "os": "iOS \(UIDevice.current.systemVersion)",
          "cores": ProcessInfo.processInfo.activeProcessorCount,
          "ram_mb": Int(ProcessInfo.processInfo.physicalMemory / 1_048_576),
        ])
      default:
        result(FlutterMethodNotImplemented)
      }
    }
  }
}
