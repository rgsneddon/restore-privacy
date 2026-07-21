import Foundation

/// Single source of truth for the product RPT node endpoint (must match Flutter `RptConfig`
/// and the production node / VPN APP Shop upstream).
public enum RptEndpoint {
    /// Active production RPT node public IPv4 (FlokiNET).
    public static let host: String = "82.221.101.241"
    /// Product UDP listen port (RPT2).
    public static let port: UInt16 = 44044
    /// Status UI HTTP (operator/VPN APP Shop only; not the tunnel).
    public static let statusHttpPort: UInt16 = 8080

    public static var hostPortDescription: String { "\(host):\(port)" }

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
}
