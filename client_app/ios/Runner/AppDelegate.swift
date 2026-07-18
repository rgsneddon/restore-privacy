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
  /// Blocking wait so process exit does not race async `loadAllFromPreferences`.
  override func applicationWillTerminate(_ application: UIApplication) {
    _ = RptVpnChannel.stopAllTunnelsAndWait(timeout: 2.0)
    super.applicationWillTerminate(application)
  }

  /// App-switcher swipe-kill often never delivers `willTerminate` or Flutter `detached`.
  /// Stop NE on background so residual ISP IP returns when the user leaves/closes the app.
  override func applicationDidEnterBackground(_ application: UIApplication) {
    RptVpnChannel.stopAllTunnels()
    super.applicationDidEnterBackground(application)
  }
}
