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
    /// Multi-hop exit pin (same material as DE when exit is Germany).
    public static let exitNodePubName = "exit_node_elgamal.pub"
    /// United States residual hop public key (HELLO when residual host is US monopin).
    public static let usNodePubName = "us_node_elgamal.pub"
    /// Germany residual hop public key (HELLO when residual host is DE monopin).
    public static let deNodePubName = "de_node_elgamal.pub"
    /// Product default residual entry (Germany monopin).
    public static let productEntryHost = "178.105.187.178"
    public static let productIcelandHost = "82.221.101.241"
    public static let productExitHost = "178.105.187.178"
    public static let productUsHost = "5.161.242.85"
    public static let productDeHost = "178.105.187.178"
    /// Must never be loaded by product clients.
    public static let nodePrivName = "node_elgamal.priv"

    /// Public key basename for residual HELLO from dial host monopin.
    /// IS → node; DE → de; retired US → de (never invent pin from entry code alone).
    public static func residualNodePubName(forHost host: String) -> String {
        let h = host.trimmingCharacters(in: .whitespacesAndNewlines)
        // Empty / unknown / retired IS/US all use the live Germany pin.
        // Iceland `node_elgamal.pub` against the DE node is a silent-drop HELLO.
        if h == productIcelandHost || h.hasSuffix(productIcelandHost) {
            return deNodePubName
        }
        if h == productUsHost || h.hasSuffix(productUsHost) {
            return deNodePubName
        }
        return deNodePubName
    }

    /// All catalog residual public pin basenames (never private keys).
    public static let catalogPublicPubNames: [String] = [
        nodePubName, deNodePubName, exitNodePubName,
    ]

    /// Copy every catalog public pin found in *candidates* into *dest*.
    /// Host uses this so Packet Tunnel App Group / home secrets can HELLO to DE
    /// even when the appex bundle only ever saw Iceland ``node_elgamal.pub``.
    public static func seedCatalogPublicKeys(
        into dest: URL,
        candidates: [URL],
        fileManager: FileManager = .default
    ) {
        try? fileManager.createDirectory(at: dest, withIntermediateDirectories: true)
        for name in catalogPublicPubNames {
            var source: URL?
            for d in candidates {
                let c = d.appendingPathComponent(name)
                if fileManager.fileExists(atPath: c.path),
                   let attrs = try? fileManager.attributesOfItem(atPath: c.path),
                   let size = attrs[.size] as? NSNumber, size.intValue >= 32 {
                    source = c
                    break
                }
            }
            guard let source else { continue }
            let out = dest.appendingPathComponent(name)
            if source.path != out.path {
                if fileManager.fileExists(atPath: out.path) {
                    try? fileManager.removeItem(at: out)
                }
                try? fileManager.copyItem(at: source, to: out)
            }
        }
    }

    /// Host pre-seed before Packet Tunnel start: App Group + home + App Support.
    ///
    /// Tunnel Bundle.main often lacks RO/DE pins; shared writable dirs historically
    /// only held Iceland. Call from host Connect path with the residual dial host.
    ///
    /// **Critical:** host HELLO and Packet Tunnel must use the **same** device
    /// `client_ed25519.priv`. After wipe/reinstall, home may keep a KEYGEN-bound
    /// key while App Group has a newly generated one — tunnel then fails while
    /// host HELLO still assigns a node IP. Unify identity first.
    public static func preseedSharedWritableSecretsForResidualHost(
        residualHost: String,
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) throws {
        let candidates = Array(
            candidateSecretsDirectories(fileManager: fileManager, bundle: bundle)
        )
        var writables: [URL] = []
        if let groupBase = fileManager.containerURL(
            forSecurityApplicationGroupIdentifier: appGroupId
        ) {
            writables.append(groupBase.appendingPathComponent("secrets", isDirectory: true))
        }
        if let realHome = realUserHomeDirectory() {
            writables.append(
                realHome
                    .appendingPathComponent(".restore-privacy", isDirectory: true)
                    .appendingPathComponent("secrets", isDirectory: true)
            )
        }
        if let support = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first {
            writables.append(
                support
                    .appendingPathComponent(appSupportFolderName, isDirectory: true)
                    .appendingPathComponent("secrets", isDirectory: true)
            )
        }
        // 1) One device identity for host + sandboxed Packet Tunnel App Group.
        try unifyDeviceAdmissionKeysAcrossWritables(
            writables: writables,
            candidates: candidates,
            fileManager: fileManager
        )
        // 2) Catalog residual pubs (IS/DE/exit) into every writable.
        for dest in writables {
            seedCatalogPublicKeys(into: dest, candidates: candidates, fileManager: fileManager)
            try ensureResidualPubInWritableDir(
                writableDir: dest,
                residualHost: residualHost,
                candidates: candidates,
                fileManager: fileManager
            )
        }
    }

    /// Pure policy: which 32-byte device priv wins when multiple stores disagree.
    ///
    /// Prefer home, then Application Support, then App Group. Older installs bound
    /// KEYGEN to `~/.restore-privacy`; the tunnel only sees App Group under sandbox
    /// — so home/app-support win and are copied into the group.
    public static func preferredDevicePrivAmong(
        home: Data?,
        appSupport: Data?,
        appGroup: Data?
    ) -> Data? {
        for d in [home, appSupport, appGroup] {
            if let d, d.count == 32 { return d }
        }
        return nil
    }

    /// Write one device priv into every writable secrets dir (overwrite mismatches).
    /// Generates a new key into App Group (or first writable) when none exist.
    @discardableResult
    public static func unifyDeviceAdmissionKeysAcrossWritables(
        writables: [URL],
        candidates: [URL],
        fileManager: FileManager = .default
    ) throws -> Data {
        func readPriv(_ dir: URL) -> Data? {
            let p = dir.appendingPathComponent(clientPrivName)
            guard fileManager.isReadableFile(atPath: p.path),
                  let d = try? Data(contentsOf: p),
                  d.count == 32
            else { return nil }
            return d
        }

        var homePriv: Data?
        var supportPriv: Data?
        var groupPriv: Data?
        for dir in writables {
            let path = dir.path
            let d = readPriv(dir)
            if path.contains("Group Containers") || path.contains(appGroupId) {
                groupPriv = d ?? groupPriv
            } else if path.contains(".restore-privacy") {
                homePriv = d ?? homePriv
            } else if path.contains(appSupportFolderName) || path.contains("Application Support") {
                supportPriv = d ?? supportPriv
            } else if groupPriv == nil {
                groupPriv = d
            }
        }

        var winner = preferredDevicePrivAmong(
            home: homePriv,
            appSupport: supportPriv,
            appGroup: groupPriv
        )

        if winner == nil {
            // No key anywhere — generate once into first writable (prefer App Group).
            var nodeSrc: URL?
            for d in candidates {
                let n = d.appendingPathComponent(nodePubName)
                if fileManager.isReadableFile(atPath: n.path) {
                    nodeSrc = n
                    break
                }
            }
            let dest =
                writables.first(where: {
                    $0.path.contains("Group Containers") || $0.path.contains(appGroupId)
                }) ?? writables.first
            guard let dest, let nodeSrc else {
                throw RptProtocol.ProtocolError(
                    "Cannot unify device key: no writable secrets dir and no node_elgamal.pub"
                )
            }
            _ = try ensureDeviceAdmissionKey(
                in: dest,
                nodePubSource: nodeSrc,
                fileManager: fileManager
            )
            winner = readPriv(dest)
        }

        guard let priv = winner, priv.count == 32 else {
            throw RptProtocol.ProtocolError("Device admission key missing after unify")
        }

        for dest in writables {
            try fileManager.createDirectory(at: dest, withIntermediateDirectories: true)
            let privURL = dest.appendingPathComponent(clientPrivName)
            if let existing = readPriv(dest), existing == priv {
                continue
            }
            try priv.write(to: privURL, options: .atomic)
            // Best-effort mode 0600 (ignore failures on some volumes).
            try? fileManager.setAttributes(
                [.posixPermissions: 0o600],
                ofItemAtPath: privURL.path
            )
        }
        return priv
    }

    public static var appGroupId: String { "group.com.restoreprivacy.shared" }

    /// Packet Tunnel start trace (host reads this after NEVPN internal error).
    public static let packetTunnelStartTraceName = "pt_start_trace.txt"

    public static func packetTunnelStartTraceURL(
        fileManager: FileManager = .default
    ) -> URL? {
        if let group = fileManager
            .containerURL(forSecurityApplicationGroupIdentifier: appGroupId) {
            return group.appendingPathComponent(packetTunnelStartTraceName)
        }
        #if os(macOS)
        if let home = realUserHomeDirectory() {
            return home
                .appendingPathComponent(".restore-privacy")
                .appendingPathComponent(packetTunnelStartTraceName)
        }
        #endif
        return nil
    }

    public static func writePacketTunnelStartTrace(_ message: String) {
        let line = "\(ISO8601DateFormatter().string(from: Date())) \(message)\n"
        guard let data = line.data(using: .utf8) else { return }
        var urls: [URL] = []
        if let u = packetTunnelStartTraceURL() { urls.append(u) }
        #if os(macOS)
        if let home = realUserHomeDirectory() {
            let fallback = home
                .appendingPathComponent(".restore-privacy")
                .appendingPathComponent(packetTunnelStartTraceName)
            if !urls.contains(fallback) { urls.append(fallback) }
        }
        #endif
        for url in urls {
            try? FileManager.default.createDirectory(
                at: url.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            if FileManager.default.fileExists(atPath: url.path),
               let handle = try? FileHandle(forWritingTo: url) {
                handle.seekToEndOfFile()
                handle.write(data)
                try? handle.close()
            } else {
                try? data.write(to: url, options: .atomic)
            }
        }
    }

    public static func packetTunnelStartTraceTail(maxChars: Int = 400) -> String? {
        guard let url = packetTunnelStartTraceURL() else { return nil }
        guard let text = try? String(contentsOf: url, encoding: .utf8) else { return nil }
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        if trimmed.count <= maxChars { return trimmed }
        return String(trimmed.suffix(maxChars))
    }

    /// Product-relative secrets folder name under Application Support / bundle.
    public static let appSupportFolderName = "Restore Privacy"

    // MARK: - Path resolution

    /// Real login-user home (not the App Sandbox container home).
    ///
    /// Packet Tunnel system extension runs as root (`getuid()==0`); HOME and
    /// getpwuid(0) are /var/root, which has no entitled device key. Use the
    /// console session owner so HELLO is signed with the same key as host.
    public static func realUserHomeDirectory() -> URL? {
        #if os(macOS)
        var uid = getuid()
        if uid == 0 {
            var st = stat()
            if stat("/dev/console", &st) == 0, st.st_uid != 0 {
                uid = st.st_uid
            }
        }
        if let pw = getpwuid(uid), let dir = pw.pointee.pw_dir {
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
        // Exist alone is not enough: sandboxed/App Group paths can appear on disk
        // but fail Data(contentsOf:) with permission denied — skip those dirs.
        return fileManager.isReadableFile(atPath: c.path)
            && fileManager.isReadableFile(atPath: n.path)
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

    /// Copy residual-required public pin into *writableDir* from package candidates.
    ///
    /// Mirrors Android always-refresh-from-package for the chosen ``pubName``.
    /// When residual host needs RO/DE pin and App Support only has Iceland
    /// ``node_elgamal.pub``, this refreshes ``exit_node_`` from bundle
    /// inject paths before HELLO. Fail closed if still missing (never substitute IS pin).
    @discardableResult
    public static func ensureResidualPubInWritableDir(
        writableDir: URL,
        residualHost: String,
        candidates: [URL],
        fileManager: FileManager = .default
    ) throws -> URL {
        let pubName = residualNodePubName(forHost: residualHost)
        let dest = writableDir.appendingPathComponent(pubName)
        try fileManager.createDirectory(at: writableDir, withIntermediateDirectories: true)

        var source: URL?
        for d in candidates {
            let c = d.appendingPathComponent(pubName)
            if fileManager.fileExists(atPath: c.path) {
                if let attrs = try? fileManager.attributesOfItem(atPath: c.path),
                   let size = attrs[.size] as? NSNumber, size.intValue >= 32 {
                    source = c
                    break
                }
            }
        }

        if let source {
            if source.path != dest.path {
                if fileManager.fileExists(atPath: dest.path) {
                    try? fileManager.removeItem(at: dest)
                }
                try fileManager.copyItem(at: source, to: dest)
            }
            return dest
        }

        if fileManager.fileExists(atPath: dest.path) {
            return dest
        }
        if pubName != nodePubName {
            throw RptProtocol.ProtocolError(
                "Missing \(pubName) for residual host \(residualHost.isEmpty ? "(unknown)" : residualHost) "
                    + "— refuse Iceland entry pub fallback (DE/RO HELLO would use wrong key)"
            )
        }
        throw RptProtocol.ProtocolError("Missing \(pubName) in \(writableDir.path)")
    }

    /// Load product admission material (device client priv + node pub). Never loads node private key.
    /// Ensures RO/DE residual pins are refreshed from package candidates into the writable dir
    /// (App Support may only have been seeded with Iceland ``node_elgamal.pub``).
    ///
    /// Tries each trusted secrets directory in order and **skips** unreadable dirs
    /// (permission / TCC) so Connect does not die on the first blocked path.
    public static func loadAdmissionMaterial(
        fileManager: FileManager = .default,
        bundle: Bundle = .main,
        residualHost: String = ""
    ) throws -> (clientPriv: Data, nodePub: Data) {
        let candidates = Array(
            candidateSecretsDirectories(fileManager: fileManager, bundle: bundle)
        )
        var lastError: Error?

        // Prefer dirs that already look complete and readable.
        for dir in candidates {
            if isPackageReadonlySecretsDir(dir, bundle: bundle, fileManager: fileManager) {
                continue
            }
            guard dirHasClientSecrets(dir, fileManager: fileManager) else { continue }
            do {
                try ensureResidualPubInWritableDir(
                    writableDir: dir,
                    residualHost: residualHost,
                    candidates: candidates,
                    fileManager: fileManager
                )
                return try loadFromDirectory(dir, residualHost: residualHost)
            } catch {
                lastError = error
                continue
            }
        }

        // Seed App Support / App Group / home then retry readable load.
        let seedAttempts: [() throws -> URL?] = [
            { try seedApplicationSupportFromBundleIfNeeded(fileManager: fileManager, bundle: bundle) },
            { try seedAppGroupFromKnownSourcesIfNeeded(fileManager: fileManager, bundle: bundle) },
            { try seedHomeRestorePrivacyFromKnownSourcesIfNeeded(fileManager: fileManager, bundle: bundle) },
        ]
        for seed in seedAttempts {
            guard let dir = try? seed() else { continue }
            do {
                try ensureResidualPubInWritableDir(
                    writableDir: dir,
                    residualHost: residualHost,
                    candidates: candidates,
                    fileManager: fileManager
                )
                return try loadFromDirectory(dir, residualHost: residualHost)
            } catch {
                lastError = error
                continue
            }
        }

        if let dest = secretsDirectory(fileManager: fileManager) {
            var nodeSrc: URL?
            let want = residualNodePubName(forHost: residualHost)
            let names = (want == nodePubName) ? [nodePubName] : [want]
            for d in candidates {
                for name in names {
                    let n = d.appendingPathComponent(name)
                    if fileManager.isReadableFile(atPath: n.path) {
                        nodeSrc = n
                        break
                    }
                }
                if nodeSrc != nil { break }
            }
            if let nodeSrc {
                do {
                    _ = try ensureDeviceAdmissionKey(in: dest, nodePubSource: nodeSrc, fileManager: fileManager)
                    try ensureResidualPubInWritableDir(
                        writableDir: dest,
                        residualHost: residualHost,
                        candidates: candidates,
                        fileManager: fileManager
                    )
                    return try loadFromDirectory(dest, residualHost: residualHost)
                } catch {
                    lastError = error
                }
            }
        }

        let paths = searchedPathsDescription(fileManager: fileManager, bundle: bundle)
        if let lastError {
            throw RptProtocol.ProtocolError(
                "\(lastError.localizedDescription) — also missing readable residual pin for host "
                    + "\(residualHost.isEmpty ? "default" : residualHost). Searched: \(paths)"
            )
        }
        throw RptProtocol.ProtocolError(
            "Missing residual public pin for host \(residualHost.isEmpty ? "default" : residualHost) — "
                + "packages ship node/exit pubs; device Ed25519 is generated on first run. "
                + "Never ship node_elgamal.priv. Searched: \(paths)"
        )
    }

    public static func loadFromDirectory(_ dir: URL) throws -> (clientPriv: Data, nodePub: Data) {
        try loadFromDirectory(dir, residualHost: "")
    }

    public static func loadFromDirectory(
        _ dir: URL,
        residualHost: String
    ) throws -> (clientPriv: Data, nodePub: Data) {
        let cURL = dir.appendingPathComponent(clientPrivName)
        let pubName = residualNodePubName(forHost: residualHost)
        let nURL = dir.appendingPathComponent(pubName)
        if !FileManager.default.fileExists(atPath: nURL.path) {
            if pubName != nodePubName {
                throw RptProtocol.ProtocolError(
                    "Missing \(pubName) for residual host \(residualHost.isEmpty ? "(unknown)" : residualHost) "
                        + "— refuse Iceland entry pub fallback (DE/RO HELLO would use wrong key)"
                )
            }
            throw RptProtocol.ProtocolError("Missing \(pubName) in \(dir.path)")
        }
        let clientPriv: Data
        let nodePub: Data
        do {
            clientPriv = try Data(contentsOf: cURL)
            nodePub = try Data(contentsOf: nURL)
        } catch {
            throw RptProtocol.ProtocolError(
                "Cannot read secrets in \(dir.path): \(error.localizedDescription)"
            )
        }
        guard clientPriv.count == 32 else {
            throw RptProtocol.ProtocolError("client_ed25519.priv must be 32 raw bytes")
        }
        guard nodePub.count == 256 else {
            throw RptProtocol.ProtocolError("\(pubName) must be 256 bytes")
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
        // Catalog residual pubs (RO/DE) — Packet Tunnel HELLO needs these in App Group
        let candidates = Array(
            candidateSecretsDirectories(fileManager: fileManager, bundle: bundle)
        )
        seedCatalogPublicKeys(into: dest, candidates: candidates, fileManager: fileManager)
        let privDest = dest.appendingPathComponent(clientPrivName)
        if let privSrc, !fileManager.fileExists(atPath: privDest.path) {
            try fileManager.copyItem(at: privSrc, to: privDest)
        }
        if !fileManager.fileExists(atPath: privDest.path) {
            _ = try ensureDeviceAdmissionKey(in: dest, nodePubSource: nodeSrc, fileManager: fileManager)
        }
        return dirHasClientSecrets(dest, fileManager: fileManager) ? dest : nil
    }

    /// Seed `~/.restore-privacy/secrets` for Packet Tunnel when host cannot use App Groups.
    ///
    /// Mac Team residual host profiles often authorize Network Extension but omit
    /// `application-groups`. The sandboxed appex still has a home-relative
    /// temporary-exception for `.restore-privacy/`, so this is the residual
    /// host→appex secrets path without App Group on the host.
    @discardableResult
    public static func seedHomeRestorePrivacyFromKnownSourcesIfNeeded(
        fileManager: FileManager = .default,
        bundle: Bundle = .main
    ) throws -> URL? {
        guard let realHome = realUserHomeDirectory() else { return nil }
        let dest = realHome
            .appendingPathComponent(".restore-privacy", isDirectory: true)
            .appendingPathComponent("secrets", isDirectory: true)
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
        var privSrc: URL?
        for dir in candidateSecretsDirectories(fileManager: fileManager, bundle: bundle) {
            if isPackageReadonlySecretsDir(dir, bundle: bundle, fileManager: fileManager) {
                continue
            }
            if dir.standardizedFileURL.path == dest.standardizedFileURL.path { continue }
            let c = dir.appendingPathComponent(clientPrivName)
            if fileManager.fileExists(atPath: c.path) {
                privSrc = c
                break
            }
        }
        guard let nodeSrc else {
            // Fall back to bundle Resources/secrets/node_elgamal.pub
            if let res = bundle.resourceURL?
                .appendingPathComponent("secrets", isDirectory: true)
                .appendingPathComponent(nodePubName),
               fileManager.fileExists(atPath: res.path) {
                return try ensureDeviceAdmissionKey(in: dest, nodePubSource: res, fileManager: fileManager)
            }
            return nil
        }
        try fileManager.createDirectory(at: dest, withIntermediateDirectories: true)
        let nodeDest = dest.appendingPathComponent(nodePubName)
        if !fileManager.fileExists(atPath: nodeDest.path) {
            try fileManager.copyItem(at: nodeSrc, to: nodeDest)
        }
        // Catalog residual pubs (RO/DE) for Packet Tunnel home-relative secrets path
        let candidates = Array(
            candidateSecretsDirectories(fileManager: fileManager, bundle: bundle)
        )
        seedCatalogPublicKeys(into: dest, candidates: candidates, fileManager: fileManager)
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
