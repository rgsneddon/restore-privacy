import Cocoa
import FlutterMacOS

class MainFlutterWindow: NSWindow {
  override func awakeFromNib() {
    let flutterViewController = FlutterViewController()
    let windowFrame = self.frame
    self.contentViewController = flutterViewController
    self.setFrame(windowFrame, display: true)

    RegisterGeneratedPlugins(registry: flutterViewController)
    // restore_privacy/vpn method channel (connect / disconnect)
    RptVpnChannel.register(with: flutterViewController.engine.binaryMessenger)
    // restore_privacy/window — hide to menu bar tray after product full-tunnel success
    RptTrayController.register(with: flutterViewController.engine.binaryMessenger)

    super.awakeFromNib()
  }

  /// Close button hides to tray when residual session is active (tray mode), else closes.
  override func close() {
    if !RptTrayController.shouldTerminateAfterLastWindowClosed {
      // Tray mode: hide without destroying the window / process.
      // Use orderOut (not miniaturize) so showMainWindow can orderFront cleanly.
      orderOut(nil)
      NSApp.hide(nil)
      return
    }
    super.close()
  }

  /// Yellow minimize: still keep process; tray/dock Show must deminiaturize (see RptTrayController).
  override func miniaturize(_ sender: Any?) {
    super.miniaturize(sender)
    // Ensure status item exists so user can restore if dock behavior is unclear.
    // Does not stop Packet Tunnel.
  }
}
