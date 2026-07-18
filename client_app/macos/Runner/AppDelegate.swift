import Cocoa
import FlutterMacOS

@main
class AppDelegate: FlutterAppDelegate {
  override func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    return true
  }

  override func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
    return true
  }

  // Product policy: closing the window / quitting the host does NOT stop the Packet Tunnel.
  // The user stops VPN only via the Flutter UI Disconnect button (method-channel "disconnect").
  // Same policy as Windows / Android Flutter shells.
}
