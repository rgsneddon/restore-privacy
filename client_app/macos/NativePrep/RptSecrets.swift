// macOS secrets helpers — App Group preferred; never ship node_elgamal.priv.

import Foundation

enum RptSecrets {
  static let clientPrivName = "client_ed25519.priv"
  static let nodePubName = "node_elgamal.pub"
  static var appGroupId: String { "group.com.restoreprivacy.shared" }

  static func secretsDirectory() -> URL? {
    if let base = FileManager.default.containerURL(
      forSecurityApplicationGroupIdentifier: appGroupId
    ) {
      return base.appendingPathComponent("secrets", isDirectory: true)
    }
    return FileManager.default.homeDirectoryForCurrentUser
      .appendingPathComponent(".restore-privacy/secrets", isDirectory: true)
  }

  static func filesPresent() -> Bool {
    guard let dir = secretsDirectory() else { return false }
    let fm = FileManager.default
    return fm.fileExists(atPath: dir.appendingPathComponent(clientPrivName).path)
      && fm.fileExists(atPath: dir.appendingPathComponent(nodePubName).path)
  }
}
