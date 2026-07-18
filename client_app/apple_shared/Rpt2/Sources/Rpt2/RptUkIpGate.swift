import Foundation

/// UK public-IP security gate — mirrors Python `client/uk_gate.py` / Android `UkIpGate`.
public enum RptUkIpGate {
    public static let deniedMessage =
        "Access denied: Restore Privacy is only available when your public IP " +
        "is located in the United Kingdom. Your current network location is not UK."

    public static let lookupFailedMessage =
        "Access denied: could not verify that your public IP is in the United Kingdom. " +
        "Check your network connection and try again."

    private static let ukCodes: Set<String> = ["GB", "UK", "GG", "JE", "IM"]
    private static let geoURL = URL(string: "https://ipapi.co/json/")!

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

    public static func normalizeCountryCode(_ raw: String?) -> String {
        guard let raw = raw?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty else {
            return ""
        }
        let s = raw.uppercased()
        let names: Set<String> = [
            "UNITED KINGDOM", "GREAT BRITAIN", "ENGLAND", "SCOTLAND", "WALES", "NORTHERN IRELAND",
        ]
        if names.contains(s) { return "GB" }
        if s.count >= 2 {
            return String(s.prefix(2))
        }
        return s
    }

    public static func isUkCountry(_ code: String) -> Bool {
        ukCodes.contains(normalizeCountryCode(code))
    }

    /// Pure decision from geo JSON (testable without network).
    public static func evaluateGeoPayload(_ json: [String: Any]?) -> Result {
        guard let json = json, !json.isEmpty else {
            return Result(allowed: false, message: lookupFailedMessage)
        }
        if let err = json["error"] as? Bool, err {
            return Result(allowed: false, message: lookupFailedMessage)
        }
        if let err = json["error"] as? String, !err.isEmpty {
            return Result(allowed: false, message: lookupFailedMessage)
        }

        var code = ""
        for key in ["country_code", "countryCode", "country"] {
            if let v = json[key] {
                let s = String(describing: v)
                code = normalizeCountryCode(s)
                if !code.isEmpty { break }
            }
        }
        let publicIp: String = {
            if let ip = json["ip"] as? String { return ip }
            if let q = json["query"] as? String { return q }
            return ""
        }()

        if code.isEmpty {
            return Result(allowed: false, message: lookupFailedMessage, publicIp: publicIp)
        }
        if isUkCountry(code) {
            return Result(allowed: true, message: "UK location verified", countryCode: code, publicIp: publicIp)
        }
        return Result(allowed: false, message: deniedMessage, countryCode: code, publicIp: publicIp)
    }

    /// Live check; inject `payloadProvider` in tests.
    public static func checkUkPublicIp(payloadProvider: (() throws -> [String: Any])? = nil) -> Result {
        do {
            let json: [String: Any]
            if let provider = payloadProvider {
                json = try provider()
            } else {
                json = try fetchGeoJson()
            }
            return evaluateGeoPayload(json)
        } catch {
            return Result(allowed: false, message: lookupFailedMessage)
        }
    }

    private static func fetchGeoJson() throws -> [String: Any] {
        var req = URLRequest(url: geoURL, timeoutInterval: 8)
        req.setValue("restore-privacy-client/0.0.5", forHTTPHeaderField: "User-Agent")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        let sem = DispatchSemaphore(value: 0)
        var resultData: Data?
        var resultError: Error?
        let task = URLSession.shared.dataTask(with: req) { data, response, error in
            resultError = error
            resultData = data
            sem.signal()
        }
        task.resume()
        _ = sem.wait(timeout: .now() + 10)
        if let resultError { throw resultError }
        guard let data = resultData else { throw RptProtocol.ProtocolError("empty geo response") }
        let obj = try JSONSerialization.jsonObject(with: data)
        guard let dict = obj as? [String: Any] else {
            throw RptProtocol.ProtocolError("geo response is not a JSON object")
        }
        return dict
    }
}
