import Foundation

/// Full-tunnel honesty: residual public IP only changes when the OS Packet Tunnel
/// is active. Host-side RPT2 HELLO alone must never be reported as product success.
public enum RptFullTunnelResult {
    /// System VPN did not come up — residual ISP IP is expected.
    /// Free monopin residual-capable: Allow / System Settings first (not Team re-sign).
    public static let packetTunnelNotActiveMessage =
        "System VPN (Packet Tunnel) did not become active — residual public IP will not "
        + "change. Open System Settings → Network → VPN & Filters, enable Restore Privacy, "
        + "choose Allow if macOS asks (also check Login Items & Extensions), then press "
        + "Connect again in the app. Do not add L2TP, Cisco IPsec, or IKEv2."

    /// Node HELLO succeeded but no system tunnel — residual IP unchanged.
    /// Assigned node IP proves entitlement (trial/KEYGEN) is live — not trial expiry.
    public static let hostOnlyHelloNotFullTunnelMessage =
        "Node session was assigned but the system Packet Tunnel is not carrying traffic — "
        + "residual public IP is unchanged. Full-tunnel requires an active OS VPN extension. "
        + "Open System Settings → Network → VPN & Filters, enable Restore Privacy, Allow if "
        + "prompted, then Connect again. This is not a trial or KEYGEN failure when a node "
        + "IP was assigned."

    /// True missing-host-NE builds only (not residual-capable free monopin).
    public static let missingHostNeEntitlementMessage =
        "This app build cannot register or activate Packet Tunnel: the host is missing the "
        + "packet-tunnel-provider Network Extension entitlement. Re-download the latest free "
        + "macOS package, or on a developer Mac re-sign with scripts/sign_macos_residual_team.py."

    /// Product residual success with IPv6 ISP leak mitigation installed in Packet Tunnel.
    public static let ipv6IspPathBlockedMessage =
        "Connected — VPN active; IPv6 ISP path blocked"

