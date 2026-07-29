import Foundation

/// Full-tunnel honesty: residual public IP only changes when the OS Packet Tunnel
/// is active. Host-side RPT2 HELLO alone must never be reported as product success.
public enum RptFullTunnelResult {
    /// System VPN did not come up — residual ISP IP is expected.
    /// End-user Allow path first; Team residual re-sign is operator/dev guidance.
    public static let packetTunnelNotActiveMessage =
        "System VPN (Packet Tunnel) did not become active — residual public IP will not "
        + "change. Allow VPN for Restore Privacy in System Settings → Network → VPN & Filters "
        + "(and Login Items & Extensions if prompted). Settings opens when possible — then "
        + "press Connect again. Residual Packet Tunnel needs a Team-signed host + appex with "
        + "Network Extension (developers: scripts/sign_macos_residual_team.py)."

    /// Node HELLO succeeded but no system tunnel — residual IP unchanged.
    public static let hostOnlyHelloNotFullTunnelMessage =
        "Node session was assigned but the system Packet Tunnel is not carrying traffic — "
        + "residual public IP is unchanged. Full-tunnel requires an active OS VPN extension. "
        + "Approve VPN configuration in System Settings → Network → VPN & Filters, then Connect again."

    /// Product residual success with IPv6 ISP leak mitigation installed in Packet Tunnel.
    public static let ipv6IspPathBlockedMessage =
        "Connected — VPN active; IPv6 ISP path blocked"

