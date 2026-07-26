import Foundation
#if canImport(CryptoKit)
import CryptoKit
#endif
#if canImport(Darwin)
import Darwin
#endif
#if canImport(Security)
import Security
#endif

/// Secrets path helpers for Apple platforms.
/// Never load or ship `node_elgamal.priv`.
/// Never ship a shared `client_ed25519.priv` — each install generates a unique
/// Ed25519 device key on first run and stores it in local private storage.
///
/// Search order mirrors Windows `client/secrets_loader.py` / Android assets inject:
/// env override → App Group → bundle Resources → Application Support → real user home
/// (`~/.restore-privacy/secrets`) → sandbox home. Sandboxed apps must use real home via
/// `getpwuid` (not container home) plus the home-relative temporary-exception entitlement.
public enum RptSecrets {
    public static let clientPrivName = "client_ed25519.priv"
    public static let nodePubName = "node_elgamal.pub"
    public static let exitNodePubName = "exit_node_elgamal.pub"
    public static let usNodePubName = "us_node_elgamal.pub"
    /// Product default residual entry (United States monopin).
    public static let productEntryHost = "5.161.242.85"
    public static let productIcelandHost = "82.221.101.241"
    public static let productExitHost = "185.146.232.107"
    public static let productUsHost = "5.161.242.85"
    /// Must never be loaded by product clients.
    public static let nodePrivName = "node_elgamal.priv"

