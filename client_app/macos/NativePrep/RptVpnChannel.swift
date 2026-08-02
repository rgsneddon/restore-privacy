// macOS Flutter host — method channel restore_privacy/vpn
// Full-tunnel honesty: product "Connected" only when Packet Tunnel is active.
// Host-side RPT2 HELLO is diagnostic only (never ok:true for residual-IP change).

import Foundation
import FlutterMacOS
import NetworkExtension
import CryptoKit
import AppKit
import Security

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
    // Product explainer (once) before App Group seed may surface macOS
    // “access data from other apps” — Apple owns that dialog; we cannot rewrite it.
    RptAppGroupAccessExplainer.presentIfNeeded()
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
        let alts = RptEndpoint.alternateHosts(from: args)
        connect(
          host: ep.host,
          port: ep.port,
          fullTunnel: fullTunnel,
          alternateHosts: alts,
          flutterResult: result
        )
      case "disconnect":
        // Same stop path as app-quit / terminate hooks — must stop system Network VPN.
        stopAllTunnels { map in result(map) }
      case "status":
        // Session rehydrate / post-disconnect verification.
        queryProductSessionStatus { map in result(map) }
      case "prepareVpn", "preparePacketTunnel", "registerVpnConfiguration":
        // Pre-Connect: save Packet Tunnel NE profile into OS VPN prefs (not L2TP/IKEv2).
        // openSettingsOnDenial default false — Flutter sequences System Settings
        // after prepare returns so Allow dialogs are not lost in a simultaneous burst.
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

  /// True when this host process is signed with `packet-tunnel-provider`.
  /// Public Developer ID packages omit host NE (AMFI); residual requires
  /// Team residual re-sign (`scripts/sign_macos_residual_team.py`).
  static func hostHasPacketTunnelNetworkExtensionEntitlement() -> Bool {
    var code: SecCode?
    guard SecCodeCopySelf([], &code) == errSecSuccess, let code else {
      return false
    }
    var staticCode: SecStaticCode?
    guard SecCodeCopyStaticCode(code, SecCSFlags(rawValue: 0), &staticCode) == errSecSuccess,
          let staticCode
    else {
      return false
    }
    var infoCF: CFDictionary?
    let flags = SecCSFlags(rawValue: kSecCSSigningInformation)
    guard SecCodeCopySigningInformation(staticCode, flags, &infoCF) == errSecSuccess,
          let info = infoCF as? [String: Any]
    else {
      return false
    }
    // Entitlements dict key (CFString bridging).
    let entsKey = kSecCodeInfoEntitlementsDict as String
    guard let ents = info[entsKey] as? [String: Any],
          let ne = ents["com.apple.developer.networking.networkextension"] as? [String]
    else {
      return false
    }
    return ne.contains("packet-tunnel-provider")
  }

  /// Actionable copy when host lacks Network Extension for NETunnelProviderManager.
  static func hostMissingNeEntitlementMessage() -> String {
    // Wording avoids bare allow-vpn phrasing so isNePermissionFailureDetail
    // does not mis-classify residual re-sign as a permission denial that opens Settings.
    "This app build cannot register or activate Packet Tunnel in Network settings: "
      + "the host is missing the packet-tunnel-provider Network Extension entitlement. "
      + "Public Developer ID downloads intentionally omit host NE so the app opens for all users. "
      + "On a developer Mac, re-sign for residual with: "
      + "python3 scripts/sign_macos_residual_team.py --app path/to/restore_privacy_client.app "
      + "then relaunch and press Connect. "
      + "If the OS shows a VPN configuration dialog, complete it, then Connect again. "
      + "Do not add L2TP / Cisco IPsec / IKEv2 manually. Network Settings alone cannot fix missing host NE."
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
    openSettingsOnDenial: Bool = false,
    completion: @escaping ([String: Any]) -> Void
  ) {
    if !hostHasPacketTunnelNetworkExtensionEntitlement() {
      var map: [String: Any] = productVpnIdentity()
      map["ok"] = false
      map["prepared"] = false
      map["needsVpnSystemSettingsApproval"] = false
      map["needsTeamResidualSign"] = true
      map["hostHasPacketTunnelEntitlement"] = false
      map["message"] = hostMissingNeEntitlementMessage()
      completion(map)
      return
    }
    if let last = lastSuccessfulPrepareAt,
       Date().timeIntervalSince(last) < prepareDebounce {
      var map: [String: Any] = [
        "ok": true,
        "prepared": true,
        "debounced": true,
        "tunnelType": productTunnelType,
        "providerBundleId": providerBundleId,
        "localizedDescription": productLocalizedDescription,
        "hostHasPacketTunnelEntitlement": true,
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
          "hostHasPacketTunnelEntitlement": true,
          "connectionStatus": statusName(manager.connection.status),
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
      let permissionClass = isNePermissionFailureDetail(detail)
      // Sequence: only open Settings when Flutter/native opt-in — never by default
      // during prepare so the NE Allow dialog is not missed among simultaneous panes.
      var opened = false
      if permissionClass && openSettingsOnDenial {
        opened = openVpnSystemSettings(force: false)
      }
      var map: [String: Any] = [
        "ok": false,
        "prepared": false,
        "tunnelType": productTunnelType,
        "providerBundleId": providerBundleId,
        "localizedDescription": productLocalizedDescription,
        "needsVpnSystemSettingsApproval": permissionClass,
        "openedVpnSettings": opened,
        "message":
          "Could not pre-register Packet Tunnel VPN configuration: \(detail). "
          + (permissionClass
            ? "Allow Restore Privacy under System Settings → Network → VPN & Filters "
              + "(Packet Tunnel — not L2TP / Cisco IPsec / IKEv2), then Connect."
            : "Press Connect again. If this build lacks host Network Extension, "
              + "use scripts/sign_macos_residual_team.py (public DevID omits host NE)."),
      ]
      completion(map)
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

  /// Residual re-sign / missing host NE — Settings cannot enable residual alone.
  /// Pure string classifier for tests and Settings auto-open gates.
  static func isTeamResidualOrMissingHostNeDetail(_ detail: String?) -> Bool {
    guard let d = detail?.lowercased(), !d.isEmpty else { return false }
    return d.contains("packet-tunnel-provider")
      || d.contains("sign_macos_residual")
      || d.contains("team residual")
      || d.contains("missing the packet-tunnel")
      || d.contains("host is missing")
      || d.contains("public developer id")
      || d.contains("needs team residual")
      || d.contains("host lacks packet-tunnel")
  }

  /// True only for user VPN-configuration authorization denial (not all NE errors).
  ///
  /// NEVPNErrorDomain alone is **not** enough — code 5 (configuration read/write)
  /// with permission language, or explicit not-authorized / permission denied.
  static func isNePermissionFailure(_ error: Error) -> Bool {
    let ns = error as NSError
    let lower = error.localizedDescription.lowercased()
    if isTeamResidualOrMissingHostNeDetail(lower) { return false }
    let authLanguage = lower.contains("permission denied")
      || lower.contains("not authorized")
      || lower.contains("user denied")
      || (lower.contains("permission") && lower.contains("denied"))
    if ns.domain == NEVPNErrorDomain {
      // NEVPNErrorConfigurationReadWriteFailed == 5 (typical after user denies Allow).
      // Other domain codes (invalid/stale/connection failed) are not auto-Settings.
      if ns.code == 5 {
        return true
      }
      return authLanguage
    }
    return authLanguage
  }

  /// String form of [isNePermissionFailure] for channel maps / host-side diagnostics.
  /// Does **not** treat residual re-sign copy, bare "allow vpn", or generic
  /// "NE preferences failed" without auth language as permission denial.
  static func isNePermissionFailureDetail(_ detail: String?) -> Bool {
    guard let raw = detail, !raw.isEmpty else { return false }
    let d = raw.lowercased()
    if isTeamResidualOrMissingHostNeDetail(d) { return false }
    // Explicit auth denial
    if d.contains("permission denied")
      || d.contains("not authorized")
      || d.contains("user denied") {
      return true
    }
    // NEVPNErrorDomain code 5 (or spelled-out) with denial context
    if d.contains("nevpnerrordomain") {
      let code5 = d.contains(" 5)") || d.contains(" 5:") || d.contains("code 5")
        || d.contains("errordomain 5")
      if code5 { return true }
      return d.contains("permission") || d.contains("denied") || d.contains("not authorized")
    }
    // Approve guidance only with System Settings / VPN & Filters context
    if d.contains("approve vpn configuration")
      && (d.contains("system settings") || d.contains("vpn & filters")) {
      return true
    }
    // Do NOT match: bare "allow vpn", generic "ne preferences failed", host-missing NE.
    return false
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
    alternateHosts: [String] = [],
    flutterResult: @escaping FlutterResult
  ) {
    // Product path is full tunnel — residual public IP only changes via Packet Tunnel.
    if !fullTunnel {
      // Explicit non-full-tunnel: diagnostic HELLO only (never product success).
      // Still try wipe-drain failover order for honesty diagnostics.
      let order = RptEndpoint.connectHostOrder(preferred: host, alternates: alternateHosts)
      hostSideDiagnostic(host: order.first ?? host, port: port) { map in
        flutterResult(map)
      }
      return
    }

    // Connect always re-registers the system VPN profile (handles user-deleted
    // Network configs) and enables it, then starts the Packet Tunnel so the
    // Network settings toggle turns on in tandem with the app Connect button.
    lastSuccessfulPrepareAt = nil

    // Wipe-drain / preferred-down: try preferred residual first, then catalog
    // alternates so DE wipe does not hard-fail Connect when IS/US are healthy.
    let order = RptEndpoint.connectHostOrder(preferred: host, alternates: alternateHosts)
    attemptTunnelConnectHosts(
      hosts: order,
      preferred: host,
      port: port,
      index: 0,
      lastMap: nil,
      flutterResult: flutterResult
    )
  }

  /// Sequential Packet Tunnel start across residual catalog hosts.
  private static func attemptTunnelConnectHosts(
    hosts: [String],
    preferred: String,
    port: UInt16,
    index: Int,
    lastMap: [String: Any]?,
    flutterResult: @escaping FlutterResult
  ) {
    guard index < hosts.count else {
      // Exhausted alternates — surface last failure (or generic).
      let map = lastMap ?? RptFullTunnelResult.productConnectMap(
        packetTunnelActive: false,
        detailMessage:
          "Connect failed: preferred residual and all catalog alternates unreachable "
          + "(wipe-drain failover exhausted). Try again when a peer is healthy."
      )
      let detail = map["message"] as? String
      if isNePermissionFailureDetail(detail) {
        hostSideDiagnostic(
          host: preferred,
          port: port,
          detail: detail,
          openVpnSettings: true
        ) { diag in
          flutterResult(diag)
        }
        return
      }
      hostSideDiagnostic(
        host: preferred,
        port: port,
        detail: detail,
        openVpnSettings: false
      ) { diag in
        flutterResult(diag)
      }
      return
    }

    let tryHost = hosts[index]
    enableProductVpnAndStartTunnel(host: tryHost, port: port) { map in
      if RptFullTunnelResult.isProductSuccess(map) {
        var out = map
        if tryHost != preferred {
          out["wipeDrainFailover"] = true
          out["wipe_drain_failover"] = true
          out["preferredHost"] = preferred
          out["activeResidualHost"] = tryHost
          out["failoverHost"] = tryHost
          let base = (map["message"] as? String) ?? "Connected"
          out["message"] =
            "\(base) — wipe_drain_failover preferred=\(preferred) active=\(tryHost)"
        } else {
          out["activeResidualHost"] = tryHost
        }
        flutterResult(out)
        return
      }
      let detail = map["message"] as? String
      // Permission / Team residual: stop — failover cannot fix NE entitlement.
      if isNePermissionFailureDetail(detail)
        || isTeamResidualOrMissingHostNeDetail(detail ?? "")
      {
        hostSideDiagnostic(
          host: tryHost,
          port: port,
          detail: detail,
          openVpnSettings: isNePermissionFailureDetail(detail)
        ) { diag in
          flutterResult(diag)
        }
        return
      }
      // Residual unreachable → try next catalog peer
      if RptEndpoint.isResidualUnreachableFailure(detail) {
        attemptTunnelConnectHosts(
          hosts: hosts,
          preferred: preferred,
          port: port,
          index: index + 1,
          lastMap: map,
          flutterResult: flutterResult
        )
        return
      }
      // Other failure (secrets, etc.) — do not silently hop
      hostSideDiagnostic(
        host: tryHost,
        port: port,
        detail: detail,
        openVpnSettings: false
      ) { diag in
        flutterResult(diag)
      }
    }
  }

  /// Save/enable product Packet Tunnel in System VPN prefs (recreate if deleted),
  /// then `startTunnel` so Network settings and the app connect together.
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
        // Residual-honest flags when host lacks packet-tunnel-provider (prepare parity).
        if isTeamResidualOrMissingHostNeDetail(detail)
          || isTeamResidualOrMissingHostNeDetail(full)
          || !hostHasPacketTunnelNetworkExtensionEntitlement() {
          map["needsTeamResidualSign"] = true
          map["hostHasPacketTunnelEntitlement"] = false
          map["needsVpnSystemSettingsApproval"] = false
          map["openedVpnSettings"] = false
          // Prefer the explicit residual message when entitlement check fails.
          if !hostHasPacketTunnelNetworkExtensionEntitlement() {
            map["message"] = hostMissingNeEntitlementMessage()
          }
        }
        completion(map)
        return
      }
      // Host pre-seed: copy IS/RO/DE pubs into App Group + home secrets so the
      // Packet Tunnel can HELLO to residual host.
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
                ?? "System VPN profile missing after save — Allow Restore Privacy in "
                + "System Settings → Network → VPN & Filters, then Connect again."
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
        completion(nil, describeNePreferencesError(error))
        return
      }
      if let existing = managers?.first(where: { isProductManager($0) }) {
        // Refresh endpoint on the live object so startTunnel options match.
        applyProductPacketTunnelProtocol(to: existing, host: host, port: port)
        existing.isEnabled = true
        existing.isOnDemandEnabled = false
        existing.saveToPreferences { saveErr in
          if saveErr != nil {
            // Still try start with existing if only endpoint refresh failed.
            completion(existing, nil)
            return
          }
          existing.loadFromPreferences { loadErr in
            if let loadErr {
              completion(nil, describeNePreferencesError(loadErr))
              return
            }
            completion(existing, nil)
          }
        }
        return
      }
      completion(
        nil,
        "Restore Privacy Packet Tunnel is not in System VPN preferences after registration. "
          + "If macOS showed an Allow dialog, choose Allow, then press Connect again."
      )
    }
  }

  /// Ensure preferences show enabled, then start tunnel (turns Network VPN on).
  private static func ensureEnabledThenStartTunnel(
    manager: NETunnelProviderManager,
    host: String,
    port: UInt16,
    completion: @escaping ([String: Any]) -> Void
  ) {
    let start = {
      startTunnel(manager: manager, host: host, port: port, completion: completion)
    }
    if manager.isEnabled, manager.connection.status != .invalid {
      start()
      return
    }
    applyProductPacketTunnelProtocol(to: manager, host: host, port: port)
    manager.isEnabled = true
    manager.isOnDemandEnabled = false
    manager.saveToPreferences { saveErr in
      if let saveErr {
        completion(
          RptFullTunnelResult.productConnectMap(
            packetTunnelActive: false,
            detailMessage: describeNePreferencesError(saveErr)
          )
        )
        return
      }
      manager.loadFromPreferences { loadErr in
        if let loadErr {
          completion(
            RptFullTunnelResult.productConnectMap(
              packetTunnelActive: false,
              detailMessage: describeNePreferencesError(loadErr)
            )
          )
          return
        }
        if !manager.isEnabled {
          completion(
            RptFullTunnelResult.productConnectMap(
              packetTunnelActive: false,
              detailMessage:
                "System VPN profile is present but still disabled. "
                + "Allow Restore Privacy under System Settings → Network → VPN & Filters, "
                + "then press Connect — the app will start the tunnel automatically."
            )
          )
          return
        }
        start()
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
      // Auto-open Settings only when caller asked AND detail is permission-class.
      // Host-only HELLO (outcome.ok) alone must not open Network Settings.
      let shouldOpen = openVpnSettings && isNePermissionFailureDetail(detail)
      if shouldOpen {
        DispatchQueue.main.async {
          let annotated = annotateNeedsVpnSettings(map, openSettings: true)
          completion(annotated)
        }
        return
      }
      DispatchQueue.main.async {
        // Sticky button only for permission-class residual messages.
        if isNePermissionFailureDetail(detail) {
          completion(annotateNeedsVpnSettings(map, openSettings: false))
        } else {
          completion(map)
        }
      }
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
  ///
  /// **Seamless upgrade:** reuse an existing product ``NETunnelProviderProtocol``
  /// when present (same provider bundle id). Replacing the protocol object on
  /// every prepare/Connect after an app upgrade can leave System VPN prefs
  /// unable to reconfigure the tunnel (reported 0.5.7→0.5.8 macOS failure).
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
    // DisconnectOnSleep false so residual session survives lid close while allowed by OS.
    proto.disconnectOnSleep = false
    var cfg = (proto.providerConfiguration as? [String: Any]) ?? [:]
    cfg["host"] = host
    cfg["port"] = Int(port)
    cfg["fullTunnel"] = true
    cfg["sessionName"] = productLocalizedDescription
    cfg["tunnelType"] = productTunnelType
    // Catalog peers for Packet Tunnel wipe-drain HELLO failover (IS/DE only)
    cfg["alternateHosts"] = RptEndpoint.alternateHosts(excluding: host)
    proto.providerConfiguration = cfg
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

  /// Surface NE preference errors with residual-honest copy.
  /// Permission-class: Approve in System Settings. Other NE errors: no Settings claim.
  private static func describeNePreferencesError(_ error: Error) -> String {
    let ns = error as NSError
    let base = error.localizedDescription
    let domain = ns.domain
    let code = ns.code
    if isNePermissionFailure(error) {
      return
        "NE preferences failed (\(domain) \(code)): \(base). "
        + "Approve VPN configuration in System Settings → Network → VPN & Filters "
        + "(or Login Items & Extensions). Allow Restore Privacy, then press Connect again."
    }
    // Non-permission NE errors (stale config, connection failed, etc.) — no auto-Settings claim.
    return
      "NE preferences error (\(domain) \(code)): \(base). "
      + "Press Connect again. If residual never activates on a developer Mac, "
      + "re-sign with scripts/sign_macos_residual_team.py (public DevID omits host NE)."
  }

  private static func loadOrCreateManager(
    host: String,
    port: UInt16,
    completion: @escaping (NETunnelProviderManager?, String?) -> Void
  ) {
    if !hostHasPacketTunnelNetworkExtensionEntitlement() {
      completion(nil, hostMissingNeEntitlementMessage())
      return
    }
    NETunnelProviderManager.loadAllFromPreferences { managers, error in
      if let error {
        completion(nil, describeNePreferencesError(error))
        return
      }
      let manager = selectOrCreateManager(from: managers)
      // Product residual: Packet Tunnel Network Extension only (never L2TP/IKEv2/IPsec).
      applyProductPacketTunnelProtocol(to: manager, host: host, port: port)
      // Must be enabled in preferences or Network settings shows the config as inactive.
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
          // Re-assert product identity + enabled after reload (macOS may clear either).
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
              completion(nil, describeNePreferencesError(reSaveErr))
              return
            }
            manager.loadFromPreferences { reLoadErr in
              if let reLoadErr {
                completion(nil, describeNePreferencesError(reLoadErr))
                return
              }
              if !manager.isEnabled {
                completion(
                  nil,
                  "Packet Tunnel saved but remains disabled in System VPN preferences. "
                    + "Open System Settings → Network → VPN & Filters, enable Restore Privacy, "
                    + "Allow if prompted, then Connect again."
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
    // startTunnel must run on main; Network settings toggle follows this session.
    let work = {
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
        // Connecting already — wait for connected instead of double-start.
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
              let stMsg =
                "Packet Tunnel still connecting/failed (status "
                + "\(statusName(manager.connection.status))). "
                + "Press Connect again. If macOS has not Allowed VPN for Restore Privacy, "
                + "use Open VPN settings once, Allow, then Connect."
              completion(
                RptFullTunnelResult.productConnectMap(
                  packetTunnelActive: false,
                  detailMessage: stMsg
                )
              )
            }
          }
          return
        }
        // Pass dual-stack residual prefs into the extension (parity with App Group).
        let stack = residualStackOptionsForTunnel()
        let alts = RptEndpoint.alternateHosts(excluding: host)
        let opts: [String: NSObject] = [
          "host": host as NSString,
          "port": NSNumber(value: port),
          "residual_ipv4": NSNumber(value: stack.ipv4),
          "residual_ipv6": NSNumber(value: stack.ipv6),
          "alternateHosts": alts as NSArray,
        ]
        // This enables the system VPN connection in Network settings (when allowed).
        try session.startTunnel(options: opts)
        // Packet Tunnel handshake + setTunnelNetworkSettings can take several seconds;
        // first run may show the system Allow VPN configuration dialog (OS-owned).
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
              // Prefer provider session flags; else the stack we just started with.
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
              + "Press Connect again after Allowing the OS VPN dialog if it appeared. "
              + "Do not use L2TP/IKEv2. Developers: scripts/sign_macos_residual_team.py "
              + "if host lacks packet-tunnel-provider. "
              + "If residual HELLO timed out (~15s): check network/UDP 44044, "
              + "keygen unlock, and Team residual Network Extension signing."
            let map = RptFullTunnelResult.productConnectMap(
              packetTunnelActive: false,
              detailMessage: detail
            )
            // Do not auto-open Network Settings — residual-honest status only.
            completion(map)
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

  /// Whether a saved VPN manager is ours (product Packet Tunnel) — used for stop/disconnect.
  /// Broader than [isProductManager]: also match by display name / bundle substring so
  /// Disconnect always tears down the Network connection the user sees as Restore Privacy.
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
            // Residual honesty from session stack / prefs — never generic "path blocked".
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
  /// Must turn **off** the system Network VPN toggle, not only update Flutter UI.
  /// Residual public IP reverts when the OS tears down the NE session.
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
        // Fallback: any still-connected tunnel provider that looks like ours by name.
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
          // Nothing to stop — already down (or profile removed).
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
              // Second hard stop pass
              issueStopOnManagers(targets) {
                waitUntilManagersDisconnected(
                  targets, attempt: 0, maxAttempts: 20, interval: 0.15
                ) { still2 in
                  map["systemVpnStopped"] = !still2
                  if still2 {
                    map["ok"] = false
                    map["message"] =
                      "Disconnect issued but system VPN still active — "
                      + "toggle off Restore Privacy in System Settings → Network → VPN & Filters, "
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

  /// Load each manager then `stopVPNTunnel` (required for reliable Network toggle off).
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
        // Stop regardless of load error — best effort for user Disconnect.
        let st = manager.connection.status
        if st != .disconnected && st != .invalid {
          manager.connection.stopVPNTunnel()
        } else {
          // Already down — still call stop for stubborn residual sessions.
          manager.connection.stopVPNTunnel()
        }
        group.leave()
      }
    }
    group.notify(queue: .main) {
      completion()
    }
  }

  /// True if any target is still connecting/connected/reasserting/disconnecting.
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
    // Refresh status via loadAll so connection objects are current.
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

  /// Blocking stop for terminate hooks — waits until tunnels are down (or timeout).
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
