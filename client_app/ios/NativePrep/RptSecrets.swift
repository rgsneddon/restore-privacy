// Secrets path helpers for iOS (App Group preferred).
// Never load or ship node_elgamal.priv.

import Foundation

enum RptSecrets {
  static let clientPrivName = "client_ed25519.priv"
  static let nodePubName = "node_elgamal.pub"

  /// Replace with your App Group id from Xcode.
  static var appGroupId: String { "group.com.restoreprivacy.shared" }

  static func secretsDirectory() -> URL? {
    if let base = FileManager.default.containerURL(
      forSecurityApplicationGroupIdentifier: appGroupId
    ) {
      return base.appendingPathComponent("secrets", isDirectory: true)
    }
    // Dev fallback (simulator / incomplete App Group)
    return FileManager.default.homeDirectoryForCurrentUser
      .appendingPathComponent(".restore-privacy/secrets", isDirectory: true)
  }

  static func clientPrivateKeyURL() -> URL? {
    secretsDirectory()?.appendingPathComponent(clientPrivName)
  }

  static func nodePublicKeyURL() -> URL? {
    secretsDirectory()?.appendingPathComponent(nodePubName)
  }

  static func filesPresent() -> Bool {
    guard let c = clientPrivateKeyURL(), let n = nodePublicKeyURL() else { return false }
    return FileManager.default.fileExists(atPath: c.path)
      && FileManager.default.fileExists(atPath: n.path)
  }
}
