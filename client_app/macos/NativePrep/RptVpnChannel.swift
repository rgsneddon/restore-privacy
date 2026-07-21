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
    // Seed Application Support + App Group + ~/.restore-privacy so Packet Tunnel
    // can load keys (Team residual host profile may omit application-groups;
    // sandboxed appex still reads home via temporary-exception).
    _ = try? RptSecrets.seedApplicationSupportFromBundleIfNeeded()
    _ = try? RptSecrets.seedAppGroupFromKnownSourcesIfNeeded()
    _ = try? RptSecrets.seedHomeRestorePrivacyFromKnownSourcesIfNeeded()
    let channel = FlutterMethodChannel(name: name, binaryMessenger: messenger)
    channel.setMethodCallHandler { call, result in
      switch call.method {
      case "connect":
        let args = call.arguments as? [String: Any] ?? [:]
        let ep = RptEndpoint.resolve(from: args)
        let fullTunnel = (args["fullTunnel"] as? Bool) ?? true
        connect(host: ep.host, port: ep.port, fullTunnel: fullTunnel, flutterResult: result)
      case "disconnect":
        // Same stop path as app-quit / terminate hooks.
        stopAllTunnels { map in result(map) }
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

  /// Prefer our saved manager; never reuse an unrelated VPN config.
  private static func selectOrCreateManager(
    from managers: [NETunnelProviderManager]?
  ) -> NETunnelProviderManager {
    if let existing = managers?.first(where: { shouldStopManager($0) }) {
      return existing
    }
    return NETunnelProviderManager()
  }

  /// Human-readable NEVPNStatus for failure messages.
  private static func statusName(_ status: NEVPNStatus) -> String {
    switch status {
    case .invalid: return "invalid"
    case .disconnected: return "disconnected"
    case .connecting: return "connecting"
    case .connected: return "connected"
    case .reasserting: return "reasserting"
    case .disconnecting: return "disconnecting"
    @unknown default: return "unknown(\(status.rawValue))"
    }
  }

  /// Surface permission / entitlement failures with an actionable residual-honest path.
  private static func describeNePreferencesError(_ error: Error) -> String {
    let ns = error as NSError
    let base = error.localizedDescription
    let domain = ns.domain
    let code = ns.code
    // Common when host lacks Network Extension entitlement / profile, or user denied VPN config.
    let lower = base.lowercased()
    if lower.contains("permission")
      || lower.contains("not authorized")
      || lower.contains("denied")
      || domain == NEVPNErrorDomain
    {
      return
        "NE preferences failed (\(domain) \(code)): \(base). "
        + "Approve VPN configuration in System Settings → Network → VPN & Filters "
        + "(or General → Login Items & Extensions), and ensure this build is Team-signed "
        + "with Packet Tunnel Network Extension entitlements on host + appex "
        + "(see scripts/sign_macos_residual_team.py)."
    }
    return "NE preferences failed (\(domain) \(code)): \(base)"
  }

  private static func loadOrCreateManager(
    host: String,
    port: UInt16,
    completion: @escaping (NETunnelProviderManager?, String?) -> Void
  ) {
    NETunnelProviderManager.loadAllFromPreferences { managers, error in
      if let error {
        completion(nil, describeNePreferencesError(error))
        return
      }
      let manager = selectOrCreateManager(from: managers)
      let proto = NETunnelProviderProtocol()
      proto.providerBundleIdentifier = providerBundleId
      proto.serverAddress = "\(host):\(port)"
      // DisconnectOnSleep false so residual session survives lid close while allowed by OS.
      proto.disconnectOnSleep = false
      proto.providerConfiguration = [
        "host": host,
        "port": Int(port),
        "fullTunnel": true,
        "sessionName": "Restore Privacy",
      ]
      manager.protocolConfiguration = proto
      manager.localizedDescription = "Restore Privacy"
      manager.isEnabled = true
      manager.isOnDemandEnabled = false
      manager.saveToPreferences { saveErr in
        if let saveErr {
          completion(nil, describeNePreferencesError(saveErr))
          return
        }
        // Required after save so connection/session objects are valid for startTunnel.
        manager.loadFromPreferences { loadErr in
          if let loadErr {
            completion(nil, describeNePreferencesError(loadErr))
            return
          }
          // Ensure enabled after reload (some macOS versions clear it).
          if !manager.isEnabled {
            manager.isEnabled = true
            manager.saveToPreferences { reSaveErr in
              if let reSaveErr {
                completion(nil, describeNePreferencesError(reSaveErr))
                return
              }
              manager.loadFromPreferences { reLoadErr in
                if let reLoadErr {
                  completion(nil, describeNePreferencesError(reLoadErr))
                  return
                }
                completion(manager, nil)
              }
            }
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
      guard let session else {
        completion(
          RptFullTunnelResult.productConnectMap(
            packetTunnelActive: false,
            detailMessage:
              "NETunnelProviderSession missing — host build may lack Network Extension "
              + "packet-tunnel-provider entitlement/profile (Team residual sign required)."
          )
        )
        return
      }
      // Already connected (re-entrant Connect) — treat as success.
      if manager.connection.status == .connected {
        queryProviderVpnIp(manager: manager) { ip in
          let map = RptFullTunnelResult.productConnectMap(
            packetTunnelActive: true,
            vpnIp: ip,
            detailMessage: ip.map { "Connected — tunnel IP \($0)" }
          )
          completion(map)
        }
        return
      }
      let opts: [String: NSObject] = [
        "host": host as NSString,
        "port": NSNumber(value: port),
      ]
      try session.startTunnel(options: opts)
      // Packet Tunnel handshake + setTunnelNetworkSettings can take several seconds;
      // user may also need to approve the VPN configuration dialog.
      pollTunnelConnected(manager: manager, attempt: 0, maxAttempts: 40, interval: 0.5) { connected in
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
          let st = manager.connection.status
          completion(
            RptFullTunnelResult.productConnectMap(
              packetTunnelActive: false,
              detailMessage:
                "Packet Tunnel start pending or failed (status \(statusName(st))/\(st.rawValue)). "
                + "If macOS asked to allow VPN configurations, choose Allow and Connect again. "
                + "Team residual builds: scripts/sign_macos_residual_team.py"
            )
          )
        }
      }
    } catch {
      completion(
        RptFullTunnelResult.productConnectMap(
          packetTunnelActive: false,
          detailMessage: describeNePreferencesError(error)
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
    let st = manager.connection.status
    if st == .connected {
      completion(true)
      return
    }
    // Still bringing the extension up — keep waiting until maxAttempts.
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

  /// Whether a saved VPN manager is ours (product Packet Tunnel).
  static func shouldStopManager(_ manager: NETunnelProviderManager) -> Bool {
    let proto = manager.protocolConfiguration as? NETunnelProviderProtocol
    let bid = proto?.providerBundleIdentifier ?? ""
    return bid.isEmpty || bid == providerBundleId || manager.localizedDescription == "Restore Privacy"
  }

  /// Stop every Restore Privacy Packet Tunnel session (channel disconnect + app quit).
  /// Residual public IP reverts when the OS tears down the NE session.
  static func stopAllTunnels(completion: (([String: Any]) -> Void)? = nil) {
    let finish: ([String: Any]) -> Void = { map in
      completion?(map)
    }
    NETunnelProviderManager.loadAllFromPreferences { managers, error in
      if let error {
        finish([
          "ok": false,
          "message": "Disconnect failed: \(error.localizedDescription)",
          "fullTunnelActive": false,
          "hostOnlySession": false,
        ] as [String: Any])
        return
      }
      for manager in managers ?? [] where shouldStopManager(manager) {
        manager.connection.stopVPNTunnel()
      }
      finish(RptFullTunnelResult.disconnectResultMap())
    }
  }

  /// Blocking stop for terminate hooks — waits until `stopVPNTunnel` is issued
  /// (or timeout) so process exit does not race the async preferences load.
  @discardableResult
  static func stopAllTunnelsAndWait(timeout: TimeInterval = 2.0) -> [String: Any] {
    let sem = DispatchSemaphore(value: 0)
    var resultMap = RptFullTunnelResult.disconnectResultMap()
    stopAllTunnels { map in
      resultMap = map
      sem.signal()
    }
    _ = sem.wait(timeout: .now() + timeout)
    return resultMap
  }
}
