import Foundation

/// Host/extension connect sequence: secrets → RPT2 handshake.
/// Used by Packet Tunnel and host channel fallback.
/// No public-IP geo admission (removed for privacy; device keys + crypto only).
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
        host: String = RptEndpoint.host,
        port: UInt16 = RptEndpoint.port,
        secretsDir: URL? = nil,
        timeout: TimeInterval = 15
    ) -> ConnectOutcome {
        let target = "\(host):\(port)"

        // 1. Load secrets (client priv + residual host pub pin).
        // Must pass residualHost so US/RO HELLO uses us_node/exit_node_elgamal.pub —
        // Iceland node_elgamal.pub against 5.161.242.85 yields UDP receive timeout.
        let material: (Data, Data)
        do {
            if let secretsDir {
                material = try RptSecrets.loadFromDirectory(secretsDir, residualHost: host)
            } else {
                material = try RptSecrets.loadAdmissionMaterial(residualHost: host)
            }
        } catch {
            return ConnectOutcome(
                ok: false,
                message: "\(error.localizedDescription) [node \(target)]",
                vpnIp: nil,
                session: nil,
                engine: nil
            )
        }

        // 2. RPT2 handshake against product node
        do {
            let engine = try RptClientEngine(clientPrivRaw: material.0, nodeElgamalPubRaw: material.1)
            let session = try engine.handshake(host: host, port: port, timeout: timeout)
            let msg = "Connected — tunnel IP \(session.vpnIp) via \(target)"
            return ConnectOutcome(
                ok: true,
                message: msg,
                vpnIp: session.vpnIp,
                session: session,
                engine: engine
            )
        } catch {
            var detail = error.localizedDescription
            // Product residual nodes require paid device entitlement and silent-drop
            // unpaid HELLO (no SERVER_HELLO). Surface keygen as the primary next step
            // so support exports are not a bare UDP timeout.
            let low = detail.lowercased()
            if low.contains("udp receive timeout") || low.contains("udp receive failed") {
                detail =
                    "\(detail) — residual HELLO got no reply from \(target). "
                    + "Product residual nodes refuse HELLO until this device is bound to an "
                    + "active paid entitlement. If you just paid: enter the keygen from your "
                    + "fulfilment email (unlock dialog or Settings → Payment entitlement / keygen), "
                    + "then Connect again."
            }
            return ConnectOutcome(
                ok: false,
                message: "Connect failed to \(target): \(detail)",
                vpnIp: nil,
                session: nil,
                engine: nil
            )
        }
    }
}
