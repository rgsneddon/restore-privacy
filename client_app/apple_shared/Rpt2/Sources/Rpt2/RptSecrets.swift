import Foundation
#if canImport(Darwin)
import Darwin
#endif

/// Secrets path helpers for Apple platforms.
/// Never load or ship `node_elgamal.priv`.
///
/// Search order mirrors Windows `client/secrets_loader.py` / Android assets inject:
/// env override → App Group → bundle Resources → Application Support → real user home
/// (`~/.restore-privacy/secrets`) → sandbox home. Sandboxed apps must use real home via
/// `getpwuid` (not container home) plus the home-relative temporary-exception entitlement.
public enum RptSecrets {
    public static let clientPrivName = "client_ed25519.priv"
    public static let nodePubName = "node_elgamal.pub"
    /// Must never be loaded by product clients.
    public static let nodePrivName = "node_elgamal.priv"

    public static var appGroupId: String { "group.com.restoreprivacy.shared" }

    /// Product-relative secrets folder name under Application Support / bundle.
    public static let appSupportFolderName = "Restore Privacy"

    // MARK: - Path resolution

    /// Real login-user home (not the App Sandbox container home).
    public static func realUserHomeDirectory() -> URL? {
        #if os(macOS) || os(iOS)
        if let pw = getpwuid(getuid()), let dir = pw.pointee.pw_dir {
            return URL(fileURLWithPath: String(cString: dir), isDirectory: true)
        }
        #endif
        if let home = ProcessInfo.processInfo.environment["HOME"], !home.isEmpty {
            // May be container path under sandbox — still useful as a candidate.
            return URL(fileURLWithPath: home, isDirectory: true)
        }
        return FileManager.default.homeDirectoryForCurrentUser
    }

    /// Ordered candidate directories that may hold admission keys (never node private key).
    public static func candidateSecretsDirectories(
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) -> [URL] {
        var dirs: [URL] = []

        // 1. Explicit override (tests / advanced installs)
        if let env = ProcessInfo.processInfo.environment["RPT_SECRETS_DIR"], !env.isEmpty {
            dirs.append(URL(fileURLWithPath: env, isDirectory: true))
        }

        // 2. App Group (host ↔ Packet Tunnel)
        if let base = fileManager.containerURL(forSecurityApplicationGroupIdentifier: appGroupId) {
            dirs.append(base.appendingPathComponent("secrets", isDirectory: true))
        }

        // 3. Bundled Resources/secrets (Android-style inject at package time)
        if let res = bundle.resourceURL {
            dirs.append(res.appendingPathComponent("secrets", isDirectory: true))
        }
        // Some Flutter layouts put resources under Contents/Resources via bundle path
        if let builtIn = bundle.url(forResource: "secrets", withExtension: nil) {
            dirs.append(builtIn)
        }

        // 4. Application Support (sandbox-visible writable location)
        if let support = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first {
            dirs.append(
                support
                    .appendingPathComponent(appSupportFolderName, isDirectory: true)
                    .appendingPathComponent("secrets", isDirectory: true)
            )
        }

        // 5. Real user home ~/.restore-privacy/secrets (requires home-relative exception when sandboxed)
        if let realHome = realUserHomeDirectory() {
            dirs.append(
                realHome
                    .appendingPathComponent(".restore-privacy", isDirectory: true)
                    .appendingPathComponent("secrets", isDirectory: true)
            )
        }

        // 6. Sandbox / NSHomeDirectory home (Flutter container)
        let containerHome = fileManager.homeDirectoryForCurrentUser
            .appendingPathComponent(".restore-privacy", isDirectory: true)
            .appendingPathComponent("secrets", isDirectory: true)
        dirs.append(containerHome)

        // De-dupe by standardized path
        var seen = Set<String>()
        var unique: [URL] = []
        for d in dirs {
            let key = d.standardizedFileURL.path
            if seen.insert(key).inserted {
                unique.append(d)
            }
        }
        return unique
    }

    /// First candidate directory that contains both admission files.
    public static func resolveSecretsDirectory(
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) -> URL? {
        for dir in candidateSecretsDirectories(fileManager: fileManager, bundle: bundle) {
            if dirHasClientSecrets(dir, fileManager: fileManager) {
                return dir
            }
        }
        return nil
    }

