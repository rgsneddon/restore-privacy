import Foundation

/// Full-tunnel honesty: residual public IP only changes when the OS Packet Tunnel
/// is active. Host-side RPT2 HELLO alone must never be reported as product success.
public enum RptFullTunnelResult {
    /// System VPN did not come up — residual ISP IP is expected.
    public static let packetTunnelNotActiveMessage =
        "System VPN (Packet Tunnel) did not become active — your residual public IP "
        + "will not change. Enable Network Extension signing/entitlements and approve "
        + "the VPN configuration, then try again."

    /// Node HELLO succeeded but no system tunnel — residual IP unchanged.
    public static let hostOnlyHelloNotFullTunnelMessage =
        "Node session was assigned but the system Packet Tunnel is not carrying traffic — "
        + "residual public IP is unchanged. Full-tunnel requires an active OS VPN extension."

    /// Build the method-channel map for a full-tunnel product connect attempt.
    /// - Parameter packetTunnelActive: true only when NE tunnel status is connected.
    /// - Parameter hostOnlyHello: true when map describes a diagnostic HELLO (never success).
    public static func productConnectMap(
        packetTunnelActive: Bool,
        vpnIp: String? = nil,
        detailMessage: String? = nil,
        hostOnlyHello: Bool = false,
        nodeDiagnostic: String? = nil
    ) -> [String: Any] {
        let ip = (vpnIp ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if packetTunnelActive && !hostOnlyHello {
            let base: String
            if let d = detailMessage?.trimmingCharacters(in: .whitespacesAndNewlines), !d.isEmpty {
                base = d
            } else if !ip.isEmpty {
                base = "Connected — tunnel IP \(ip)"
            } else {
                base = "Connected — Packet Tunnel active"
            }
            var m: [String: Any] = [
                "ok": true,
                "message": base,
                "fullTunnelActive": true,
                "hostOnlySession": false,
            ]
            if !ip.isEmpty { m["vpnIp"] = ip }
            return m
        }

        var parts: [String] = []
        if hostOnlyHello {
            var line = hostOnlyHelloNotFullTunnelMessage
            if !ip.isEmpty { line += " (node assigned \(ip))" }
            parts.append(line)
        } else {
            parts.append(packetTunnelNotActiveMessage)
        }
        if let d = detailMessage?.trimmingCharacters(in: .whitespacesAndNewlines), !d.isEmpty {
            parts.append(d)
        }
        if let n = nodeDiagnostic?.trimmingCharacters(in: .whitespacesAndNewlines), !n.isEmpty {
            parts.append(n)
        }
        var m: [String: Any] = [
            "ok": false,
            "message": parts.joined(separator: " "),
            "fullTunnelActive": false,
            "hostOnlySession": hostOnlyHello,
        ]
        if !ip.isEmpty { m["vpnIp"] = ip }
        return m
    }

    /// True when a channel map is a product full-tunnel success (mirrors Dart `isConnectSuccess`).
    public static func isProductSuccess(_ map: [String: Any]) -> Bool {
        guard let ok = map["ok"] as? Bool, ok else { return false }
        if let hostOnly = map["hostOnlySession"] as? Bool, hostOnly { return false }
        if let active = map["fullTunnelActive"] as? Bool, active == false { return false }
        return true
    }
}