    /// Honest Connected card line from session dual-stack residual flags.
    /// Never claims "IPv6 ISP path blocked" when residual IPv6 protection is off.
    public static func connectedHonestyMessage(
        vpnIp: String? = nil,
        ipv4Residual: Bool = true,
        ipv6Protected: Bool = true
    ) -> String {
        let ip = (vpnIp ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let suffix = ip.isEmpty ? "" : " (\(ip))"
        if ipv4Residual && ipv6Protected {
            return ipv6IspPathBlockedMessage + suffix
        }
        if ipv4Residual && !ipv6Protected {
            return "Connected — IPv4 via VPN; IPv6 not protected" + suffix
        }
        if !ipv4Residual && ipv6Protected {
            return "Connected — IPv4 residual off; IPv6 ISP path blocked" + suffix
        }
        return "Connected — residual dual-stack off" + suffix
    }

    /// Build the method-channel map for a full-tunnel product connect attempt.
    /// - Parameter packetTunnelActive: true only when NE tunnel status is connected.
    /// - Parameter hostOnlyHello: true when map describes a diagnostic HELLO (never success).
    /// - Parameter ipv6Protected: true when Packet Tunnel installs IPv6 ISP mitigation
    ///   (default-route capture / blackhole intent). Node residual remains IPv4 session.
    /// - Parameter ipv4Residual: true when Packet Tunnel captures full IPv4 residual traffic.
    public static func productConnectMap(
        packetTunnelActive: Bool,
        vpnIp: String? = nil,
        detailMessage: String? = nil,
        hostOnlyHello: Bool = false,
        nodeDiagnostic: String? = nil,
        ipv6Protected: Bool = true,
        ipv4Residual: Bool = true
    ) -> [String: Any] {
        let ip = (vpnIp ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if packetTunnelActive && !hostOnlyHello {
            let base: String
            if let d = detailMessage?.trimmingCharacters(in: .whitespacesAndNewlines),
               !d.isEmpty,
               (d.lowercased().contains("ipv6")
                || d.lowercased().contains("dual-stack")
                || d.lowercased().contains("residual off")) {
                // Trust an already-honest dual-stack detail from the Packet Tunnel.
                base = d
            } else {
                base = connectedHonestyMessage(
                    vpnIp: ip.isEmpty ? nil : ip,
                    ipv4Residual: ipv4Residual,
                    ipv6Protected: ipv6Protected
                )
            }
            var m: [String: Any] = [
                "ok": true,
                "message": base,
                "fullTunnelActive": true,
                "hostOnlySession": false,
                "ipv6Protected": ipv6Protected,
                "ipv4Residual": ipv4Residual,
                // Live residual/DNS flags for Flutter leak posture + watchdog.
                "residualCapture": ipv4Residual,
                "dnsTunnelGatewayOnly": true,
                "dnsTunnelOnly": true,
                "dnsServers": ["10.88.0.1"],
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
    /// Residual-capable: HELLO UDP silence / entitlement beats PT tip boilerplate.
    /// Public DevID: explicit missing-host-NE only (not bare sign_macos_residual tips).
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

        // 1) Strict public-DevID missing host NE only.
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

        // 3) Residual-capable: node HELLO/admission failure is primary over PT tips.
        if !node.isEmpty, isNodeHelloAdmissionFailure(node) {
            return primaryNodeConnectFailureMessage(node)
        }

        // 4) Explicit tunnel/NE detail without node HELLO noise.
        if !detail.isEmpty {
            let hasResidualHonesty =
                detailLow.contains("residual public ip")
                || detailLow.contains("did not become active")
                || detailLow.contains("did not become connected")
                || detailLow.contains("system vpn (packet tunnel)")
                || detailLow.contains("packet tunnel did not")
                || detailLow.contains("vpn & filters")
            // Residual-capable: keep tunnel Allow detail; do not prepend Team re-sign tips.
            let base = hasResidualHonesty ? detail : "\(packetTunnelNotActiveMessage) \(detail)"
            if !node.isEmpty, !isRedundantNodeDiagnostic(node: node, detail: base) {
                return "\(base) \(node)"
            }
            return base
        }

        if !node.isEmpty {
            return primaryNodeConnectFailureMessage(node)
        }

        return packetTunnelNotActiveMessage
    }

    /// True only for actual missing-host-NE / public DevID dual-path copy.
    /// Must not match residual-capable PT boilerplate that mentions residual tips.
    public static func isMissingHostNeDetail(_ text: String) -> Bool {
        let m = text.lowercased()
        if m.isEmpty { return false }
        if m.contains("this app build cannot register or activate packet tunnel") {
            return true
        }
        if m.contains("host is missing the packet-tunnel-provider") {
            return true
        }
        if m.contains("public developer id downloads intentionally omit") {
            return true
        }
        if m.contains("needs team residual sign") || m.contains("needsteamresidualsign") {
            return true
        }
        return false
    }

    public static func isNodeHelloAdmissionFailure(_ nodeDiagnostic: String) -> Bool {
        let low = nodeDiagnostic.lowercased()
        if low.isEmpty { return false }
        return low.contains("udp receive timeout")
            || low.contains("udp receive failed")
            || low.contains("no reply")
            || low.contains("payment entitlement")
            || (low.contains("keygen") && low.contains("connect failed"))
    }

    public static func primaryNodeConnectFailureMessage(_ nodeDiagnostic: String) -> String {
        let n = nodeDiagnostic.trimmingCharacters(in: .whitespacesAndNewlines)
        if n.isEmpty { return n }
        let low = n.lowercased()
        if low.contains("udp receive timeout")
            || low.contains("udp receive failed")
            || low.contains("no reply") {
            if low.contains("keygen") || low.contains("entitlement") {
                return n
            }
            return "\(n) — residual HELLO got no reply. Product residual nodes refuse HELLO "
                + "until this device is bound to an active paid entitlement. If you just paid: "
                + "enter the keygen from your fulfilment email (unlock dialog or Settings → "
                + "Payment entitlement / keygen), then Connect again."
        }
        return n
    }

    private static func isRedundantNodeDiagnostic(node: String, detail: String) -> Bool {
        let n = node.lowercased()
        let d = detail.lowercased()
        if n.isEmpty { return true }
        if d.contains(n) { return true }
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
