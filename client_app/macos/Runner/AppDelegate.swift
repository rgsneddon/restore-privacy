import Cocoa
import FlutterMacOS
import NetworkExtension

@main
class AppDelegate: FlutterAppDelegate {
  override func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    return true
  }

  override func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
    return true
  }

  /// Stop Packet Tunnel before quit so residual ISP IP returns when the UI closes.
  /// Uses the same stop path as method-channel `disconnect`.
  override func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
    RptVpnChannel.stopAllTunnels { _ in
      DispatchQueue.main.async {
        NSApp.reply(toApplicationShouldTerminate: true)
      }
    }
    return .terminateLater
  }

  override func applicationWillTerminate(_ notification: Notification) {
    // Best-effort if ShouldTerminate path was skipped (e.g. force paths).
    RptVpnChannel.stopAllTunnels()
  }
}
