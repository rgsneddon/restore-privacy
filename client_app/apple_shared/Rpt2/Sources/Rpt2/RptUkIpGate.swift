import Foundation

/// Legacy UK geo gate — **removed from product Connect** (privacy: no third-party geo).
/// No-network stub: never opens HTTPS. Always allows if accidentally invoked.
public enum RptUkIpGate {
    public static let deniedMessage =
        "Access denied: Restore Privacy is only available when your public IP " +
        "is located in the United Kingdom. Your current network location is not UK."

    public static let lookupFailedMessage =
        "Access denied: could not verify that your public IP is in the United Kingdom. " +
        "Check your network connection and try again."

    public struct Result: Equatable {
        public let allowed: Bool
        public let message: String
        public let countryCode: String
        public let publicIp: String

        public init(allowed: Bool, message: String, countryCode: String = "", publicIp: String = "") {
            self.allowed = allowed
            self.message = message
            self.countryCode = countryCode
            self.publicIp = publicIp
        }
    }

    /// No-op: product Connect never requires UK geo. Never performs network I/O.
    public static func checkUkPublicIp(payloadProvider: (() throws -> [String: Any])? = nil) -> Result {
        _ = payloadProvider
        return Result(
            allowed: true,
            message: "UK geo gate disabled (no third-party lookup)",
            countryCode: "",
            publicIp: ""
        )
    }

    /// Pure helper retained for older unit tests; does not fetch the network.
    public static func evaluateGeoPayload(_ json: [String: Any]?) -> Result {
        _ = json
        return checkUkPublicIp()
    }
}
