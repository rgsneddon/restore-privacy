import Flutter
import UIKit
import NetworkExtension

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
    // restore_privacy/vpn method channel (connect / disconnect)
    RptVpnChannel.register(with: engineBridge.applicationRegistrar.messenger())
  }

  /// App is closing — stop Packet Tunnel so residual public IP is restored.
  /// Same stop path as method-channel `disconnect` (`stopAllTunnels` → `stopVPNTunnel`).
  override func applicationWillTerminate(_ application: UIApplication) {
    RptVpnChannel.stopAllTunnels()
    super.applicationWillTerminate(application)
  }
}
