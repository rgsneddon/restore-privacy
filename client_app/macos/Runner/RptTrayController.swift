// macOS menu bar (system tray) status item for Restore Privacy.
// Hide main window after product full-tunnel Connect; restore via tray menu.
// Closing the last window does not quit while tray mode is active; Packet Tunnel
// is never stopped by hide/window-close (Disconnect remains explicit).

import Cocoa
import FlutterMacOS

enum RptTrayController {
  static let channelName = "restore_privacy/window"
  private static var statusItem: NSStatusItem?
  private static var messenger: FlutterBinaryMessenger?
  private static var trayMode = false
  private static var connected = false

  static func register(with messenger: FlutterBinaryMessenger) {
    self.messenger = messenger
    let channel = FlutterMethodChannel(name: channelName, binaryMessenger: messenger)
    channel.setMethodCallHandler { call, result in
      switch call.method {
      case "hideToTray":
        let args = call.arguments as? [String: Any] ?? [:]
        let conn = (args["connected"] as? Bool) ?? true
        ensureStatusItem()
        setConnected(conn)
        hideMainWindow()
        trayMode = true
        result(nil)
      case "showFromTray":
        showMainWindow()
        result(nil)
      case "setTrayConnected":
        let args = call.arguments as? [String: Any] ?? [:]
        let conn = (args["connected"] as? Bool) ?? false
        setConnected(conn)
        if conn {
          ensureStatusItem()
          trayMode = true
        }
        result(nil)
      default:
        result(FlutterMethodNotImplemented)
      }
    }
  }

  /// When tray mode is on, do not terminate after the last window closes.
  static var shouldTerminateAfterLastWindowClosed: Bool {
    !trayMode
  }

  private static func ensureStatusItem() {
    if statusItem != nil { return }
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    if let button = item.button {
      // Prefer app icon; fall back to short product mark.
      if let img = NSApp.applicationIconImage?.copy() as? NSImage {
        img.size = NSSize(width: 18, height: 18)
        button.image = img
        button.imagePosition = .imageLeading
      }
      button.title = " RP"
      button.toolTip = "Restore Privacy"
    }
    let menu = NSMenu()
    menu.addItem(NSMenuItem(
      title: "Show Restore Privacy",
      action: #selector(StatusMenuTarget.showWindow(_:)),
      keyEquivalent: ""
    ))
    menu.addItem(NSMenuItem(
      title: "Disconnect",
      action: #selector(StatusMenuTarget.disconnect(_:)),
      keyEquivalent: ""
    ))
    menu.addItem(NSMenuItem.separator())
    menu.addItem(NSMenuItem(
      title: "Quit",
      action: #selector(StatusMenuTarget.quitApp(_:)),
      keyEquivalent: "q"
    ))
    // Target must outlive menu — use shared singleton target.
    let target = StatusMenuTarget.shared
    for item in menu.items where item.action != nil {
      item.target = target
    }
    item.menu = menu
    statusItem = item
  }

  private static func setConnected(_ value: Bool) {
    connected = value
    if let button = statusItem?.button {
      button.toolTip = value
        ? "Restore Privacy — Connected (residual VPN active)"
        : "Restore Privacy — Disconnected"
      button.title = value ? " RP●" : " RP"
    }
  }

  private static func hideMainWindow() {
    for window in NSApp.windows {
      window.orderOut(nil)
    }
    // Keep dock icon; user restores via tray or dock.
    NSApp.hide(nil)
  }

  static func showMainWindow() {
    NSApp.unhide(nil)
    NSApp.activate(ignoringOtherApps: true)
    if let window = NSApp.windows.first(where: { $0 is MainFlutterWindow })
      ?? NSApp.windows.first {
      window.makeKeyAndOrderFront(nil)
      window.orderFrontRegardless()
    }
  }

  static func requestFlutterDisconnect() {
    guard let messenger else { return }
    let channel = FlutterMethodChannel(name: channelName, binaryMessenger: messenger)
    channel.invokeMethod("trayDisconnect", arguments: nil)
  }

  static func requestFlutterShow() {
    guard let messenger else { return }
    let channel = FlutterMethodChannel(name: channelName, binaryMessenger: messenger)
    channel.invokeMethod("trayShow", arguments: nil)
  }

  /// Menu target for NSStatusItem actions.
  final class StatusMenuTarget: NSObject {
    static let shared = StatusMenuTarget()

    @objc func showWindow(_ sender: Any?) {
      RptTrayController.showMainWindow()
      RptTrayController.requestFlutterShow()
    }

    @objc func disconnect(_ sender: Any?) {
      // Show UI so user sees disconnect status; tunnel stop is Flutter Disconnect path.
      RptTrayController.showMainWindow()
      RptTrayController.requestFlutterDisconnect()
    }

    @objc func quitApp(_ sender: Any?) {
      // Quit host only — product policy: Packet Tunnel is not auto-stopped on host quit
      // unless Flutter/shell wires terminate hooks (macOS AppDelegate leaves tunnel up).
      NSApp.terminate(nil)
    }
  }
}
