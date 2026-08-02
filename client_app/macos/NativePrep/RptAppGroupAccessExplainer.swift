// Product-owned explainer before App Group / “access data from other apps” TCC.
// Apple owns the system dialog text; this NSAlert is additive context only.
//
// Show-once: first cold path that seeds host↔Packet Tunnel shared state.

import AppKit
import Foundation

/// Copy + show-once gate for the Mac App Group access explainer.
enum RptAppGroupAccessExplainer {
  /// UserDefaults flag — after first dismiss, do not re-spam every launch.
  static let seenKey = "rpt_app_group_access_explainer_seen"

  /// Sheet title (product UI, not Apple TCC title).
  static let title = "Share with Packet Tunnel"

  /// Primary one-line reason to Allow (tunnel ↔ residual nodes).
  static let oneLine =
    "Allow this so the Packet Tunnel can share keys with the host and connect to residual nodes."

  /// Short secondary: not third-party apps.
  static let secondaryLine =
    "This is only our tunnel extension — not Chrome, Mail, or other apps."

  static let continueButton = "Continue"

  /// Full informative body (one-line + secondary).
  static var body: String {
    "\(oneLine)\n\n\(secondaryLine)"
  }

  /// Pure gate: show only when the user has not dismissed the product sheet yet.
  static func shouldShow(defaults: UserDefaults = .standard) -> Bool {
    !defaults.bool(forKey: seenKey)
  }

  static func markShown(defaults: UserDefaults = .standard) {
    defaults.set(true, forKey: seenKey)
    defaults.synchronize()
  }

  /// Product honesty: copy names Packet Tunnel / residual nodes, not third-party inventory.
  static func copyIsValid(
    oneLine: String = oneLine,
    secondary: String = secondaryLine
  ) -> Bool {
    let blob = "\(oneLine) \(secondary)".lowercased()
    if blob.contains("chrome") && blob.contains("not") {
      // secondary may mention Chrome as something we do *not* access — OK
    }
    let mustOne: [String] = ["allow", "tunnel", "node"]
    for m in mustOne {
      if !oneLine.lowercased().contains(m) { return false }
    }
    // Must not claim scanning other people's apps as the purpose.
    if oneLine.lowercased().contains("scan") { return false }
    if oneLine.lowercased().contains("all apps") { return false }
    // Secondary clarifies Packet Tunnel only / not other apps.
    let sec = secondary.lowercased()
    if !(sec.contains("tunnel") || sec.contains("extension") || sec.contains("not")) {
      return false
    }
    return true
  }

  /// Present product NSAlert once, then mark seen. Call **before** first App Group seed.
  @discardableResult
  static func presentIfNeeded(
    defaults: UserDefaults = .standard,
    runModal: ((NSAlert) -> NSApplication.ModalResponse)? = nil
  ) -> Bool {
    guard shouldShow(defaults: defaults) else { return false }
    let alert = NSAlert()
    alert.messageText = title
    alert.informativeText = body
    alert.alertStyle = .informational
    alert.addButton(withTitle: continueButton)
    if let runModal {
      _ = runModal(alert)
    } else {
      // Main-thread modal; register() runs from MainFlutterWindow.awakeFromNib.
      _ = alert.runModal()
    }
    markShown(defaults: defaults)
    return true
  }
}