    public static func dirHasClientSecrets(_ dir: URL, fileManager: FileManager = .default) -> Bool {
        let c = dir.appendingPathComponent(clientPrivName)
        let n = dir.appendingPathComponent(nodePubName)
        return fileManager.fileExists(atPath: c.path) && fileManager.fileExists(atPath: n.path)
    }

    /// Preferred secrets directory for UI / docs (resolved or default install path).
    public static func secretsDirectory(fileManager: FileManager = .default) -> URL? {
        if let found = resolveSecretsDirectory(fileManager: fileManager) {
            return found
        }
        // Default install location advertised to users
        if let realHome = realUserHomeDirectory() {
            return realHome
                .appendingPathComponent(".restore-privacy", isDirectory: true)
                .appendingPathComponent("secrets", isDirectory: true)
        }
        return fileManager.homeDirectoryForCurrentUser
            .appendingPathComponent(".restore-privacy/secrets", isDirectory: true)
    }

    public static func clientPrivateKeyURL(fileManager: FileManager = .default) -> URL? {
        secretsDirectory(fileManager: fileManager)?.appendingPathComponent(clientPrivName)
    }

    public static func nodePublicKeyURL(fileManager: FileManager = .default) -> URL? {
        secretsDirectory(fileManager: fileManager)?.appendingPathComponent(nodePubName)
    }

    public static func filesPresent(fileManager: FileManager = .default) -> Bool {
        resolveSecretsDirectory(fileManager: fileManager) != nil
    }

    /// Human-readable list of paths searched (for error messages / diagnostics).
    public static func searchedPathsDescription(
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) -> String {
        candidateSecretsDirectories(fileManager: fileManager, bundle: bundle)
            .prefix(8)
            .map(\.path)
            .joined(separator: ", ")
    }

    // MARK: - Load

    /// Load product admission material only (client priv + node pub). Never loads node private key.
    public static func loadAdmissionMaterial(
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) throws -> (clientPriv: Data, nodePub: Data) {
        // Prefer a resolved directory that already has both files.
        if let dir = resolveSecretsDirectory(fileManager: fileManager, bundle: bundle) {
            return try loadFromDirectory(dir)
        }

        // Attempt bundle → Application Support seed if bundle has secrets but App Support does not
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

    public static func loadFromDirectory(_ dir: URL) throws -> (clientPriv: Data, nodePub: Data) {
        let cURL = dir.appendingPathComponent(clientPrivName)
        let nURL = dir.appendingPathComponent(nodePubName)
        // Explicitly do not open node_elgamal.priv
        let clientPriv = try Data(contentsOf: cURL)
        let nodePub = try Data(contentsOf: nURL)
        guard clientPriv.count == 32 else {
            throw RptProtocol.ProtocolError("client_ed25519.priv must be 32 raw bytes")
        }
        guard nodePub.count == 256 else {
            throw RptProtocol.ProtocolError("node_elgamal.pub must be 256 bytes")
        }
        return (clientPriv, nodePub)
    }

    /// Copy bundled Resources/secrets into Application Support so host and future launches find them.
    @discardableResult
    public static func seedApplicationSupportFromBundleIfNeeded(
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) throws -> URL? {
        guard let res = bundle.resourceURL?
            .appendingPathComponent("secrets", isDirectory: true),
            dirHasClientSecrets(res, fileManager: fileManager) else {
            return nil
        }
        guard let support = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            return res
        }
        let dest = support
            .appendingPathComponent(appSupportFolderName, isDirectory: true)
            .appendingPathComponent("secrets", isDirectory: true)
        if dirHasClientSecrets(dest, fileManager: fileManager) {
            return dest
        }
        try fileManager.createDirectory(at: dest, withIntermediateDirectories: true)
        for name in [clientPrivName, nodePubName] {
            let from = res.appendingPathComponent(name)
            let to = dest.appendingPathComponent(name)
            if fileManager.fileExists(atPath: to.path) {
                try fileManager.removeItem(at: to)
            }
            try fileManager.copyItem(at: from, to: to)
        }
        // Never copy node_elgamal.priv even if present in source tree by mistake
        return dest
    }
}
