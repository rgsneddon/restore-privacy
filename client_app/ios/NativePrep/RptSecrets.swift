// macOS secrets helpers — multi-path search (bundle, App Support, real home).
// Never load or ship node_elgamal.priv.
//
// Implementation is the shared Rpt2/RptSecrets.swift when compiled into the target.
// This file is the NativePrep entry for prep docs / Xcode groups; keep API + path rules
// in sync with apple_shared/Rpt2/Sources/Rpt2/RptSecrets.swift.

import Foundation
import Darwin

enum RptSecrets {
  static let clientPrivName = "client_ed25519.priv"
  static let nodePubName = "node_elgamal.pub"
  /// Must never be loaded or shipped by product clients.
  static let nodePrivName = "node_elgamal.priv"
  static var appGroupId: String { "group.com.restoreprivacy.shared" }
  static let appSupportFolderName = "Restore Privacy"

  /// Real login-user home (not App Sandbox container home). macOS-focused; iOS uses container paths.
  static func realUserHomeDirectory() -> URL? {
    #if os(macOS)
    if let pw = getpwuid(getuid()), let dir = pw.pointee.pw_dir {
      return URL(fileURLWithPath: String(cString: dir), isDirectory: true)
    }
    #endif
    if let home = ProcessInfo.processInfo.environment["HOME"], !home.isEmpty {
      return URL(fileURLWithPath: home, isDirectory: true)
    }
    #if os(macOS)
    return FileManager.default.homeDirectoryForCurrentUser
    #else
    return FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
    #endif
  }

  static func candidateSecretsDirectories(
    fileManager: FileManager = .default,
    bundle: Bundle = .main
  ) -> [URL] {
    var dirs: [URL] = []
    if let env = ProcessInfo.processInfo.environment["RPT_SECRETS_DIR"], !env.isEmpty {
      dirs.append(URL(fileURLWithPath: env, isDirectory: true))
    }
    if let base = fileManager.containerURL(forSecurityApplicationGroupIdentifier: appGroupId) {
      dirs.append(base.appendingPathComponent("secrets", isDirectory: true))
    }
    if let res = bundle.resourceURL {
      dirs.append(res.appendingPathComponent("secrets", isDirectory: true))
    }
    if let builtIn = bundle.url(forResource: "secrets", withExtension: nil) {
      dirs.append(builtIn)
    }
    if let support = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first {
      dirs.append(
        support
          .appendingPathComponent(appSupportFolderName, isDirectory: true)
          .appendingPathComponent("secrets", isDirectory: true)
      )
    }
    if let realHome = realUserHomeDirectory() {
      dirs.append(
        realHome
          .appendingPathComponent(".restore-privacy", isDirectory: true)
          .appendingPathComponent("secrets", isDirectory: true)
      )
    }
    #if os(macOS)
    dirs.append(
      fileManager.homeDirectoryForCurrentUser
        .appendingPathComponent(".restore-privacy/secrets", isDirectory: true)
    )
    #else
    if let docs = fileManager.urls(for: .documentDirectory, in: .userDomainMask).first {
      dirs.append(docs.appendingPathComponent("secrets", isDirectory: true))
    }
    #endif
    var seen = Set<String>()
    var unique: [URL] = []
    for d in dirs {
      let key = d.standardizedFileURL.path
      if seen.insert(key).inserted { unique.append(d) }
    }
    return unique
  }

  static func dirHasClientSecrets(_ dir: URL, fileManager: FileManager = .default) -> Bool {
    fileManager.fileExists(atPath: dir.appendingPathComponent(clientPrivName).path)
      && fileManager.fileExists(atPath: dir.appendingPathComponent(nodePubName).path)
  }

  static func resolveSecretsDirectory(
    fileManager: FileManager = .default,
    bundle: Bundle = .main
  ) -> URL? {
    for dir in candidateSecretsDirectories(fileManager: fileManager, bundle: bundle) {
      if dirHasClientSecrets(dir, fileManager: fileManager) { return dir }
    }
    return nil
  }

