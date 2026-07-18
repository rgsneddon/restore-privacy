import Foundation

/// Host/extension connect sequence: UK gate → secrets → RPT2 handshake.
/// Used by Packet Tunnel and host channel fallback.
public enum RptConnectOrchestrator {
    public struct ConnectOutcome {
        public let ok: Bool
        public let message: String
        public let vpnIp: String?
        public let session: RptClientEngine.Session?
        public let engine: RptClientEngine?

        public init(
            ok: Bool,
            message: String,
            vpnIp: String?,
            session: RptClientEngine.Session?,
            engine: RptClientEngine?
        ) {
            self.ok = ok
            self.message = message
            self.vpnIp = vpnIp
            self.session = session
            self.engine = engine
        }

        public var resultMap: [String: Any] {
            var m: [String: Any] = ["ok": ok, "message": message]
            if let vpnIp { m["vpnIp"] = vpnIp }
            return m
        }
    }

    public static func connect(
        host: String = "104.156.224.47",
        port: UInt16 = 44044,
        skipUkGate: Bool = false,
        ukGateFetcher: (() throws -> [String: Any])? = nil,
        secretsDir: URL? = nil,
        timeout: TimeInterval = 15
    ) -> ConnectOutcome {
        // 1. UK IP gate (fail closed)
        if !skipUkGate {
            let gate = RptUkIpGate.checkUkPublicIp(payloadProvider: ukGateFetcher)
            if !gate.allowed {
                return ConnectOutcome(ok: false, message: gate.message, vpnIp: nil, session: nil, engine: nil)
            }
        }

        // 2. Load secrets (client priv + node pub only)
        let material: (Data, Data)
        do {
            if let secretsDir {
                material = try RptSecrets.loadFromDirectory(secretsDir)
            } else {
                material = try RptSecrets.loadAdmissionMaterial()
            }
        } catch {
            return ConnectOutcome(
                ok: false,
                message: error.localizedDescription,
                vpnIp: nil,
                session: nil,
                engine: nil
            )
        }

        // 3. RPT2 handshake
        do {
            let engine = try RptClientEngine(clientPrivRaw: material.0, nodeElgamalPubRaw: material.1)
            let session = try engine.handshake(host: host, port: port, timeout: timeout)
            let msg = "Connected — tunnel IP \(session.vpnIp)"
            return ConnectOutcome(
                ok: true,
                message: msg,
                vpnIp: session.vpnIp,
                session: session,
                engine: engine
            )
        } catch {
            return ConnectOutcome(
                ok: false,
                message: "Connect failed: \(error.localizedDescription)",
                vpnIp: nil,
                session: nil,
                engine: nil
            )
        }
    }
}
