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

  /// Dock icon click / Cmd-Tab reopen while windows are hidden, ordered-out, or miniaturized.
  /// Restores the main Flutter window without disconnecting Packet Tunnel.
  override func applicationShouldHandleReopen(
    _ sender: NSApplication,
    hasVisibleWindows flag: Bool
  ) -> Bool {
    // Always restore when tray keep-alive is on, or when no visible windows (hide/minimize).
    if RptTrayController.isTrayMode || !flag {
      RptTrayController.showMainWindow()
      RptTrayController.requestFlutterShow()
      // We presented the window ourselves.
      return false
    }
    return true
  }

  // Product policy: closing the window / quitting the host does NOT stop the Packet Tunnel.
  // The user stops VPN only via the Flutter UI Disconnect button (method-channel "disconnect")
  // or the tray "Disconnect" item (invokes Flutter). Same policy as Windows tray.
}