    /// Build the method-channel map for a full-tunnel product connect attempt.
    /// - Parameter packetTunnelActive: true only when NE tunnel status is connected.
    /// - Parameter hostOnlyHello: true when map describes a diagnostic HELLO (never success).
    /// - Parameter ipv6Protected: true when Packet Tunnel installs IPv6 ISP mitigation
    ///   (default-route capture / blackhole intent). Node residual remains IPv4 session.
    public static func productConnectMap(
        packetTunnelActive: Bool,
        vpnIp: String? = nil,
        detailMessage: String? = nil,
        hostOnlyHello: Bool = false,
        nodeDiagnostic: String? = nil,
        ipv6Protected: Bool = true
    ) -> [String: Any] {
        let ip = (vpnIp ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if packetTunnelActive && !hostOnlyHello {
            let base: String
            if let d = detailMessage?.trimmingCharacters(in: .whitespacesAndNewlines),
               !d.isEmpty,
               d.lowercased().contains("ipv6") {
                base = d
            } else if ipv6Protected {
                base = !ip.isEmpty
                    ? "\(ipv6IspPathBlockedMessage) (\(ip))"
                    : ipv6IspPathBlockedMessage
            } else if !ip.isEmpty {
                base = "Connected — IPv4 via VPN; IPv6 not protected (\(ip))"
            } else {
                base = "Connected — IPv4 via VPN; IPv6 not protected"
            }
            var m: [String: Any] = [
                "ok": true,
                "message": base,
                "fullTunnelActive": true,
                "hostOnlySession": false,
                "ipv6Protected": ipv6Protected,
            ]
            if !ip.isEmpty { m["vpnIp"] = ip }
            return m
        }

        let message = composeConnectFailurePrimaryMessage(
            hostOnlyHello: hostOnlyHello,
            vpnIp: ip.isEmpty ? nil : ip,
            detailMessage: detailMessage,
            nodeDiagnostic: nodeDiagnostic
        )
        var m: [String: Any] = [
            "ok": false,
            "message": message,
            "fullTunnelActive": false,
            "hostOnlySession": hostOnlyHello,
        ]
        if !ip.isEmpty { m["vpnIp"] = ip }
        return m
    }

    /// Single primary root-cause for Connect failure (support export + UI).
    /// Avoid stacking missing-host-NE + Allow-Settings + UDP timeout walls of text.
    public static func composeConnectFailurePrimaryMessage(
        hostOnlyHello: Bool,
        vpnIp: String? = nil,
        detailMessage: String? = nil,
        nodeDiagnostic: String? = nil
    ) -> String {
        let detail = (detailMessage ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let node = (nodeDiagnostic ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let ip = (vpnIp ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let detailLow = detail.lowercased()
        let nodeLow = node.lowercased()

        // 1) Missing host NE / Team residual re-sign — only that path (Settings cannot fix).
        if isMissingHostNeDetail(detail) || isMissingHostNeDetail(node) {
            if !detail.isEmpty, isMissingHostNeDetail(detail) {
                return detail
            }
            if !node.isEmpty, isMissingHostNeDetail(node) {
                return node
            }
            return detail.isEmpty ? packetTunnelNotActiveMessage : detail
        }

        // 2) Host-only HELLO (node up, no system tunnel).
        if hostOnlyHello {
            var line = hostOnlyHelloNotFullTunnelMessage
            if !ip.isEmpty { line += " (node assigned \(ip))" }
            if !detail.isEmpty, !line.lowercased().contains(detailLow) {
                line += " \(detail)"
            }
            return line
        }

        // 3) Explicit NE/tunnel detail without node noise.
        if !detail.isEmpty {
            let hasResidualHonesty =
                detailLow.contains("residual public ip")
                || detailLow.contains("did not become active")
                || detailLow.contains("system vpn (packet tunnel)")
            let base = hasResidualHonesty ? detail : "\(packetTunnelNotActiveMessage) \(detail)"
            if !node.isEmpty, !isRedundantNodeDiagnostic(node: node, detail: base) {
                if hasResidualHonesty,
                   detailLow.contains("did not become") || detailLow.contains("system vpn") {
                    return base
                }
                return "\(base) \(node)"
            }
            return base
        }

        // 4) Node HELLO failure alone (residual-capable host, tunnel not up).
        if !node.isEmpty {
            // Prefix brief PT context so export is residual-honest, not bare node timeout.
            if nodeLow.contains("udp receive timeout") || nodeLow.contains("connect failed to") {
                return "\(packetTunnelNotActiveMessage) \(node)"
            }
            return "\(packetTunnelNotActiveMessage) \(node)"
        }

        return packetTunnelNotActiveMessage
    }

    /// True when text is missing host packet-tunnel-provider / Team residual re-sign class.
    public static func isMissingHostNeDetail(_ text: String) -> Bool {
        let m = text.lowercased()
        if m.isEmpty { return false }
        return m.contains("packet-tunnel-provider")
            || m.contains("sign_macos_residual")
            || m.contains("team residual")
            || m.contains("needs team residual")
            || (m.contains("host is missing") && m.contains("network extension"))
            || m.contains("public developer id downloads intentionally omit")
    }

    private static func isRedundantNodeDiagnostic(node: String, detail: String) -> Bool {
        let n = node.lowercased()
        let d = detail.lowercased()
        if n.isEmpty { return true }
        if d.contains(n) { return true }
        // When detail already says missing host NE, UDP/HELLO noise is redundant.
        if isMissingHostNeDetail(detail) { return true }
        return false
    }

    /// True when a channel map is a product full-tunnel success (mirrors Dart `isConnectSuccess`).
    public static func isProductSuccess(_ map: [String: Any]) -> Bool {
        guard let ok = map["ok"] as? Bool, ok else { return false }
        if let hostOnly = map["hostOnlySession"] as? Bool, hostOnly { return false }
        if let active = map["fullTunnelActive"] as? Bool, active == false { return false }
        return true
    }

    /// Result of stopping the system Packet Tunnel (channel disconnect / app quit).
    /// Not a product connect success — residual public IP is expected after NE stops.
    public static func disconnectResultMap(
        message: String = "Disconnected — system VPN stopped; residual public IP restored"
    ) -> [String: Any] {
        [
            "ok": true,
            "message": message,
            "fullTunnelActive": false,
            "hostOnlySession": false,
        ]
    }
}
