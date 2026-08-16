// macOS menu bar (system tray) status item for residual VPN.
// Durable tray text is always "Privacy, Restored" (forward monopin identity).
// Hide main window after product full-tunnel Connect; restore via tray menu.
// Closing the last window does not quit while tray mode is active; Packet Tunnel
// is never stopped by hide/window-close (Disconnect remains explicit).

import Cocoa
import FlutterMacOS

enum RptTrayController {
  /// Durable system-tray / status-item title (all forward monopin ships).
  static let trayDisplayName = "Privacy, Restored"
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

  /// True while menu-bar tray keep-alive is active (hide-to-tray / connected).
  static var isTrayMode: Bool { trayMode }

  private static var statusMenu: NSMenu?

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
      button.title = trayDisplayName
      button.toolTip = "\(trayDisplayName) — click to show window"
      // Left-click restores window; right-click / Ctrl-click shows menu.
      // (Assigning item.menu would steal left-click and only open the menu.)
      button.target = StatusMenuTarget.shared
      button.action = #selector(StatusMenuTarget.statusItemClicked(_:))
      button.sendAction(on: [.leftMouseUp, .rightMouseUp])
    }
    let menu = NSMenu()
    menu.addItem(NSMenuItem(
      title: "Show \(trayDisplayName)",
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
    let target = StatusMenuTarget.shared
    for mi in menu.items where mi.action != nil {
      mi.target = target
    }
    statusMenu = menu
    // Do not set item.menu — left-click must call statusItemClicked → showMainWindow.
    statusItem = item
  }

  private static func setConnected(_ value: Bool) {
    connected = value
    if let button = statusItem?.button {
      button.toolTip = value
        ? "\(trayDisplayName) — connected (VPN active)"
        : "\(trayDisplayName) — disconnected"
      button.title = value ? "\(trayDisplayName)●" : trayDisplayName
    }
  }

  private static func hideMainWindow() {
    for window in NSApp.windows {
      // Prefer orderOut so the window instance survives (not destroyed).
      window.orderOut(nil)
    }
    // Keep dock icon; user restores via tray or dock.
    NSApp.hide(nil)
  }

  /// Restore the main Flutter window after hide-to-tray or minimize.
  /// Does **not** stop the Packet Tunnel (product: Disconnect only).
  static func showMainWindow() {
    // Keep tray mode so last-window-close still does not quit while connected UX remains.
    NSApp.unhide(nil)
    NSApp.activate(ignoringOtherApps: true)

    // Prefer MainFlutterWindow; fall back to any app window (dialogs, etc.).
    let flutterWindows = NSApp.windows.filter { $0 is MainFlutterWindow }
    let targets: [NSWindow] = flutterWindows.isEmpty ? Array(NSApp.windows) : flutterWindows

    if targets.isEmpty {
      // No window object left — nothing to order front (should not happen after orderOut hide).
      return
    }

    for window in targets {
      if window.isMiniaturized {
        window.deminiaturize(nil)
      }
      // Ensure non-visible / ordered-out windows return to the screen.
      if !window.isVisible {
        window.orderFrontRegardless()
      }
      window.makeKeyAndOrderFront(nil)
      window.orderFrontRegardless()
      // Focus the content view for keyboard input.
      if let content = window.contentView {
        window.makeFirstResponder(content)
      }
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

  /// App menu Settings… / Cmd+, — Flutter TunnelHome opens product Settings.
  static func requestOpenProductSettings() {
    guard let messenger else { return }
    let channel = FlutterMethodChannel(name: channelName, binaryMessenger: messenger)
    channel.invokeMethod("openProductSettings", arguments: nil)
  }

  /// Menu / status-item target for NSStatusItem actions.
  final class StatusMenuTarget: NSObject {
    static let shared = StatusMenuTarget()

    @objc func statusItemClicked(_ sender: Any?) {
      guard let event = NSApp.currentEvent else {
        showWindow(sender)
        return
      }
      // Right-click or control-click → menu (Disconnect / Quit).
      if event.type == .rightMouseUp
        || event.modifierFlags.contains(.control) {
        if let button = RptTrayController.statusItem?.button,
           let menu = RptTrayController.statusMenu {
          menu.popUp(
            positioning: nil,
            at: NSPoint(x: 0, y: button.bounds.height),
            in: button
          )
        }
        return
      }
      // Left-click → restore main window (primary user path).
      showWindow(sender)
    }

    @objc func showWindow(_ sender: Any?) {
      // Native must deminiaturize/order-front; Flutter only rehydrates UI state.
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