    /// Public key basename for residual HELLO from dial host monopin.
    /// IS → node; RO → exit; US → us.
    public static func residualNodePubName(forHost host: String) -> String {
        let h = host.trimmingCharacters(in: .whitespacesAndNewlines)
        if h == productExitHost || h.hasSuffix(productExitHost) {
            return exitNodePubName
        }
        if h == productUsHost || h.hasSuffix(productUsHost) {
            return usNodePubName
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

    /// True for bundle Resources/secrets — may hold a residual shared product priv; never trust it as device identity.
    public static func isPackageReadonlySecretsDir(
        _ dir: URL,
        bundle: Bundle = .main,
        fileManager: FileManager = .default
    ) -> Bool {
        let path = dir.standardizedFileURL.path
        if let res = bundle.resourceURL?
            .appendingPathComponent("secrets", isDirectory: true)
            .standardizedFileURL.path,
            path == res {
            return true
        }
        if let builtIn = bundle.url(forResource: "secrets", withExtension: nil)?
            .standardizedFileURL.path,
            path == builtIn {
            return true
        }
        // Common package markers
        let lower = path.lowercased()
        if lower.contains("/contents/resources/secrets") { return true }
        if lower.hasSuffix("/runner.app/secrets") { return true }
        return false
    }

    /// First **trusted** (non-package) directory that already has a device key + node pub.
    public static func resolveSecretsDirectory(
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) -> URL? {
        for dir in candidateSecretsDirectories(fileManager: fileManager, bundle: bundle) {
            if isPackageReadonlySecretsDir(dir, bundle: bundle, fileManager: fileManager) {
                continue
            }
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

    public static func dirHasNodePub(_ dir: URL, fileManager: FileManager = .default) -> Bool {
        fileManager.fileExists(atPath: dir.appendingPathComponent(nodePubName).path)
    }

    /// Generate a unique Ed25519 private key (32 raw bytes) for this device install.
    public static func generateDeviceEd25519PrivateKey() throws -> Data {
        #if canImport(CryptoKit)
        let key = Curve25519.Signing.PrivateKey()
        let raw = key.rawRepresentation
        guard raw.count == 32 else {
            throw RptProtocol.ProtocolError("generated Ed25519 key must be 32 bytes")
        }
        return raw
        #else
        // Fallback: OS random 32-byte seed (Ed25519 seed)
        var bytes = [UInt8](repeating: 0, count: 32)
        let status = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        guard status == errSecSuccess else {
            throw RptProtocol.ProtocolError("SecRandomCopyBytes failed for device key")
        }
        return Data(bytes)
        #endif
    }

    /// Ensure a per-device Ed25519 priv exists under `dest` (idempotent).
    @discardableResult
    public static func ensureDeviceAdmissionKey(
        in dest: URL,
        nodePubSource: URL? = nil,
        fileManager: FileManager = .default
    ) throws -> URL {
        try fileManager.createDirectory(at: dest, withIntermediateDirectories: true)
        let privURL = dest.appendingPathComponent(clientPrivName)
        let nodeURL = dest.appendingPathComponent(nodePubName)

        if !fileManager.fileExists(atPath: nodeURL.path) {
            guard let src = nodePubSource else {
                throw RptProtocol.ProtocolError("missing \(nodePubName) for device key bootstrap")
            }
            if fileManager.fileExists(atPath: nodeURL.path) {
                try fileManager.removeItem(at: nodeURL)
            }
            try fileManager.copyItem(at: src, to: nodeURL)
        }

        if !fileManager.fileExists(atPath: privURL.path) {
            let raw = try generateDeviceEd25519PrivateKey()
            try raw.write(to: privURL, options: .atomic)
        } else {
            let existing = try Data(contentsOf: privURL)
            guard existing.count == 32 else {
                throw RptProtocol.ProtocolError("\(clientPrivName) must be 32 raw bytes")
            }
        }
        return dest
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

    /// Load product admission material (device client priv + node pub). Never loads node private key.
    /// Generates a unique Ed25519 device key on first run. Never adopts a shared priv from the app bundle.
    public static func loadAdmissionMaterial(
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) throws -> (clientPriv: Data, nodePub: Data) {
        // Prefer trusted writable storage that already has a device key (not bundle).
        if let dir = resolveSecretsDirectory(fileManager: fileManager, bundle: bundle) {
            return try loadFromDirectory(dir)
        }

        // Bootstrap: node pub from bundle → generate device key into App Support / App Group
        if let dir = try? seedApplicationSupportFromBundleIfNeeded(fileManager: fileManager, bundle: bundle) {
            return try loadFromDirectory(dir)
        }
        if let dir = try? seedAppGroupFromKnownSourcesIfNeeded(fileManager: fileManager, bundle: bundle) {
            return try loadFromDirectory(dir)
        }

        // Last resort: generate device key in preferred writable dir next to any node pub
        if let dest = secretsDirectory(fileManager: fileManager) {
            var nodeSrc: URL?
            for d in candidateSecretsDirectories(fileManager: fileManager, bundle: bundle) {
                let n = d.appendingPathComponent(nodePubName)
                if fileManager.fileExists(atPath: n.path) {
                    nodeSrc = n
                    break
                }
            }
            if let nodeSrc {
                _ = try ensureDeviceAdmissionKey(in: dest, nodePubSource: nodeSrc, fileManager: fileManager)
                return try loadFromDirectory(dest)
            }
        }

        let paths = searchedPathsDescription(fileManager: fileManager, bundle: bundle)
        throw RptProtocol.ProtocolError(
            "Missing node_elgamal.pub — packages ship the public node key; "
                + "a unique device Ed25519 key is generated on first run. "
                + "Never ship node_elgamal.priv or a shared client_ed25519.priv. "
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

    /// Seed node_elgamal.pub from bundle and ensure a per-device Ed25519 key under Application Support.
    /// Never copies client_ed25519.priv from the bundle (shared product key risk).
    @discardableResult
    public static func seedApplicationSupportFromBundleIfNeeded(
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) throws -> URL? {
        guard let res = bundle.resourceURL?
            .appendingPathComponent("secrets", isDirectory: true) else {
            return nil
        }
        let resNode = res.appendingPathComponent(nodePubName)
        guard fileManager.fileExists(atPath: resNode.path) else {
            return nil
        }
        guard let support = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            return nil
        }
        let dest = support
            .appendingPathComponent(appSupportFolderName, isDirectory: true)
            .appendingPathComponent("secrets", isDirectory: true)
        if dirHasClientSecrets(dest, fileManager: fileManager) {
            return dest
        }
        return try ensureDeviceAdmissionKey(in: dest, nodePubSource: resNode, fileManager: fileManager)
    }

    /// Ensure App Group has device key + node pub so Packet Tunnel can connect.
    /// Never copies client_ed25519.priv from the app bundle — only from trusted writable dirs or generate.
    @discardableResult
    public static func seedAppGroupFromKnownSourcesIfNeeded(
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) throws -> URL? {
        guard let groupBase = fileManager.containerURL(
            forSecurityApplicationGroupIdentifier: appGroupId
        ) else {
            return nil
        }
        let dest = groupBase.appendingPathComponent("secrets", isDirectory: true)
        if dirHasClientSecrets(dest, fileManager: fileManager) {
            return dest
        }
        var nodeSrc: URL?
        for dir in candidateSecretsDirectories(fileManager: fileManager, bundle: bundle) {
            if dir.standardizedFileURL.path == dest.standardizedFileURL.path { continue }
            let n = dir.appendingPathComponent(nodePubName)
            if fileManager.fileExists(atPath: n.path) {
                nodeSrc = n
                break
            }
        }
        // Device priv only from trusted (non-package) locations
        var privSrc: URL?
        for dir in candidateSecretsDirectories(fileManager: fileManager, bundle: bundle) {
            if isPackageReadonlySecretsDir(dir, bundle: bundle, fileManager: fileManager) {
                continue
            }
            let c = dir.appendingPathComponent(clientPrivName)
            if fileManager.fileExists(atPath: c.path) {
                privSrc = c
                break
            }
        }
        guard let nodeSrc else { return nil }
        try fileManager.createDirectory(at: dest, withIntermediateDirectories: true)
        let nodeDest = dest.appendingPathComponent(nodePubName)
        if !fileManager.fileExists(atPath: nodeDest.path) {
            try fileManager.copyItem(at: nodeSrc, to: nodeDest)
        }
        let privDest = dest.appendingPathComponent(clientPrivName)
        if let privSrc, !fileManager.fileExists(atPath: privDest.path) {
            try fileManager.copyItem(at: privSrc, to: privDest)
        }
        if !fileManager.fileExists(atPath: privDest.path) {
            _ = try ensureDeviceAdmissionKey(in: dest, nodePubSource: nodeSrc, fileManager: fileManager)
        }
        return dirHasClientSecrets(dest, fileManager: fileManager) ? dest : nil
    }
}
