// macOS Flutter host — method channel restore_privacy/vpn
// Full-tunnel honesty: product "Connected" only when Packet Tunnel is active.
// Host-side RPT2 HELLO is diagnostic only (never ok:true for residual-IP change).

import Foundation
import FlutterMacOS
import NetworkExtension

enum RptVpnChannel {
  static let name = "restore_privacy/vpn"
  static let providerBundleId = "com.restoreprivacy.restorePrivacyClient.PacketTunnel"

  static func register(with messenger: FlutterBinaryMessenger) {
    // Seed Application Support + App Group so Packet Tunnel can load the same keys.
    _ = try? RptSecrets.seedApplicationSupportFromBundleIfNeeded()
    _ = try? RptSecrets.seedAppGroupFromKnownSourcesIfNeeded()
    let channel = FlutterMethodChannel(name: name, binaryMessenger: messenger)
    channel.setMethodCallHandler { call, result in
      switch call.method {
      case "connect":
        let args = call.arguments as? [String: Any] ?? [:]
        let ep = RptEndpoint.resolve(from: args)
        let fullTunnel = (args["fullTunnel"] as? Bool) ?? true
        connect(host: ep.host, port: ep.port, fullTunnel: fullTunnel, flutterResult: result)
      case "disconnect":
        disconnect { map in result(map) }
      case "hasSecrets":
        result([
          "ok": RptSecrets.filesPresent(),
          "message": RptSecrets.filesPresent()
            ? "Admission secrets found"
            : "Missing admission secrets — searched: \(RptSecrets.searchedPathsDescription())",
        ] as [String: Any])
      default:
        result(FlutterMethodNotImplemented)
      }
    }
  }

  private static func connect(
    host: String,
    port: UInt16,
    fullTunnel: Bool,
    flutterResult: @escaping FlutterResult
  ) {
    // Product path is full tunnel — residual public IP only changes via Packet Tunnel.
    if !fullTunnel {
      // Explicit non-full-tunnel: diagnostic HELLO only (never product success).
      hostSideDiagnostic(host: host, port: port) { map in
        flutterResult(map)
      }
      return
    }

    loadOrCreateManager(host: host, port: port) { manager, neError in
      guard let manager else {
        let detail = neError.map { "NE preferences: \($0)" }
        hostSideDiagnostic(host: host, port: port, detail: detail) { map in
          flutterResult(map)
        }
        return
      }
      startTunnel(manager: manager, host: host, port: port) { map in
        if RptFullTunnelResult.isProductSuccess(map) {
          flutterResult(map)
          return
        }
        // Tunnel not active — optional diagnostic HELLO (still ok:false).
        let detail = map["message"] as? String
        hostSideDiagnostic(host: host, port: port, detail: detail) { diag in
          flutterResult(diag)
        }
      }
    }
  }

  /// Host RPT2 HELLO for diagnostics only — always ok:false for full-tunnel product.
  /// Closes transport immediately; residual public IP does not change.
  private static func hostSideDiagnostic(
    host: String,
    port: UInt16,
    detail: String? = nil,
    completion: @escaping ([String: Any]) -> Void
  ) {
    DispatchQueue.global(qos: .userInitiated).async {
      let outcome = RptConnectOrchestrator.connect(host: host, port: port)
      outcome.engine?.closeTransport()
      let nodeDiag: String?
      if outcome.ok, let ip = outcome.vpnIp {
        nodeDiag = "Node reachable; session assigned \(ip) via \(host):\(port) (HELLO-only, transport closed)."
      } else if !outcome.ok {
        nodeDiag = "Node diagnostic: \(outcome.message)"
      } else {
        nodeDiag = nil
      }
      let map = RptFullTunnelResult.productConnectMap(
        packetTunnelActive: false,
        vpnIp: outcome.vpnIp,
        detailMessage: detail,
        hostOnlyHello: outcome.ok,
        nodeDiagnostic: nodeDiag
      )
      DispatchQueue.main.async { completion(map) }
    }
  }

