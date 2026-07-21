import Cocoa
import FlutterMacOS

@main
class AppDelegate: FlutterAppDelegate {
  override func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    // When menu-bar tray mode is active after full-tunnel Connect, keep process alive.
    return RptTrayController.shouldTerminateAfterLastWindowClosed
  }

  override func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
    return true
  }

  // Product policy: closing the window / quitting the host does NOT stop the Packet Tunnel.
  // The user stops VPN only via the Flutter UI Disconnect button (method-channel "disconnect")
  // or the tray "Disconnect" item (invokes Flutter). Same policy as Windows tray.
}
