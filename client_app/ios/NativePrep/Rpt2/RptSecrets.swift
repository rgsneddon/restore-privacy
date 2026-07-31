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
    public static let exitNodePubName = "exit_node_elgamal.pub"
    public static let usNodePubName = "us_node_elgamal.pub" // retired monopin file
    /// Germany residual hop public key (HELLO when residual host is DE monopin).
    public static let deNodePubName = "de_node_elgamal.pub"
    /// Product default residual entry (Germany monopin).
    public static let productEntryHost = "178.105.187.178"
    public static let productIcelandHost = "82.221.101.241"
    public static let productExitHost = "178.105.187.178"
    public static let productUsHost = "5.161.242.85" // retired monopin
    public static let productDeHost = "178.105.187.178"
    /// Must never be loaded by product clients.
    public static let nodePrivName = "node_elgamal.priv"

    /// Public key basename for residual HELLO from dial host monopin.
    /// IS → node; DE → de; retired US → de (never invent pin from entry code alone).
    public static func residualNodePubName(forHost host: String) -> String {
        let h = host.trimmingCharacters(in: .whitespacesAndNewlines)
        if h == productDeHost || h.hasSuffix(productDeHost)
            || h == productExitHost || h.hasSuffix(productExitHost) {
            return deNodePubName
        }
        // Retired US monopin — heal to DE pin
        if h == productUsHost || h.hasSuffix(productUsHost) {
            return deNodePubName
        }
        if h == productIcelandHost || h.hasSuffix(productIcelandHost) {
            return nodePubName
        }
        return nodePubName
    }

    public static var appGroupId: String { "group.com.restoreprivacy.shared" }

    /// Product-relative secrets folder name under Application Support / bundle.
    public static let appSupportFolderName = "Restore Privacy"

    // MARK: - Path resolution

    /// Real login-user home (not the App Sandbox container home).
    public static func realUserHomeDirectory() -> URL? {
        #if os(macOS)
        if let pw = getpwuid(getuid()), let dir = pw.pointee.pw_dir {
            return URL(fileURLWithPath: String(cString: dir), isDirectory: true)
        }
        #endif
        if let home = ProcessInfo.processInfo.environment["HOME"], !home.isEmpty {
            // May be container path under sandbox — still useful as a candidate.
            return URL(fileURLWithPath: home, isDirectory: true)
        }
        #if os(macOS)
        return FileManager.default.homeDirectoryForCurrentUser
        #else
        return FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
        #endif
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

        // 6. Sandbox / container home (Flutter)
        #if os(macOS)
        let containerHome = fileManager.homeDirectoryForCurrentUser
            .appendingPathComponent(".restore-privacy", isDirectory: true)
            .appendingPathComponent("secrets", isDirectory: true)
        dirs.append(containerHome)
        #else
        if let docs = fileManager.urls(for: .documentDirectory, in: .userDomainMask).first {
            dirs.append(docs.appendingPathComponent("secrets", isDirectory: true))
        }
        #endif

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
        #if os(macOS)
        return fileManager.homeDirectoryForCurrentUser
            .appendingPathComponent(".restore-privacy/secrets", isDirectory: true)
        #else
        return fileManager.urls(for: .documentDirectory, in: .userDomainMask).first?
            .appendingPathComponent("secrets", isDirectory: true)
        #endif
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
        // Host should seed App Group so Packet Tunnel can load the same keys.
        if let dir = try? seedAppGroupFromKnownSourcesIfNeeded(fileManager: fileManager, bundle: bundle) {
            return try loadFromDirectory(dir)
        }

        let paths = searchedPathsDescription(fileManager: fileManager, bundle: bundle)
        throw RptProtocol.ProtocolError(
            "Missing admission secrets — place client_ed25519.priv and node_elgamal.pub in "
                + "App Group group.com.restoreprivacy.shared/secrets/ "
                + "(or ~/.restore-privacy/secrets/, Application Support, or bundle Resources/secrets/). "
                + "Never ship node_elgamal.priv. "
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