  private static func loadOrCreateManager(
    host: String,
    port: UInt16,
    completion: @escaping (NETunnelProviderManager?, String?) -> Void
  ) {
    NETunnelProviderManager.loadAllFromPreferences { managers, error in
      if let error {
        completion(nil, error.localizedDescription)
        return
      }
      let manager = managers?.first ?? NETunnelProviderManager()
      let proto = NETunnelProviderProtocol()
      proto.providerBundleIdentifier = providerBundleId
      proto.serverAddress = "\(host):\(port)"
      proto.providerConfiguration = [
        "host": host,
        "port": Int(port),
        "fullTunnel": true,
        "sessionName": "Restore Privacy",
      ]
      manager.protocolConfiguration = proto
      manager.localizedDescription = "Restore Privacy"
      manager.isEnabled = true
      manager.saveToPreferences { saveErr in
        if let saveErr {
          completion(nil, saveErr.localizedDescription)
          return
        }
        manager.loadFromPreferences { loadErr in
          if let loadErr {
            completion(nil, loadErr.localizedDescription)
            return
          }
          completion(manager, nil)
        }
      }
    }
  }

  private static func startTunnel(
    manager: NETunnelProviderManager,
    host: String,
    port: UInt16,
    completion: @escaping ([String: Any]) -> Void
  ) {
    do {
      let session = manager.connection as? NETunnelProviderSession
      let opts: [String: NSObject] = [
        "host": host as NSString,
        "port": NSNumber(value: port),
      ]
      try session?.startTunnel(options: opts)
      // Poll for connected (Packet Tunnel handshake + setTunnelNetworkSettings can take several seconds).
      pollTunnelConnected(manager: manager, attempt: 0, maxAttempts: 20, interval: 0.5) { connected in
        if connected {
          queryProviderVpnIp(manager: manager) { ip in
            var resolved = ip
            if resolved == nil || resolved?.isEmpty == true,
               let cfg = (manager.protocolConfiguration as? NETunnelProviderProtocol)?
                 .providerConfiguration,
               let cfgIp = cfg["vpnIp"] as? String, !cfgIp.isEmpty {
              resolved = cfgIp
            }
            let map = RptFullTunnelResult.productConnectMap(
              packetTunnelActive: true,
              vpnIp: resolved,
              detailMessage: resolved.map { "Connected — tunnel IP \($0)" }
            )
            completion(map)
          }
        } else {
          let st = manager.connection.status.rawValue
          completion(
            RptFullTunnelResult.productConnectMap(
              packetTunnelActive: false,
              detailMessage: "Packet Tunnel start pending or failed (status \(st))."
            )
          )
        }
      }
    } catch {
      completion(
        RptFullTunnelResult.productConnectMap(
          packetTunnelActive: false,
          detailMessage: error.localizedDescription
        )
      )
    }
  }

  private static func pollTunnelConnected(
    manager: NETunnelProviderManager,
    attempt: Int,
    maxAttempts: Int,
    interval: TimeInterval,
    completion: @escaping (Bool) -> Void
  ) {
    if manager.connection.status == .connected {
      completion(true)
      return
    }
    if attempt >= maxAttempts {
      completion(false)
      return
    }
    DispatchQueue.main.asyncAfter(deadline: .now() + interval) {
      pollTunnelConnected(
        manager: manager,
        attempt: attempt + 1,
        maxAttempts: maxAttempts,
        interval: interval,
        completion: completion
      )
    }
  }

  private static func queryProviderVpnIp(
    manager: NETunnelProviderManager,
    completion: @escaping (String?) -> Void
  ) {
    guard let session = manager.connection as? NETunnelProviderSession else {
      completion(nil)
      return
    }
    let msg = Data("status".utf8)
    do {
      try session.sendProviderMessage(msg) { response in
        guard let response,
              let obj = try? JSONSerialization.jsonObject(with: response) as? [String: Any] else {
          completion(nil)
          return
        }
        completion(obj["vpnIp"] as? String)
      }
    } catch {
      completion(nil)
    }
  }

  private static func disconnect(completion: @escaping ([String: Any]) -> Void) {
    NETunnelProviderManager.loadAllFromPreferences { managers, _ in
      managers?.forEach { $0.connection.stopVPNTunnel() }
      completion(["ok": true, "message": "Disconnected"] as [String: Any])
    }
  }
}
