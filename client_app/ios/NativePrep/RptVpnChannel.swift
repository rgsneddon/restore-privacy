// iOS Flutter host — method channel restore_privacy/vpn
// Full-tunnel honesty: product "Connected" only when Packet Tunnel is active.
// Host-side RPT2 HELLO is diagnostic only (never ok:true for residual-IP change).
//
// Parity with macOS 0.4.8: Connect saves/enables product Packet Tunnel then
// startTunnel; Disconnect stopVPNTunnel + wait so system VPN turns off with app.

import Foundation
import Flutter
import NetworkExtension
import CryptoKit
import UIKit

enum RptVpnChannel {
  static let name = "restore_privacy/vpn"
  static let providerBundleId = "com.restoreprivacy.restorePrivacyClient.PacketTunnel"
  static let productLocalizedDescription = "Restore Privacy"
  static let productTunnelType = "packet-tunnel"

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
        // Same stop path as app-quit / terminate hooks — must stop system VPN.
        stopAllTunnels { map in result(map) }
      case "status":
        queryProductSessionStatus { map in result(map) }
      case "prepareVpn", "preparePacketTunnel", "registerVpnConfiguration":
        // Pre-Connect: save Packet Tunnel into iOS VPN preferences (not L2TP/IKEv2).
        // openSettingsOnDenial default false — Flutter sequences Settings after prepare.
        let args = call.arguments as? [String: Any] ?? [:]
        let ep = RptEndpoint.resolve(from: args)
        let openOnDenial = (args["openSettingsOnDenial"] as? Bool) ?? false
        preparePacketTunnelConfiguration(
          host: ep.host,
          port: ep.port,
          openSettingsOnDenial: openOnDenial
        ) { map in
          result(map)
        }
      case "openVpnSettings", "openVpnSystemSettings":
        let opened = openVpnSystemSettings()
        result([
          "ok": opened,
          "opened": opened,
          "message": opened
            ? "Opened Settings — Allow VPN for Restore Privacy if listed, then return and Connect."
            : "Open the Settings app → general VPN / Restore Privacy and Allow, then Connect again.",
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
        if let suite = UserDefaults(suiteName: RptSecrets.appGroupId) {
          suite.set(defaults.object(forKey: "privacy_traffic_shape"), forKey: "privacy_traffic_shape")
          suite.set(defaults.object(forKey: "privacy_outer_obfuscation"), forKey: "privacy_outer_obfuscation")
          suite.set(defaults.object(forKey: "privacy_multihop"), forKey: "privacy_multihop")
          suite.synchronize()
        }
        result(["ok": true] as [String: Any])
      case "setResidualStack":
        // Residual IPv4 is product always-on; only residual IPv6 is adjustable.
        let args = call.arguments as? [String: Any] ?? [:]
        let defaults = UserDefaults.standard
        defaults.set(true, forKey: "residual_ipv4")
        if let v = args["ipv6"] as? Bool {
          defaults.set(v, forKey: "residual_ipv6")
        }
        defaults.synchronize()
        if let suite = UserDefaults(suiteName: RptSecrets.appGroupId) {
          suite.set(true, forKey: "residual_ipv4")
          if let v = args["ipv6"] as? Bool {
            suite.set(v, forKey: "residual_ipv6")
          }
          suite.synchronize()
        }
        result([
          "ok": true,
          "residual_ipv4": true,
          "residual_ipv6": defaults.object(forKey: "residual_ipv6") as? Bool ?? true,
        ] as [String: Any])
      default:
        result(FlutterMethodNotImplemented)
      }
    }
  }

  /// Dual-stack residual prefs for Packet Tunnel start options.
  /// Residual IPv4 is always ON (product policy); IPv6 defaults ON when unset.
  static func residualStackOptionsForTunnel() -> (ipv4: Bool, ipv6: Bool) {
    func dualOn(_ defaults: UserDefaults, _ key: String) -> Bool {
      if defaults.object(forKey: key) == nil { return true }
      return defaults.bool(forKey: key)
    }
    if let suite = UserDefaults(suiteName: RptSecrets.appGroupId),
       suite.object(forKey: "residual_ipv6") != nil {
      return (true, dualOn(suite, "residual_ipv6"))
    }
    let std = UserDefaults.standard
    return (true, dualOn(std, "residual_ipv6"))
  }

  /// Session dual-stack flags for product success maps.
  /// Residual IPv4 is always ON; IPv6 prefers providerConfiguration then prefs.
  static func residualStackForSession(
    manager: NETunnelProviderManager?,
    providerIpv4: Bool? = nil,
    providerIpv6: Bool? = nil
  ) -> (ipv4: Bool, ipv6: Bool) {
    let prefs = residualStackOptionsForTunnel()
    // Product policy: residual IPv4 always ON (ignore stale provider/prefs false).
    if let v6 = providerIpv6 {
      return (true, v6)
    }
    if let proto = manager?.protocolConfiguration as? NETunnelProviderProtocol,
       let cfg = proto.providerConfiguration {
      let v6 = (cfg["ipv6Protected"] as? Bool) ?? prefs.ipv6
      return (true, v6)
    }
    return (true, prefs.ipv6)
  }

  /// Full-tunnel product success map with session residual honesty (never default IPv6 ON alone).
  static func productSuccessConnectMap(
    vpnIp: String?,
    manager: NETunnelProviderManager? = nil,
    providerIpv4: Bool? = nil,
    providerIpv6: Bool? = nil
  ) -> [String: Any] {
    let stack = residualStackForSession(
      manager: manager,
      providerIpv4: providerIpv4,
      providerIpv6: providerIpv6
    )
    return RptFullTunnelResult.productConnectMap(
      packetTunnelActive: true,
      vpnIp: vpnIp,
      ipv6Protected: stack.ipv6,
      ipv4Residual: stack.ipv4
    )
  }

  /// Identity of the product VPN manager saved to OS preferences (Packet Tunnel only).
  static func productVpnIdentity() -> [String: String] {
    [
      "tunnelType": productTunnelType,
      "providerBundleId": providerBundleId,
      "localizedDescription": productLocalizedDescription,
    ]
  }

  /// Best-effort open Settings so the user can Allow VPN configuration.
  @discardableResult
  static func openVpnSystemSettings() -> Bool {
    // iOS has no stable public deep-link to the VPN list; open root Settings.
    if let u = URL(string: UIApplication.openSettingsURLString) {
      var opened = false
      if Thread.isMainThread {
        opened = UIApplication.shared.openURL_compat(u)
      } else {
        DispatchQueue.main.sync {
          opened = UIApplication.shared.openURL_compat(u)
        }
      }
      return opened
    }
    return false
  }

  /// Pre-Connect: register Restore Privacy Packet Tunnel in iOS VPN preferences.
  /// Does **not** start the tunnel. iOS may still show Allow — that is required.
  /// Never configures L2TP, Cisco IPsec, or IKEv2.
  ///
  /// Success (prepared:true) only after load/create + isEnabled + saveToPreferences
  /// succeed. Failed saves never claim prepared/ok.
  private static func preparePacketTunnelConfiguration(
    host: String,
    port: UInt16,
    openSettingsOnDenial: Bool = false,
    completion: @escaping ([String: Any]) -> Void
  ) {
    // Always attempt loadOrCreateManager + save isEnabled=true so VPN prefs
    // list Restore Privacy and can show Allow when required.
    loadOrCreateManager(host: host, port: port) { manager, neError in
      if let manager {
        let proto = manager.protocolConfiguration as? NETunnelProviderProtocol
        let bid = proto?.providerBundleIdentifier ?? providerBundleId
        // Re-assert enabled and re-save so registration is not a silent no-op.
        manager.isEnabled = true
        manager.isOnDemandEnabled = false
        manager.saveToPreferences { saveErr in
          if let saveErr {
            var map: [String: Any] = [
              "ok": false,
              "prepared": false,
              "tunnelType": productTunnelType,
              "providerBundleId": bid,
              "localizedDescription": productLocalizedDescription,
              "needsVpnSystemSettingsApproval": true,
              "openedVpnSettings": false,
              // iOS residual host always carries Packet Tunnel NE capability when
              // the app is residual-capable; never emit false (macOS catalog DevID).
              "hostHasPacketTunnelEntitlement": true,
              "needsTeamResidualSign": false,
              "message":
                "Could not save Packet Tunnel VPN configuration: "
                + "\(saveErr.localizedDescription). "
                + "Allow VPN for Restore Privacy in iOS Settings if prompted, then Connect again.",
            ]
            for (k, v) in productVpnIdentity() { map[k] = v }
            completion(map)
            return
          }
          var map: [String: Any] = [
            "ok": true,
            "prepared": true,
            "tunnelType": productTunnelType,
            "providerBundleId": bid,
            "localizedDescription":
              manager.localizedDescription ?? productLocalizedDescription,
            "enabled": manager.isEnabled,
            "connectionStatus": statusName(manager.connection.status),
            "hostHasPacketTunnelEntitlement": true,
            "needsTeamResidualSign": false,
            "message":
              "Restore Privacy Packet Tunnel registered in VPN preferences. "
              + "If iOS asks to Allow VPN configuration, choose Allow — "
              + "do not add L2TP, Cisco IPsec, or IKEv2. Then press Connect.",
          ]
          for (k, v) in productVpnIdentity() { map[k] = v }
          completion(map)
        }
        return
      }
      let detail = neError ?? "NE preferences unavailable"
      var opened = false
      if openSettingsOnDenial {
        opened = openVpnSystemSettings()
      }
      var map: [String: Any] = [
        "ok": false,
        "prepared": false,
        "tunnelType": productTunnelType,
        "providerBundleId": providerBundleId,
        "localizedDescription": productLocalizedDescription,
        "needsVpnSystemSettingsApproval": true,
        "openedVpnSettings": opened,
        // Omitted false — Flutter treats only explicit false as host-NE missing.
        "hostHasPacketTunnelEntitlement": true,
        "needsTeamResidualSign": false,
        "message":
          "Could not pre-register Packet Tunnel VPN configuration: \(detail). "
          + "Allow VPN for Restore Privacy in iOS Settings if prompted, then Connect.",
      ]
      for (k, v) in productVpnIdentity() { map[k] = v }
      completion(map)
    }
  }

  /// 64-char hex Ed25519 device public key for status-host bind-device-entitlement.
  private static func devicePubHexMap() -> [String: Any] {
    do {
      let material = try RptSecrets.loadAdmissionMaterial()
      let priv = material.clientPriv
      let signing = try Curve25519.Signing.PrivateKey(rawRepresentation: priv)
      let pub = signing.publicKey.rawRepresentation
      let hex = pub.map { String(format: "%02x", $0) }.joined()
      return ["ok": true, "devicePubHex": hex, "device_pub_hex": hex]
    } catch {
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
      hostSideDiagnostic(host: host, port: port) { map in
        flutterResult(map)
      }
      return
    }

    // Connect always re-registers the system VPN profile (handles user-deleted
    // VPN configs) and enables it, then starts the Packet Tunnel so the
    // system VPN session turns on in tandem with the app Connect button.
    enableProductVpnAndStartTunnel(host: host, port: port) { map in
      if RptFullTunnelResult.isProductSuccess(map) {
        flutterResult(map)
        return
      }
      let detail = map["message"] as? String
      hostSideDiagnostic(host: host, port: port, detail: detail) { diag in
        var out = diag
        out["needsVpnSystemSettingsApproval"] = true
        flutterResult(out)
      }
    }
  }

  /// Save/enable product Packet Tunnel in VPN prefs (recreate if deleted),
  /// then `startTunnel` so system VPN and the app connect together.
  private static func enableProductVpnAndStartTunnel(
    host: String,
    port: UInt16,
    completion: @escaping ([String: Any]) -> Void
  ) {
    loadOrCreateManager(host: host, port: port) { manager, neError in
      guard manager != nil else {
        let detail = neError ?? "NE preferences unavailable"
        let full = "Could not enable system VPN for Connect: \(detail)"
        var map = RptFullTunnelResult.productConnectMap(
          packetTunnelActive: false,
          detailMessage: full
        )
        // Surface Open VPN settings so the user can complete Allow.
        map["needsVpnSystemSettingsApproval"] = true
        map["openedVpnSettings"] = false
        map["message"] = full
          + " Allow VPN for Restore Privacy in iOS Settings if prompted, then Connect."
        completion(map)
        return
      }
      // Host pre-seed: copy IS/RO/DE pubs into App Group so Packet Tunnel HELLO
      // can use residual host pin (appex Bundle.main often only has Iceland).
      do {
        try RptSecrets.preseedSharedWritableSecretsForResidualHost(residualHost: host)
      } catch {
        // Best-effort; tunnel load may still find inject/package pins
      }
      // Apple: after save, prefer a freshly loaded manager instance for startTunnel.
      reloadProductManager(host: host, port: port) { live, reloadErr in
        guard let live else {
          completion(
            RptFullTunnelResult.productConnectMap(
              packetTunnelActive: false,
              detailMessage: reloadErr
                ?? "System VPN profile missing after save — Allow VPN for Restore Privacy "
                + "if iOS prompts, then Connect again."
            )
          )
          return
        }
        ensureEnabledThenStartTunnel(manager: live, host: host, port: port, completion: completion)
      }
    }
  }

  /// Load product manager from prefs after save (must match provider bundle id).
  private static func reloadProductManager(
    host: String,
    port: UInt16,
    completion: @escaping (NETunnelProviderManager?, String?) -> Void
  ) {
    NETunnelProviderManager.loadAllFromPreferences { managers, error in
      if let error {
        completion(nil, error.localizedDescription)
        return
      }
      if let existing = managers?.first(where: { isProductManager($0) }) {
        applyProductPacketTunnelProtocol(to: existing, host: host, port: port)
        existing.isEnabled = true
        existing.isOnDemandEnabled = false
        existing.saveToPreferences { saveErr in
          if saveErr != nil {
            completion(existing, nil)
            return
          }
          existing.loadFromPreferences { loadErr in
            if let loadErr {
              completion(nil, loadErr.localizedDescription)
              return
            }
            completion(existing, nil)
          }
        }
        return
      }
      completion(
        nil,
        "Restore Privacy Packet Tunnel is not in VPN preferences after registration. "
          + "If iOS showed an Allow dialog, choose Allow, then press Connect again."
      )
    }
  }

  /// Ensure preferences show enabled, then start tunnel (turns system VPN on).
  /// Always save isEnabled=true so iOS VPN prefs list Restore Privacy and can
  /// present the Allow configuration dialog when required.
  private static func ensureEnabledThenStartTunnel(
    manager: NETunnelProviderManager,
    host: String,
    port: UInt16,
    completion: @escaping ([String: Any]) -> Void
  ) {
    let start = {
      startTunnel(manager: manager, host: host, port: port, completion: completion)
    }
    // Always re-apply protocol + isEnabled and save (do not short-circuit on
    // already-enabled — user may have deleted/re-denied prefs between prepares).
    applyProductPacketTunnelProtocol(to: manager, host: host, port: port)
    manager.isEnabled = true
    manager.isOnDemandEnabled = false
    manager.saveToPreferences { saveErr in
      if let saveErr {
        // If already enabled, still attempt startTunnel (profile may already be allowed).
        if manager.isEnabled, manager.connection.status != .invalid {
          start()
          return
        }
        var map = RptFullTunnelResult.productConnectMap(
          packetTunnelActive: false,
          detailMessage: saveErr.localizedDescription
        )
        map["needsVpnSystemSettingsApproval"] = true
        completion(map)
        return
      }
      manager.loadFromPreferences { loadErr in
        if let loadErr {
          var map = RptFullTunnelResult.productConnectMap(
            packetTunnelActive: false,
            detailMessage: loadErr.localizedDescription
          )
          map["needsVpnSystemSettingsApproval"] = true
          completion(map)
          return
        }
        if !manager.isEnabled {
          var map = RptFullTunnelResult.productConnectMap(
            packetTunnelActive: false,
            detailMessage:
              "System VPN profile is present but still disabled. "
              + "Allow VPN for Restore Privacy if iOS prompts, then press Connect."
          )
          map["needsVpnSystemSettingsApproval"] = true
          completion(map)
          return
        }
        start()
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
    if let existing = managers?.first(where: { isProductManager($0) }) {
      return existing
    }
    return NETunnelProviderManager()
  }

  /// True when a manager is the product Restore Privacy Packet Tunnel.
  /// Does **not** match empty/unknown providers (avoids hijacking other VPN rows).
  static func isProductManager(_ manager: NETunnelProviderManager) -> Bool {
    let proto = manager.protocolConfiguration as? NETunnelProviderProtocol
    let bid = proto?.providerBundleIdentifier ?? ""
    if bid == providerBundleId { return true }
    if manager.localizedDescription == productLocalizedDescription,
       bid.isEmpty || bid == providerBundleId {
      return true
    }
    return false
  }

  /// Apply product Packet Tunnel protocol identity (shared by prepare + Connect).
  /// Seamless upgrade: reuse existing product Packet Tunnel protocol when present.
  private static func applyProductPacketTunnelProtocol(
    to manager: NETunnelProviderManager,
    host: String,
    port: UInt16
  ) {
    let proto: NETunnelProviderProtocol
    if let existing = manager.protocolConfiguration as? NETunnelProviderProtocol,
       (existing.providerBundleIdentifier ?? "").isEmpty
         || existing.providerBundleIdentifier == providerBundleId {
      proto = existing
    } else {
      proto = NETunnelProviderProtocol()
    }
    proto.providerBundleIdentifier = providerBundleId
    proto.serverAddress = "\(host):\(port)"
    proto.disconnectOnSleep = false
    var cfg = (proto.providerConfiguration as? [String: Any]) ?? [:]
    cfg["host"] = host
    cfg["port"] = Int(port)
    cfg["fullTunnel"] = true
    cfg["sessionName"] = productLocalizedDescription
    cfg["tunnelType"] = productTunnelType
    proto.providerConfiguration = cfg
    manager.protocolConfiguration = proto
    manager.localizedDescription = productLocalizedDescription
  }

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
      let manager = selectOrCreateManager(from: managers)
      applyProductPacketTunnelProtocol(to: manager, host: host, port: port)
      manager.isEnabled = true
      manager.isOnDemandEnabled = false
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
          let proto = manager.protocolConfiguration as? NETunnelProviderProtocol
          let bidOk = (proto?.providerBundleIdentifier ?? "") == providerBundleId
          if manager.isEnabled, bidOk {
            completion(manager, nil)
            return
          }
          applyProductPacketTunnelProtocol(to: manager, host: host, port: port)
          manager.isEnabled = true
          manager.isOnDemandEnabled = false
          manager.saveToPreferences { reSaveErr in
            if let reSaveErr {
              completion(nil, reSaveErr.localizedDescription)
              return
            }
            manager.loadFromPreferences { reLoadErr in
              if let reLoadErr {
                completion(nil, reLoadErr.localizedDescription)
                return
              }
              if !manager.isEnabled {
                completion(
                  nil,
                  "Packet Tunnel saved but remains disabled in VPN preferences. "
                    + "Allow VPN for Restore Privacy if iOS prompts, then Connect again."
                )
                return
              }
              completion(manager, nil)
            }
          }
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
    let work = {
      do {
        let session = manager.connection as? NETunnelProviderSession
        guard let session else {
          completion(
            RptFullTunnelResult.productConnectMap(
              packetTunnelActive: false,
              detailMessage:
                "NETunnelProviderSession missing — Packet Tunnel entitlement/profile required."
            )
          )
          return
        }
        if manager.connection.status == .connected {
          queryProviderSession(manager: manager) { ip, v4, v6 in
            completion(
              productSuccessConnectMap(
                vpnIp: ip,
                manager: manager,
                providerIpv4: v4,
                providerIpv6: v6
              )
            )
          }
          return
        }
        if manager.connection.status == .connecting
          || manager.connection.status == .reasserting {
          pollTunnelConnected(manager: manager, attempt: 0, maxAttempts: 40, interval: 0.5) {
            connected in
            if connected {
              queryProviderSession(manager: manager) { ip, v4, v6 in
                completion(
                  productSuccessConnectMap(
                    vpnIp: ip,
                    manager: manager,
                    providerIpv4: v4,
                    providerIpv6: v6
                  )
                )
              }
            } else {
              completion(
                RptFullTunnelResult.productConnectMap(
                  packetTunnelActive: false,
                  detailMessage:
                    "Packet Tunnel still connecting/failed (status "
                    + "\(statusName(manager.connection.status))). "
                    + "Allow VPN if iOS prompts, then Connect again."
                )
              )
            }
          }
          return
        }
        let stack = residualStackOptionsForTunnel()
        let opts: [String: NSObject] = [
          "host": host as NSString,
          "port": NSNumber(value: port),
          "residual_ipv4": NSNumber(value: stack.ipv4),
          "residual_ipv6": NSNumber(value: stack.ipv6),
        ]
        // Enables the system VPN connection when the user has Allowed the config.
        try session.startTunnel(options: opts)
        pollTunnelConnected(manager: manager, attempt: 0, maxAttempts: 50, interval: 0.5) {
          connected in
          if connected {
            queryProviderSession(manager: manager) { ip, v4, v6 in
              var resolved = ip
              if resolved == nil || resolved?.isEmpty == true,
                 let cfg = (manager.protocolConfiguration as? NETunnelProviderProtocol)?
                   .providerConfiguration,
                 let cfgIp = cfg["vpnIp"] as? String, !cfgIp.isEmpty {
                resolved = cfgIp
              }
              completion(
                productSuccessConnectMap(
                  vpnIp: resolved,
                  manager: manager,
                  providerIpv4: v4 ?? stack.ipv4,
                  providerIpv6: v6 ?? stack.ipv6
                )
              )
            }
          } else {
            let st = manager.connection.status
            let detail =
              "Packet Tunnel did not become Connected (status \(statusName(st))/\(st.rawValue)). "
              + "Connect re-creates and enables the VPN profile automatically. "
              + "If iOS asked to Allow VPN configuration, choose Allow, then Connect again. "
              + "If residual HELLO timed out (~15s): check network/UDP 44044, "
              + "keygen unlock, and Network Extension entitlements."
            completion(
              RptFullTunnelResult.productConnectMap(
                packetTunnelActive: false,
                detailMessage: detail
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
    if Thread.isMainThread {
      work()
    } else {
      DispatchQueue.main.async(execute: work)
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
    queryProviderSession(manager: manager) { ip, _, _ in
      completion(ip)
    }
  }

  /// Provider session honesty: tunnel IP + dual-stack residual flags from the extension.
  private static func queryProviderSession(
    manager: NETunnelProviderManager,
    completion: @escaping (_ vpnIp: String?, _ ipv4Residual: Bool?, _ ipv6Protected: Bool?) -> Void
  ) {
    guard let session = manager.connection as? NETunnelProviderSession else {
      completion(nil, nil, nil)
      return
    }
    let msg = Data("status".utf8)
    do {
      try session.sendProviderMessage(msg) { response in
        guard let response,
              let obj = try? JSONSerialization.jsonObject(with: response) as? [String: Any] else {
          completion(nil, nil, nil)
          return
        }
        completion(
          obj["vpnIp"] as? String,
          obj["ipv4Residual"] as? Bool,
          obj["ipv6Protected"] as? Bool
        )
      }
    } catch {
      completion(nil, nil, nil)
    }
  }

  /// Whether a saved VPN manager is ours — used for stop/disconnect.
  /// Broader than [isProductManager] so Disconnect always tears down product VPN.
  static func shouldStopManager(_ manager: NETunnelProviderManager) -> Bool {
    if isProductManager(manager) { return true }
    let desc = manager.localizedDescription ?? ""
    if desc == productLocalizedDescription { return true }
    if desc.range(of: "Restore Privacy", options: .caseInsensitive) != nil {
      return true
    }
    let proto = manager.protocolConfiguration as? NETunnelProviderProtocol
    let bid = proto?.providerBundleIdentifier ?? ""
    if bid == providerBundleId { return true }
    if bid.range(of: "restorePrivacyClient", options: .caseInsensitive) != nil {
      return true
    }
    if bid.range(of: "restoreprivacy", options: .caseInsensitive) != nil {
      return true
    }
    return false
  }

  /// Product session snapshot for Flutter status / post-disconnect checks.
  private static func queryProductSessionStatus(
    completion: @escaping ([String: Any]) -> Void
  ) {
    let work = {
      NETunnelProviderManager.loadAllFromPreferences { managers, error in
        if let error {
          completion([
            "ok": false,
            "connected": false,
            "fullTunnelActive": false,
            "message": "Status unavailable: \(error.localizedDescription)",
          ] as [String: Any])
          return
        }
        let ours = (managers ?? []).filter { shouldStopManager($0) }
        let active = ours.first(where: {
          let st = $0.connection.status
          return st == .connected || st == .connecting || st == .reasserting
        })
        if let active {
          let st = active.connection.status
          let connecting = st == .connecting || st == .reasserting
          if st == .connected {
            queryProviderSession(manager: active) { ip, v4, v6 in
              var map = productSuccessConnectMap(
                vpnIp: ip,
                manager: active,
                providerIpv4: v4,
                providerIpv6: v6
              )
              map["connected"] = true
              map["connecting"] = false
              completion(map)
            }
            return
          }
          completion([
            "ok": false,
            "connected": false,
            "connecting": connecting,
            "fullTunnelActive": false,
            "message": "VPN \(statusName(st))",
          ] as [String: Any])
          return
        }
        completion([
          "ok": false,
          "connected": false,
          "connecting": false,
          "fullTunnelActive": false,
          "message": "Disconnected",
        ] as [String: Any])
      }
    }
    if Thread.isMainThread {
      work()
    } else {
      DispatchQueue.main.async(execute: work)
    }
  }

  /// Stop every Restore Privacy Packet Tunnel session (channel disconnect + app quit).
  /// Must turn **off** the system VPN session, not only update Flutter UI.
  static func stopAllTunnels(completion: (([String: Any]) -> Void)? = nil) {
    let finish: ([String: Any]) -> Void = { map in
      if Thread.isMainThread {
        completion?(map)
      } else {
        DispatchQueue.main.async { completion?(map) }
      }
    }
    let begin = {
      NETunnelProviderManager.loadAllFromPreferences { managers, error in
        if let error {
          finish([
            "ok": false,
            "message": "Disconnect failed: \(error.localizedDescription)",
            "fullTunnelActive": false,
            "hostOnlySession": false,
            "systemVpnStopped": false,
          ] as [String: Any])
          return
        }
        let all = managers ?? []
        var targets = all.filter { shouldStopManager($0) }
        if targets.isEmpty {
          targets = all.filter { m in
            let st = m.connection.status
            let live = st == .connected || st == .connecting || st == .reasserting
              || st == .disconnecting
            guard live else { return false }
            let desc = m.localizedDescription ?? ""
            return desc.range(of: "Restore Privacy", options: .caseInsensitive) != nil
              || desc.range(of: "Packet Tunnel", options: .caseInsensitive) != nil
          }
        }
        if targets.isEmpty {
          var map = RptFullTunnelResult.disconnectResultMap()
          map["systemVpnStopped"] = true
          map["stoppedCount"] = 0
          finish(map)
          return
        }
        issueStopOnManagers(targets) {
          waitUntilManagersDisconnected(targets, attempt: 0, maxAttempts: 30, interval: 0.15) {
            stillLive in
            var map = RptFullTunnelResult.disconnectResultMap()
            map["stoppedCount"] = targets.count
            map["systemVpnStopped"] = !stillLive
            if stillLive {
              issueStopOnManagers(targets) {
                waitUntilManagersDisconnected(
                  targets, attempt: 0, maxAttempts: 20, interval: 0.15
                ) { still2 in
                  map["systemVpnStopped"] = !still2
                  if still2 {
                    map["ok"] = false
                    map["message"] =
                      "Disconnect issued but system VPN still active — "
                      + "turn off Restore Privacy in the Settings VPN list, "
                      + "or press Disconnect again."
                    map["fullTunnelActive"] = true
                  }
                  finish(map)
                }
              }
              return
            }
            finish(map)
          }
        }
      }
    }
    if Thread.isMainThread {
      begin()
    } else {
      DispatchQueue.main.async(execute: begin)
    }
  }

  private static func issueStopOnManagers(
    _ managers: [NETunnelProviderManager],
    completion: @escaping () -> Void
  ) {
    guard !managers.isEmpty else {
      completion()
      return
    }
    let group = DispatchGroup()
    for manager in managers {
      group.enter()
      manager.loadFromPreferences { _ in
        manager.connection.stopVPNTunnel()
        group.leave()
      }
    }
    group.notify(queue: .main) {
      completion()
    }
  }

  private static func anyManagerStillLive(_ managers: [NETunnelProviderManager]) -> Bool {
    for m in managers {
      switch m.connection.status {
      case .connected, .connecting, .reasserting, .disconnecting:
        return true
      default:
        continue
      }
    }
    return false
  }

  private static func waitUntilManagersDisconnected(
    _ managers: [NETunnelProviderManager],
    attempt: Int,
    maxAttempts: Int,
    interval: TimeInterval,
    completion: @escaping (_ stillLive: Bool) -> Void
  ) {
    NETunnelProviderManager.loadAllFromPreferences { all, _ in
      let liveTargets: [NETunnelProviderManager]
      if let all {
        liveTargets = all.filter { shouldStopManager($0) }
      } else {
        liveTargets = managers
      }
      if !anyManagerStillLive(liveTargets) {
        completion(false)
        return
      }
      if attempt >= maxAttempts {
        completion(true)
        return
      }
      DispatchQueue.main.asyncAfter(deadline: .now() + interval) {
        waitUntilManagersDisconnected(
          managers,
          attempt: attempt + 1,
          maxAttempts: maxAttempts,
          interval: interval,
          completion: completion
        )
      }
    }
  }

  /// Blocking stop for `applicationWillTerminate` — waits until tunnels are down.
  @discardableResult
  static func stopAllTunnelsAndWait(timeout: TimeInterval = 4.0) -> [String: Any] {
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

// MARK: - UIApplication open URL (iOS version-safe)

private extension UIApplication {
  /// open(_:options:completionHandler:) wrapper that works without async bridging.
  func openURL_compat(_ url: URL) -> Bool {
    open(url, options: [:], completionHandler: nil)
    return true
  }
}
