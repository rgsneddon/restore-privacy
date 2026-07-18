import Foundation

/// Secrets path helpers for Apple platforms.
/// Never load or ship `node_elgamal.priv`.
public enum RptSecrets {
    public static let clientPrivName = "client_ed25519.priv"
    public static let nodePubName = "node_elgamal.pub"
    /// Must never be loaded by product clients.
    public static let nodePrivName = "node_elgamal.priv"

    public static var appGroupId: String { "group.com.restoreprivacy.shared" }

    public static func secretsDirectory(fileManager: FileManager = .default) -> URL? {
        if let base = fileManager.containerURL(forSecurityApplicationGroupIdentifier: appGroupId) {
            return base.appendingPathComponent("secrets", isDirectory: true)
        }
        #if os(macOS)
        return fileManager.homeDirectoryForCurrentUser
            .appendingPathComponent(".restore-privacy/secrets", isDirectory: true)
        #else
        if let support = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first {
            return support.appendingPathComponent("restore-privacy/secrets", isDirectory: true)
        }
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
        guard let c = clientPrivateKeyURL(fileManager: fileManager),
              let n = nodePublicKeyURL(fileManager: fileManager) else { return false }
        return fileManager.fileExists(atPath: c.path) && fileManager.fileExists(atPath: n.path)
    }

    /// Load product admission material only (client priv + node pub). Never loads node private key.
    public static func loadAdmissionMaterial(fileManager: FileManager = .default) throws -> (clientPriv: Data, nodePub: Data) {
        guard let cURL = clientPrivateKeyURL(fileManager: fileManager),
              let nURL = nodePublicKeyURL(fileManager: fileManager) else {
            throw RptProtocol.ProtocolError("secrets directory unavailable")
        }
        // Explicitly refuse node private key path
        if let dir = secretsDirectory(fileManager: fileManager) {
            let forbidden = dir.appendingPathComponent(nodePrivName)
            // Do not read forbidden even if present
            _ = forbidden
        }
        guard fileManager.fileExists(atPath: cURL.path),
              fileManager.fileExists(atPath: nURL.path) else {
            throw RptProtocol.ProtocolError(
                "Missing admission secrets — place client_ed25519.priv and " +
                "node_elgamal.pub under app secrets (never node_elgamal.priv)"
            )
        }
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

    public static func loadFromDirectory(_ dir: URL) throws -> (clientPriv: Data, nodePub: Data) {
        let cURL = dir.appendingPathComponent(clientPrivName)
        let nURL = dir.appendingPathComponent(nodePubName)
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
}