  static func secretsDirectory(fileManager: FileManager = .default) -> URL? {
    if let found = resolveSecretsDirectory(fileManager: fileManager) { return found }
    if let realHome = realUserHomeDirectory() {
      return realHome
        .appendingPathComponent(".restore-privacy/secrets", isDirectory: true)
    }
    #if os(macOS)
    return fileManager.homeDirectoryForCurrentUser
      .appendingPathComponent(".restore-privacy/secrets", isDirectory: true)
    #else
    return fileManager.urls(for: .documentDirectory, in: .userDomainMask).first?
      .appendingPathComponent("secrets", isDirectory: true)
    #endif
  }

  static func clientPrivateKeyURL(fileManager: FileManager = .default) -> URL? {
    secretsDirectory(fileManager: fileManager)?.appendingPathComponent(clientPrivName)
  }

  static func nodePublicKeyURL(fileManager: FileManager = .default) -> URL? {
    secretsDirectory(fileManager: fileManager)?.appendingPathComponent(nodePubName)
  }

  static func filesPresent(fileManager: FileManager = .default) -> Bool {
    resolveSecretsDirectory(fileManager: fileManager) != nil
  }

  static func searchedPathsDescription(
    fileManager: FileManager = .default,
    bundle: Bundle = .main
  ) -> String {
    candidateSecretsDirectories(fileManager: fileManager, bundle: bundle)
      .prefix(8)
      .map(\.path)
      .joined(separator: ", ")
  }

  /// Load product admission material only. Never loads node_elgamal.priv.
  static func loadAdmissionMaterial(
    fileManager: FileManager = .default,
    bundle: Bundle = .main
  ) throws -> (clientPriv: Data, nodePub: Data) {
    if let dir = resolveSecretsDirectory(fileManager: fileManager, bundle: bundle) {
      return try loadFromDirectory(dir)
    }
    if let dir = try? seedApplicationSupportFromBundleIfNeeded(fileManager: fileManager, bundle: bundle) {
      return try loadFromDirectory(dir)
    }
    let paths = searchedPathsDescription(fileManager: fileManager, bundle: bundle)
    throw RptProtocol.ProtocolError(
      "Missing admission secrets — place client_ed25519.priv and node_elgamal.pub in "
        + "~/.restore-privacy/secrets/ (or Application Support/Restore Privacy/secrets/, "
        + "or bundle Resources/secrets/). Never ship node_elgamal.priv. "
        + "Searched: \(paths)"
    )
  }

  static func loadFromDirectory(_ dir: URL) throws -> (clientPriv: Data, nodePub: Data) {
    let clientPriv = try Data(contentsOf: dir.appendingPathComponent(clientPrivName))
    let nodePub = try Data(contentsOf: dir.appendingPathComponent(nodePubName))
    guard clientPriv.count == 32 else {
      throw RptProtocol.ProtocolError("client_ed25519.priv must be 32 raw bytes")
    }
    guard nodePub.count == 256 else {
      throw RptProtocol.ProtocolError("node_elgamal.pub must be 256 bytes")
    }
    return (clientPriv, nodePub)
  }

  @discardableResult
  static func seedApplicationSupportFromBundleIfNeeded(
    fileManager: FileManager = .default,
    bundle: Bundle = .main
  ) throws -> URL? {
    guard let res = bundle.resourceURL?.appendingPathComponent("secrets", isDirectory: true),
          dirHasClientSecrets(res, fileManager: fileManager) else {
      return nil
    }
    guard let support = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
      return res
    }
    let dest = support
      .appendingPathComponent(appSupportFolderName, isDirectory: true)
      .appendingPathComponent("secrets", isDirectory: true)
    if dirHasClientSecrets(dest, fileManager: fileManager) { return dest }
    try fileManager.createDirectory(at: dest, withIntermediateDirectories: true)
    for name in [clientPrivName, nodePubName] {
      let from = res.appendingPathComponent(name)
      let to = dest.appendingPathComponent(name)
      if fileManager.fileExists(atPath: to.path) { try fileManager.removeItem(at: to) }
      try fileManager.copyItem(at: from, to: to)
    }
    return dest
  }
}
