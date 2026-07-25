// macOS Flutter host — method channel restore_privacy/vpn
// Full-tunnel honesty: product "Connected" only when Packet Tunnel is active.
// Host-side RPT2 HELLO is diagnostic only (never ok:true for residual-IP change).

import Foundation
import FlutterMacOS
import NetworkExtension
import CryptoKit
import AppKit

enum RptVpnChannel {
  static let name = "restore_privacy/vpn"
  /// Packet Tunnel Network Extension provider — product residual path (not L2TP/IKEv2/IPsec).
  static let providerBundleId = "com.restoreprivacy.restorePrivacyClient.PacketTunnel"
  /// System VPN preferences display name for the product manager.
  static let productLocalizedDescription = "Restore Privacy"
  /// Tunnel type token returned to Flutter / tests (never l2tp / ikev2 / ipsec).
  static let productTunnelType = "packet-tunnel"
  /// Debounce auto-open of System Settings so a double Connect does not spam panes.
  private static var lastVpnSettingsOpenAt: Date?
  private static let vpnSettingsOpenDebounce: TimeInterval = 20
  /// Debounce only after a **successful** prepare (saveToPreferences OK).
  /// Never set this on NE permission failure — otherwise a second call within the
  /// window would dishonestly report prepared:true after a failed save.
  private static var lastSuccessfulPrepareAt: Date?
  private static let prepareDebounce: TimeInterval = 8

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
      case "prepareVpn", "preparePacketTunnel", "registerVpnConfiguration":
        // Pre-Connect: save Packet Tunnel NE profile into OS VPN prefs (not L2TP/IKEv2).
        let args = call.arguments as? [String: Any] ?? [:]
        let ep = RptEndpoint.resolve(from: args)
        preparePacketTunnelConfiguration(host: ep.host, port: ep.port) { map in
          result(map)
        }
      case "openVpnSettings", "openVpnSystemSettings":
        // Explicit UI / Flutter retry — always attempt open (no debounce skip).
        let opened = openVpnSystemSettings(force: true)
        result([
          "ok": opened,
          "opened": opened,
          "message": opened
            ? "Opened System Settings (Network / VPN). Allow Restore Privacy Packet Tunnel if prompted — do not add L2TP, Cisco IPsec, or IKEv2 manually."
            : "Could not open System Settings automatically — go to System Settings → Network → VPN & Filters and Allow Restore Privacy (Packet Tunnel). Do not add L2TP/IKEv2.",
        ] as [String: Any])
      case "hasSecrets":
        result([
          "ok": RptSecrets.filesPresent(),
          "message": RptSecrets.filesPresent()
            ? "Admission secrets found"
            : "Missing admission secrets — searched: \(RptSecrets.searchedPathsDescription())",
        ] as [String: Any])
      case "devicePubHex":
        result(devicePubHexMap())
      case "setPrivacyScale":
        // Persist privacy-scale prefs for residual shell / next Connect (parity with Windows).
        let args = call.arguments as? [String: Any] ?? [:]
        let defaults = UserDefaults.standard
        if let v = args["trafficShape"] as? Bool {
          defaults.set(v, forKey: "privacy_traffic_shape")
        }
        if let v = args["outerObfuscation"] as? Bool {
          defaults.set(v, forKey: "privacy_outer_obfuscation")
        }
        if let v = args["multihop"] as? Bool {
          defaults.set(v, forKey: "privacy_multihop")
        }
        defaults.synchronize()
        // App Group for Packet Tunnel when available
        if let suite = UserDefaults(suiteName: RptSecrets.appGroupId) {
          suite.set(defaults.object(forKey: "privacy_traffic_shape"), forKey: "privacy_traffic_shape")
          suite.set(defaults.object(forKey: "privacy_outer_obfuscation"), forKey: "privacy_outer_obfuscation")
          suite.set(defaults.object(forKey: "privacy_multihop"), forKey: "privacy_multihop")
          suite.synchronize()
        }
        result(["ok": true] as [String: Any])
      default:
        result(FlutterMethodNotImplemented)
      }
    }
  }

  /// Identity of the product VPN manager saved to OS preferences (Packet Tunnel only).
  static func productVpnIdentity() -> [String: String] {
    [
      "tunnelType": productTunnelType,
      "providerBundleId": providerBundleId,
      "localizedDescription": productLocalizedDescription,
    ]
  }

  /// Pre-Connect: register Restore Privacy Packet Tunnel in System VPN preferences.
  /// Does **not** start the tunnel. macOS may still show Allow — that is required.
  /// Never configures L2TP, Cisco IPsec, or IKEv2.
  ///
  /// Debounce (skip re-save) applies **only** after a successful manager save.
  /// Failed NE preferences must leave lastSuccessfulPrepareAt unset so a later
  /// call (e.g. keygen unlock then launch prep) re-attempts registration.
  private static func preparePacketTunnelConfiguration(
    host: String,
    port: UInt16,
    completion: @escaping ([String: Any]) -> Void
  ) {
    if let last = lastSuccessfulPrepareAt,
       Date().timeIntervalSince(last) < prepareDebounce {
      var map: [String: Any] = [
        "ok": true,
        "prepared": true,
        "debounced": true,
        "tunnelType": productTunnelType,
        "providerBundleId": providerBundleId,
        "localizedDescription": productLocalizedDescription,
        "message":
          "Restore Privacy Packet Tunnel configuration already registered. "
          + "Press Connect when ready (Allow in System Settings if macOS asks).",
      ]
      for (k, v) in productVpnIdentity() { map[k] = v }
      completion(map)
      return
    }
    loadOrCreateManager(host: host, port: port) { manager, neError in
      if let manager {
        // Only stamp success after loadOrCreateManager returned a saved manager.
        lastSuccessfulPrepareAt = Date()
        // Confirm product Packet Tunnel identity (not legacy VPN types).
        let proto = manager.protocolConfiguration as? NETunnelProviderProtocol
        let bid = proto?.providerBundleIdentifier ?? providerBundleId
        let map: [String: Any] = [
          "ok": true,
          "prepared": true,
          "tunnelType": productTunnelType,
          "providerBundleId": bid,
          "localizedDescription": manager.localizedDescription ?? productLocalizedDescription,
          "enabled": manager.isEnabled,
          "message":
            "Restore Privacy Packet Tunnel registered in System VPN preferences. "
            + "If macOS asked to Allow VPN configuration, choose Allow — "
            + "do not add L2TP, Cisco IPsec, or IKEv2. Then press Connect.",
        ]
        completion(map)
        return
      }
      // Failure: do NOT set lastSuccessfulPrepareAt — next prepare must re-attempt.
      let detail = neError ?? "NE preferences unavailable"
      let openSettings = isNePermissionFailureDetail(detail)
      if openSettings {
        _ = openVpnSystemSettings(force: false)
      }
      var map: [String: Any] = [
        "ok": false,
        "prepared": false,
        "tunnelType": productTunnelType,
        "providerBundleId": providerBundleId,
        "localizedDescription": productLocalizedDescription,
        "needsVpnSystemSettingsApproval": true,
        "openedVpnSettings": openSettings,
        "message":
          "Could not pre-register Packet Tunnel VPN configuration: \(detail). "
          + "Allow Restore Privacy under System Settings → Network → VPN & Filters "
          + "(Packet Tunnel Network Extension — not L2TP / Cisco IPsec / IKEv2), then relaunch or Connect.",
      ]
      completion(annotateNeedsVpnSettings(map, openSettings: false))
    }
  }

  /// Best-effort System Settings deep-links for Network / VPN & Filters (macOS version varies).
  /// Pure list so tests can assert the shipped candidates without opening UI.
  static func vpnSystemSettingsURLCandidates() -> [String] {
    [
      // Ventura+ Network settings (VPN & Filters lives under Network).
      "x-apple.systempreferences:com.apple.Network-Settings.extension",
      // Older System Preferences Network pane.
      "x-apple.systempreferences:com.apple.preference.network",
      // Extensions / Login Items (where some NE prompts surface).
      "x-apple.systempreferences:com.apple.LoginItems-Settings.extension",
      "x-apple.systempreferences:com.apple.ExtensionsPreferences",
    ]
  }

  /// Open Network / VPN System Settings so the user can Allow VPN configuration.
  /// Cannot silently enable Packet Tunnel — macOS requires user Allow.
  @discardableResult
  static func openVpnSystemSettings(force: Bool = false) -> Bool {
    if !force, let last = lastVpnSettingsOpenAt,
       Date().timeIntervalSince(last) < vpnSettingsOpenDebounce {
      return true // recently opened — treat as ok for callers
    }
    var opened = false
    for s in vpnSystemSettingsURLCandidates() {
      if let u = URL(string: s), NSWorkspace.shared.open(u) {
        opened = true
        break
      }
    }
    if !opened {
      let pane = URL(fileURLWithPath: "/System/Library/PreferencePanes/Network.prefPane")
      opened = NSWorkspace.shared.open(pane)
    }
    if opened {
      lastVpnSettingsOpenAt = Date()
    }
    return opened
  }

  /// True for NEVPNErrorDomain permission / not-authorized / denied class (incl. code 5).
  static func isNePermissionFailure(_ error: Error) -> Bool {
    let ns = error as NSError
    let lower = error.localizedDescription.lowercased()
    if ns.domain == NEVPNErrorDomain { return true }
    return lower.contains("permission")
      || lower.contains("not authorized")
      || lower.contains("denied")
  }

  static func isNePermissionFailureDetail(_ detail: String?) -> Bool {
    guard let d = detail?.lowercased(), !d.isEmpty else { return false }
    return d.contains("nevpnerrordomain")
      || d.contains("permission")
      || d.contains("not authorized")
      || d.contains("denied")
      || d.contains("ne preferences failed")
      || d.contains("approve vpn")
      || d.contains("allow vpn")
  }

  /// Annotate a failed connect map and optionally open System Settings (debounced).
  private static func annotateNeedsVpnSettings(
    _ map: [String: Any],
    openSettings: Bool
  ) -> [String: Any] {
    var out = map
    out["needsVpnSystemSettingsApproval"] = true
    if openSettings {
      let opened = openVpnSystemSettings(force: false)
      out["openedVpnSettings"] = opened
    }
    return out
  }

  /// 64-char hex Ed25519 device public key for status-host bind-device-entitlement.
  private static func devicePubHexMap() -> [String: Any] {
    do {
      let material = try RptSecrets.loadAdmissionMaterial()
      let priv = material.clientPriv
      // CryptoKit Ed25519 from 32-byte seed
      let signing = try Curve25519.Signing.PrivateKey(rawRepresentation: priv)
      let pub = signing.publicKey.rawRepresentation
      let hex = pub.map { String(format: "%02x", $0) }.joined()
      return ["ok": true, "devicePubHex": hex, "device_pub_hex": hex]
    } catch {
      // Best-effort generate if load path differs
      return ["ok": false, "error": error.localizedDescription, "devicePubHex": ""]
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
        // Missing NE manager (incl. NEVPNErrorDomain 5) — open Settings so user can Allow.
        hostSideDiagnostic(
          host: host,
          port: port,
          detail: detail,
          openVpnSettings: true
        ) { map in
          flutterResult(map)
        }
        return
      }
      // Host pre-seed: copy IS/RO/DE pubs into App Group + home secrets so the
      // Packet Tunnel (IS-only historical seed) can HELLO to residual host.
      do {
        try RptSecrets.preseedSharedWritableSecretsForResidualHost(residualHost: host)
      } catch {
        // Best-effort; tunnel load may still find inject/package pins
      }
      startTunnel(manager: manager, host: host, port: port) { map in
        if RptFullTunnelResult.isProductSuccess(map) {
          flutterResult(map)
          return
        }
        // Tunnel not active — diagnostic HELLO (still ok:false) + open Settings so user can Allow.
        let detail = map["message"] as? String
        hostSideDiagnostic(
          host: host,
          port: port,
          detail: detail,
          openVpnSettings: true
        ) { diag in
          flutterResult(diag)
        }
      }
    }
  }

  /// Host RPT2 HELLO for diagnostics only — always ok:false for full-tunnel product.
  /// Closes transport immediately; residual public IP does not change.
  /// When [openVpnSettings] is true, opens System Settings (debounced) so the user can Allow VPN.
  private static func hostSideDiagnostic(
    host: String,
    port: UInt16,
    detail: String? = nil,
    openVpnSettings: Bool = false,
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
      // Host-only HELLO or NE prefs failure: user must Allow VPN config for residual IP change.
      let shouldOpen = openVpnSettings
        || outcome.ok
        || isNePermissionFailureDetail(detail)
      if shouldOpen {
        // Open on main so NSWorkspace is happy; annotate map for Flutter button.
        DispatchQueue.main.async {
          let annotated = annotateNeedsVpnSettings(map, openSettings: true)
          completion(annotated)
        }
        return
      }
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

  /// Apply product Packet Tunnel protocol identity (shared by prepare + Connect).
  private static func applyProductPacketTunnelProtocol(
    to manager: NETunnelProviderManager,
    host: String,
    port: UInt16
  ) {
    let proto = NETunnelProviderProtocol()
    proto.providerBundleIdentifier = providerBundleId
    proto.serverAddress = "\(host):\(port)"
    // DisconnectOnSleep false so residual session survives lid close while allowed by OS.
    proto.disconnectOnSleep = false
    proto.providerConfiguration = [
      "host": host,
      "port": Int(port),
      "fullTunnel": true,
      "sessionName": productLocalizedDescription,
      "tunnelType": productTunnelType,
    ]
    manager.protocolConfiguration = proto
    manager.localizedDescription = productLocalizedDescription
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
  /// End-user: Allow in System Settings (auto-opened). Operators: Team residual re-sign.
  private static func describeNePreferencesError(_ error: Error) -> String {
    let ns = error as NSError
    let base = error.localizedDescription
    let domain = ns.domain
    let code = ns.code
    // Common when host lacks Network Extension entitlement / profile, or user denied VPN config.
    if isNePermissionFailure(error) {
      return
        "NE preferences failed (\(domain) \(code)): \(base). "
        + "Approve VPN configuration in System Settings → Network → VPN & Filters "
        + "(or Login Items & Extensions). Settings opens automatically when possible — "
        + "Allow Restore Privacy, then press Connect again. "
        + "If Allow never appears, this build may need Team residual signing with "
        + "Packet Tunnel Network Extension on host + appex "
        + "(developers: scripts/sign_macos_residual_team.py)."
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
      // Product residual: Packet Tunnel Network Extension only (never L2TP/IKEv2/IPsec).
      applyProductPacketTunnelProtocol(to: manager, host: host, port: port)
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
          let map = RptFullTunnelResult.productConnectMap(
            packetTunnelActive: false,
            detailMessage:
              "Packet Tunnel start pending or failed (status \(statusName(st))/\(st.rawValue)). "
              + "If macOS asked to allow VPN configurations, choose Allow in System Settings "
              + "→ Network → VPN & Filters, then Connect again. "
              + "Developers: Team residual re-sign via scripts/sign_macos_residual_team.py"
          )
          // User may still need to Allow — open Settings (debounced).
          completion(annotateNeedsVpnSettings(map, openSettings: true))
        }
      }
    } catch {
      let map = RptFullTunnelResult.productConnectMap(
        packetTunnelActive: false,
        detailMessage: describeNePreferencesError(error)
      )
      completion(
        annotateNeedsVpnSettings(map, openSettings: isNePermissionFailure(error))
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
    return bid.isEmpty
      || bid == providerBundleId
      || manager.localizedDescription == productLocalizedDescription
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
