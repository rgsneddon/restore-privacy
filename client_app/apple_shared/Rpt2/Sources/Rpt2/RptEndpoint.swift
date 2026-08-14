import Foundation

/// Single source of truth for the product RPT residual catalog (must match Flutter
/// `RptConfig` / `country_select.dart` and monorepo `client.multihop`).
public enum RptEndpoint {
    /// Product default residual entry (Germany monopin).
    public static let host: String = "178.105.187.178"
    /// Iceland residual peer.
    public static let icelandHost: String = "82.221.101.241"
    /// Retired United States residual peer (not dialable).
    public static let usHost: String = "5.161.242.85"
    /// Germany residual peer (default entry / multi-hop exit).
    public static let deHost: String = "178.105.187.178"
    /// Singapore residual peer (selectable entry).
    public static let sgHost: String = "5.223.48.8"

    /// Product UDP listen port (RPT2).
    public static let port: UInt16 = 44044
    /// Status UI HTTP (operator/VPN APP Shop only; not the tunnel).
    public static let statusHttpPort: UInt16 = 8080

    public static var hostPortDescription: String { "\(host):\(port)" }

    /// Live residual catalog hosts (Germany default + Singapore).
    public static let catalogHosts: [String] = [
        deHost,
        sgHost,
    ]

    /// Alternates for wipe-drain / preferred-down failover (never includes preferred).
    public static func alternateHosts(excluding preferred: String) -> [String] {
        let p = preferred.trimmingCharacters(in: .whitespacesAndNewlines)
        return catalogHosts.filter { $0 != p && !$0.isEmpty }
    }

    /// Preferred first, then catalog alternates (deduped). Used by Connect failover.
    public static func connectHostOrder(
        preferred: String,
        alternates: [String]? = nil
    ) -> [String] {
        let pref = preferred.trimmingCharacters(in: .whitespacesAndNewlines)
        var order: [String] = []
        if !pref.isEmpty {
            order.append(pref)
        }
        let alts = (alternates ?? alternateHosts(excluding: pref))
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        for h in alts where !order.contains(h) {
            order.append(h)
        }
        // Always ensure catalog coverage if preferred empty/unknown
        for h in catalogHosts where !order.contains(h) {
            order.append(h)
        }
        return order
    }

    /// True when a connect/start failure looks like residual unreachable (try alternate).
    /// Permission / Team residual / Settings issues must not failover.
    public static func isResidualUnreachableFailure(_ detail: String?) -> Bool {
        let d = (detail ?? "").lowercased()
        if d.isEmpty { return false }
        // Do not failover on NE permission / re-sign issues
        if d.contains("permission")
            || d.contains("not authorized")
            || d.contains("user denied")
            || d.contains("team residual")
            || d.contains("packet-tunnel-provider")
            || d.contains("sign_macos_residual")
            || d.contains("needsvpn")
            || d.contains("system settings")
        {
            return false
        }
        return d.contains("udp receive timeout")
            || d.contains("udp receive failed")
            || d.contains("connect failed")
            || d.contains("timed out")
            || d.contains("timeout")
            || d.contains("could not connect")
            || d.contains("connection refused")
            || d.contains("network is unreachable")
            || d.contains("no route to host")
            || d.contains("host is down")
            || d.contains("handshake")
            || d.contains("residual hello got no reply")
            || d.contains("failed to connect")
            || d.contains("nwerror")
            || d.contains("socket")
    }

    /// Parse MethodChannel args (`host` / `port`) with NSNumber-safe port casting.
    public static func resolve(from args: [String: Any]?) -> (host: String, port: UInt16) {
        let a = args ?? [:]
        let h = (a["host"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
        let hostOut = (h?.isEmpty == false) ? h! : host
        let portOut: UInt16
        if let p = a["port"] as? UInt16 {
            portOut = p
        } else if let p = a["port"] as? Int, p > 0, p <= 65535 {
            portOut = UInt16(p)
        } else if let p = a["port"] as? Int64, p > 0, p <= 65535 {
            portOut = UInt16(p)
        } else if let n = a["port"] as? NSNumber {
            let v = n.intValue
            portOut = (v > 0 && v <= 65535) ? UInt16(v) : port
        } else if let s = a["port"] as? String, let v = UInt16(s) {
            portOut = v
        } else {
            portOut = port
        }
        return (hostOut, portOut)
    }

    /// Optional alternate host list from MethodChannel args.
    public static func alternateHosts(from args: [String: Any]?) -> [String] {
        let a = args ?? [:]
        if let arr = a["alternateHosts"] as? [String] {
            return arr
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty }
        }
        if let arr = a["alternate_hosts"] as? [String] {
            return arr
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty }
        }
        return []
    }
}
