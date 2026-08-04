// iOS Packet Tunnel — full RPT2 path (secrets → handshake → full tunnel → DATA loops).
// HELLO and DATA share one long-lived UDP socket (node binds session.client_addr to HELLO source).
// Product residual defaults: outer obfs + RPTP pad + cover (~2s) + bounded send jitter.
// No public-IP geo admission (device keys + crypto only).

import Foundation
import NetworkExtension

class PacketTunnelProvider: NEPacketTunnelProvider {
  private var engine: RptClientEngine?
  private var session: RptClientEngine.Session?
  private var keepaliveTimer: DispatchSourceTimer?
  private var coverTimer: DispatchSourceTimer?
  private var receiveSource: DispatchSourceRead?
  private var pathQueue = DispatchQueue(label: "com.restoreprivacy.tunnel.io")
  private var endpointHost = RptEndpoint.host
  private var endpointPort = RptEndpoint.port
  private var running = false
  private var lastCoverSent = Date.distantPast

  override func startTunnel(options: [String: NSObject]?, completionHandler: @escaping (Error?) -> Void) {
    let proto = protocolConfiguration as? NETunnelProviderProtocol
    let providerCfg = proto?.providerConfiguration ?? [:]
    if let h = options?["host"] as? String ?? providerCfg["host"] as? String {
      endpointHost = h
    }
    if let p = options?["port"] as? Int ?? providerCfg["port"] as? Int {
      endpointPort = UInt16(p)
    } else if let p = options?["port"] as? NSNumber ?? providerCfg["port"] as? NSNumber {
      endpointPort = p.uint16Value
    }

    pathQueue.async { [weak self] in
      guard let self else { return }
      do {
        // Privacy-scale Settings (App Group): shape/obfs OFF must disable residual pad/cover/wrap.
        let privacy = RptResidualPrivacyPolicy.loadFromAppGroup()
        privacy.applyToProductFlags()
        if let shape = providerCfg["trafficShape"] as? Bool {
          RptTrafficShape.productPadding = shape
          RptTrafficShape.productCover = shape
          RptTrafficShape.productJitterMsMax = shape ? 40 : 0
        }
        if let obfs = providerCfg["outerObfuscation"] as? Bool {
          RptObfuscation.productObfsEnabled = obfs
        }
        // 1. Load secrets (client_ed25519.priv + entry/exit pub only — never node_elgamal.priv)
        // Multi-hop residual: when host is Romania exit, HELLO uses exit_node_elgamal.pub.
        let material = try RptSecrets.loadAdmissionMaterial(residualHost: self.endpointHost)
        let engine = try RptClientEngine(clientPrivRaw: material.clientPriv, nodeElgamalPubRaw: material.nodePub)

        // 2. RPT2 handshake on a long-lived connected UDP socket (kept open for DATA/KEEPALIVE)
        let session = try engine.handshake(host: self.endpointHost, port: self.endpointPort, timeout: 20)
        guard engine.transport?.isConnected == true else {
          completionHandler(Self.error("UDP transport not ready after HELLO", code: 12))
          return
        }
        self.engine = engine
        self.session = session

        // 4. Residual IPv4 always-on; residual IPv6 from Settings (default ON).
        var stack = Self.loadResidualStackPrefs()
        stack = (true, stack.ipv6)
        if let o6 = options?["residual_ipv6"] as? Bool {
          stack = (true, o6)
        } else if let o6 = options?["residual_ipv6"] as? NSNumber {
          stack = (true, o6.boolValue)
        }
        let settings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: self.endpointHost)
        let ipv4 = NEIPv4Settings(addresses: [session.vpnIp], subnetMasks: ["255.255.255.255"])
        ipv4.excludedRoutes = [NEIPv4Route(destinationAddress: self.endpointHost, subnetMask: "255.255.255.255")]
        ipv4.includedRoutes = [NEIPv4Route.default()]
        settings.ipv4Settings = ipv4
        if stack.ipv6 {
          settings.ipv6Settings = Self.ipv6IspLeakMitigationSettings()
        } else {
          settings.ipv6Settings = nil
        }
        // Node tunnel DNS (Unbound on 10.88.0.1) — not third-party public resolvers
        settings.dnsSettings = NEDNSSettings(servers: ["10.88.0.1"])
        settings.mtu = 1280

        self.setTunnelNetworkSettings(settings) { err in
          if let err {
            engine.closeTransport()
            completionHandler(err)
            return
          }
          // Publish vpnIp for host channel IPC
          self.setTunnelNetworkSettingsDone(
            vpnIp: session.vpnIp,
            ipv6Protected: stack.ipv6,
            ipv4Residual: stack.ipv4
          )
          self.running = true
          // Transport already connected + ready (BSD connect completed before HELLO reply)
          self.startPacketLoops()
          self.startKeepalive()
          self.startCoverTraffic()
          completionHandler(nil)
        }
      } catch {
        completionHandler(Self.error(error.localizedDescription, code: 11))
      }
    }
  }

  /// Product residual IPv6 ISP leak mitigation settings (parity with desktop block_isp).
  static func ipv6IspLeakMitigationSettings() -> NEIPv6Settings {
    let ipv6 = NEIPv6Settings(
      addresses: ["fd00:5274:7074::1"],
      networkPrefixLengths: [128]
    )
    ipv6.includedRoutes = [NEIPv6Route.default()]
    return ipv6
  }

  /// Residual prefs: IPv4 always ON; IPv6 defaults ON when unset.
  static func loadResidualStackPrefs(
    appGroupId: String = "group.com.restoreprivacy.shared"
  ) -> (ipv4: Bool, ipv6: Bool) {
    func dualOn(_ defaults: UserDefaults, _ key: String) -> Bool {
      if defaults.object(forKey: key) == nil { return true }
      return defaults.bool(forKey: key)
    }
    if let suite = UserDefaults(suiteName: appGroupId),
       suite.object(forKey: "residual_ipv6") != nil {
      return (true, dualOn(suite, "residual_ipv6"))
    }
    let std = UserDefaults.standard
    return (true, dualOn(std, "residual_ipv6"))
  }

  /// Store vpnIp so handleAppMessage / host can return criterion-3 maps.
  private func setTunnelNetworkSettingsDone(
    vpnIp: String,
    ipv6Protected: Bool = true,
    ipv4Residual: Bool = true
  ) {
    if let proto = protocolConfiguration as? NETunnelProviderProtocol {
      var cfg = proto.providerConfiguration ?? [:]
      cfg["vpnIp"] = vpnIp
      cfg["ok"] = true
      cfg["ipv6Protected"] = ipv6Protected
      cfg["ipv4Residual"] = ipv4Residual
      proto.providerConfiguration = cfg
    }
  }

  override func stopTunnel(with reason: NEProviderStopReason, completionHandler: @escaping () -> Void) {
    running = false
    keepaliveTimer?.cancel()
    keepaliveTimer = nil
    coverTimer?.cancel()
    coverTimer = nil
    receiveSource?.cancel()
    receiveSource = nil
    engine?.closeTransport()
    engine = nil
    session = nil
    completionHandler()
  }

  override func handleAppMessage(_ messageData: Data, completionHandler: ((Data?) -> Void)?) {
    // Host queries session status including vpnIp (criterion 3 map)
    if let s = session {
      let proto = protocolConfiguration as? NETunnelProviderProtocol
      let cfg = proto?.providerConfiguration ?? [:]
      let v6 = (cfg["ipv6Protected"] as? Bool) ?? Self.loadResidualStackPrefs().ipv6
      let v4 = (cfg["ipv4Residual"] as? Bool) ?? Self.loadResidualStackPrefs().ipv4
      let msg: String
      if v4 && v6 {
        msg = "Connected — VPN active; IPv6 ISP path blocked (\(s.vpnIp))"
      } else if v4 && !v6 {
        msg = "Connected — IPv4 via VPN; IPv6 not protected (\(s.vpnIp))"
      } else if !v4 && v6 {
        msg = "Connected — IPv4 residual off; IPv6 ISP path blocked (\(s.vpnIp))"
      } else {
        msg = "Connected — residual dual-stack off (\(s.vpnIp))"
      }
      let info: [String: Any] = [
        "ok": true,
        "message": msg,
        "vpnIp": s.vpnIp,
        "ipv6Protected": v6,
        "ipv4Residual": v4,
        "fullTunnelActive": v4,
      ]
      completionHandler?(try? JSONSerialization.data(withJSONObject: info))
    } else {
      completionHandler?(try? JSONSerialization.data(withJSONObject: [
        "ok": false,
        "message": "No active RPT2 session",
      ] as [String: Any]))
    }
  }

  // MARK: - packetFlow ↔ same UDP transport as HELLO

  private func startPacketLoops() {
    guard let transport = engine?.transport, transport.fileDescriptor >= 0 else { return }

    // UDP → outer-unwrap → open (cover-tolerant) → packetFlow
    let source = DispatchSource.makeReadSource(
      fileDescriptor: transport.fileDescriptor,
      queue: pathQueue
    )
    source.setEventHandler { [weak self] in
      guard let self, self.running, let engine = self.engine else { return }
      do {
        let data = try engine.receiveFrame(timeout: 0.0)
        if RptProtocol.peekType(data) == .data {
          // Product residual: discard peer cover (RPTC) without tearing tunnel
          if let plain = try engine.openPacketAllowCover(data), !plain.isEmpty {
            self.packetFlow.writePackets([plain], withProtocols: [NSNumber(value: AF_INET)])
          }
        }
      } catch {
        // timeout / empty — ignore
      }
    }
    source.setCancelHandler {
      // do not close fd here — engine owns transport lifecycle
    }
    source.resume()
    receiveSource = source

    // packetFlow → pad + jitter + seal + outer wrap → UDP
    readPackets()
  }

  private func readPackets() {
    guard running else { return }
    packetFlow.readPackets { [weak self] packets, _ in
      guard let self, self.running, let engine = self.engine else { return }
      for packet in packets {
        do {
          // sendSealedPacket: product pad + outer obfs + bounded jitter
          try engine.sendSealedPacket(packet)
        } catch {
          // drop
        }
      }
      self.readPackets()
    }
  }

  /// Lean RPT2 KEEPALIVE period (seconds). Must stay under node idle prune (~60s).
  /// Mirrors client residual_keepalive_policy.RESIDUAL_KEEPALIVE_INTERVAL_SEC.
  static let residualKeepaliveIntervalSec: TimeInterval = 25

  private func startKeepalive() {
    // Cancel any prior timer so reconnect does not stack keep-alives.
    keepaliveTimer?.cancel()
    keepaliveTimer = nil
    let interval = Self.residualKeepaliveIntervalSec
    let timer = DispatchSource.makeTimerSource(queue: pathQueue)
    // First fire soon after tunnel up, then lean multi-second period (not cover).
    timer.schedule(
      deadline: .now() + interval,
      repeating: interval,
      leeway: .seconds(2)
    )
    timer.setEventHandler { [weak self] in
      // Keep refreshing node last_seen while tunnel is running — even with no TUN data.
      guard let self, self.running, let engine = self.engine else { return }
      do {
        try engine.sendKeepalive()
      } catch {
        // Transient send errors: leave timer running so idle does not starve forever.
      }
    }
    timer.resume()
    keepaliveTimer = timer
  }

  /// Product residual cover traffic (RPTC) only when privacy-scale shape is ON.
  /// Timer fires at productCoverIntervalS (not sub-second spin checks).
  private func startCoverTraffic() {
    guard RptTrafficShape.productCover else { return }
    let interval = max(0.5, RptTrafficShape.productCoverIntervalS)
    let timer = DispatchSource.makeTimerSource(queue: pathQueue)
    timer.schedule(deadline: .now() + interval, repeating: interval)
    timer.setEventHandler { [weak self] in
      guard let self, self.running, let engine = self.engine else { return }
      guard RptTrafficShape.productCover else { return }
      do {
        try engine.sendCoverFrame()
        self.lastCoverSent = Date()
      } catch {}
    }
    timer.resume()
    coverTimer = timer
  }

  private static func error(_ message: String, code: Int) -> NSError {
    NSError(
      domain: "com.restoreprivacy.tunnel",
      code: code,
      userInfo: [NSLocalizedDescriptionKey: message]
    )
  }
}
