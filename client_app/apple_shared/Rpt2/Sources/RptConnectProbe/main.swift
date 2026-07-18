import Foundation
import Rpt2

/// Host-side connect probe using the same orchestrator as iOS/macOS clients.
@main
struct RptConnectProbe {
    static func main() {
        let env = ProcessInfo.processInfo.environment
        let host = env["RPT_HOST"] ?? RptEndpoint.host
        let port = UInt16(env["RPT_PORT"] ?? "") ?? RptEndpoint.port
        let secretsPath = env["RPT_SECRETS_DIR"]
            ?? (FileManager.default.currentDirectoryPath + "/secrets")
        let skipUk = (env["RPT_SKIP_UK"] ?? "1") == "1"
        print("APPLE_ORCHESTRATOR_CONNECT host=\(host) port=\(port) secrets=\(secretsPath) skipUk=\(skipUk)")
        print("RptEndpoint.default=\(RptEndpoint.hostPortDescription)")
        let dir = URL(fileURLWithPath: secretsPath, isDirectory: true)
        let outcome = RptConnectOrchestrator.connect(
            host: host,
            port: port,
            skipUkGate: skipUk,
            secretsDir: dir,
            timeout: 20
        )
        print("ok=\(outcome.ok)")
        print("message=\(outcome.message)")
        if let ip = outcome.vpnIp {
            print("vpnIp=\(ip)")
        }
        outcome.engine?.closeTransport()
        if !outcome.ok {
            FileHandle.standardError.write(Data("CONNECT_FAILED\n".utf8))
            exit(1)
        }
    }
}
