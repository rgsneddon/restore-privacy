// macOS Packet Tunnel — full RPT2 path (secrets → handshake → full tunnel → DATA loops).
// HELLO and DATA share one long-lived UDP socket (node binds session.client_addr to HELLO source).
// Product residual defaults: outer obfs + RPTP pad + cover (~2s) + bounded send jitter.
// No public-IP geo admission (device keys + crypto only).

import Foundation
import NetworkExtension
import os.log

class PacketTunnelProvider: NEPacketTunnelProvider {
  private static let log = OSLog(
    subsystem: "com.restoreprivacy.restorePrivacyClient.PacketTunnel",
    category: "start"
  )

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
    let proto = protocolConfiguration as? NETunnelProviderProtocol
    let providerCfg = proto?.providerConfiguration ?? [:]
    if let h = options?["host"] as? String ?? providerCfg["host"] as? String {
      let trimmed = h.trimmingCharacters(in: .whitespacesAndNewlines)
      if !trimmed.isEmpty {
        endpointHost = trimmed
      }
    }
    if let p = options?["port"] as? Int ?? providerCfg["port"] as? Int {
      endpointPort = UInt16(p)
    } else if let p = options?["port"] as? NSNumber ?? providerCfg["port"] as? NSNumber {
      endpointPort = p.uint16Value
    }
    os_log(
      "startTunnel host=%{public}@ port=%{public}u",
      log: Self.log,
      type: .info,
      endpointHost,
      endpointPort
    )
    RptSecrets.writePacketTunnelStartTrace("startTunnel host=\(endpointHost) port=\(endpointPort)")

    // HELLO/UDP on pathQueue; NE setTunnelNetworkSettings + startTunnel
    // completionHandler must hop to main — calling them off-thread is a
    // documented NEVPNConnectionErrorDomain Plugin "internal error".
    pathQueue.async { [weak self] in
      guard let self else { return }
      do {
        // Privacy-scale Settings (App Group): shape/obfs OFF must disable residual pad/cover/wrap.
        // Multi-hop residual host is already selected by Flutter Connect host argument.
        let privacy = RptResidualPrivacyPolicy.loadFromAppGroup()
        privacy.applyToProductFlags()
        // HELLO must stay bare even if Settings later enables wrap/pad on DATA.
        RptObfuscation.productObfsEnabled = false
        RptTrafficShape.productPadding = false
        RptTrafficShape.productCover = false
        // Do not setTunnelNetworkSettings before HELLO. A placeholder utun
        // (even with excludedRoutes) swallows SERVER_HELLO; host Swift HELLO
        // on the physical NIC succeeds in <2s with the same keys.
        // Optional overrides from providerConfiguration (Connect-time)
        if let shape = providerCfg["trafficShape"] as? Bool {
          RptTrafficShape.productPadding = shape
          RptTrafficShape.productCover = shape
          RptTrafficShape.productJitterMsMax = shape ? 40 : 0
        }
        if let obfs = providerCfg["outerObfuscation"] as? Bool {
          RptObfuscation.productObfsEnabled = obfs
        }
        // 1–2. HELLO with wipe-drain failover: preferred host first, then catalog peers
        // when residual is down (fleet wipe). Not a mid-tunnel zero-loss hop.
        let preferred = self.endpointHost
        var altFromCfg: [String] = []
        if let raw = providerCfg["alternateHosts"] as? [String] {
          altFromCfg = raw
        } else if let raw = providerCfg["alternateHosts"] as? NSArray {
          altFromCfg = raw.compactMap { $0 as? String }
        }
        let order = RptEndpoint.connectHostOrder(
          preferred: preferred,
          alternates: altFromCfg.isEmpty ? nil : altFromCfg
        )
        var session: RptClientEngine.Session?
        var engine: RptClientEngine?
        var lastError: Error?
        let injectedPriv = (options?["clientPriv"] as? Data)
          ?? (options?["clientPriv"] as? NSData).map { Data(referencing: $0) }
        let injectedPub = (options?["nodePub"] as? Data)
          ?? (options?["nodePub"] as? NSData).map { Data(referencing: $0) }
        for host in order {
          do {
            let material: (clientPriv: Data, nodePub: Data)
            if let priv = injectedPriv, priv.count == 32,
               let pub = injectedPub, pub.count == 256 {
              material = (priv, pub)
            } else {
              material = try RptSecrets.loadAdmissionMaterial(residualHost: host)
            }
            os_log(
              "admission ok host=%{public}@ privBytes=%{public}d",
              log: Self.log,
              type: .info,
              host,
              material.clientPriv.count
            )
            let eng = try RptClientEngine(
              clientPrivRaw: material.clientPriv,
              nodeElgamalPubRaw: material.nodePub
            )
            let sess = try eng.handshake(host: host, port: self.endpointPort, timeout: 3)
            guard eng.transport?.isConnected == true else {
              eng.closeTransport()
              lastError = Self.error("UDP transport not ready after HELLO", code: 12)
              continue
            }
            self.endpointHost = host
            engine = eng
            session = sess
            break
          } catch {
            lastError = error
            os_log(
              "admission/HELLO failed host=%{public}@: %{public}@",
              log: Self.log,
              type: .error,
              host,
              error.localizedDescription
            )
            // Try next catalog peer only when residual looks unreachable
            if !RptEndpoint.isResidualUnreachableFailure(error.localizedDescription) {
              throw error
            }
          }
        }
        guard let engine, let session else {
          let msg =
            lastError?.localizedDescription
            ?? "Connect failed: preferred residual and catalog alternates unreachable"
          os_log("startTunnel abort: %{public}@", log: Self.log, type: .error, msg)
          RptSecrets.writePacketTunnelStartTrace("abort \(msg)")
          Self.completeStartOnMain(completionHandler, Self.error(msg, code: 11))
          return
        }
        self.engine = engine
        self.session = session

        // 4. Tunnel network settings: residual IPv4 is product always-on;
        // residual IPv6 follows Settings (default ON). Prefer startTunnel options
        // for IPv6, then App Group / UserDefaults.
        var stack = Self.loadResidualStackPrefs()
        // Force IPv4 capture ON regardless of stale prefs/options.
        stack = (true, stack.ipv6)
        if let o6 = options?["residual_ipv6"] as? Bool {
          stack = (true, o6)
        } else if let o6 = options?["residual_ipv6"] as? NSNumber {
          stack = (true, o6.boolValue)
        }
        let settings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: self.endpointHost)
        let ipv4 = NEIPv4Settings(addresses: [session.vpnIp], subnetMasks: ["255.255.255.255"])
        ipv4.excludedRoutes = [NEIPv4Route(destinationAddress: self.endpointHost, subnetMask: "255.255.255.255")]
        // Full-tunnel IPv4 residual capture (always on)
        ipv4.includedRoutes = [NEIPv4Route.default()]
        settings.ipv4Settings = ipv4
        // IPv6 residual protection: claim ::/0 only when Settings IPv6 residual is ON.
        if stack.ipv6 {
          settings.ipv6Settings = Self.ipv6IspLeakMitigationSettings()
        } else {
          settings.ipv6Settings = nil
        }
        // Node tunnel DNS (Unbound on 10.88.0.1) — not third-party public resolvers
        settings.dnsSettings = NEDNSSettings(servers: ["10.88.0.1"])
        settings.mtu = 1280

        RptSecrets.writePacketTunnelStartTrace("hello_ok vpnIp=\(session.vpnIp) applying settings on main")
        DispatchQueue.main.async {
          self.setTunnelNetworkSettings(settings) { err in
            if let err {
              RptSecrets.writePacketTunnelStartTrace("setTunnelNetworkSettings \(err.localizedDescription)")
              engine.closeTransport()
              completionHandler(err)
              return
            }
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
            RptSecrets.writePacketTunnelStartTrace("connected vpnIp=\(session.vpnIp)")
            completionHandler(nil)
          }
        }
      } catch {
        os_log(
          "startTunnel error: %{public}@",
          log: Self.log,
          type: .error,
          error.localizedDescription
        )
        RptSecrets.writePacketTunnelStartTrace("error \(error.localizedDescription)")
        Self.completeStartOnMain(
          completionHandler,
          Self.error(error.localizedDescription, code: 11)
        )
      }
    }
  }

  static func completeStartOnMain(
    _ completionHandler: @escaping (Error?) -> Void,
    _ error: Error?
  ) {
    if Thread.isMainThread {
      completionHandler(error)
    } else {
      DispatchQueue.main.async { completionHandler(error) }
    }
  }

  /// Product residual IPv6 ISP leak mitigation settings (parity with desktop block_isp).
  static func ipv6IspLeakMitigationSettings() -> NEIPv6Settings {
    // Stable ULA host address for the tunnel interface (not a public residual IPv6).
    let ipv6 = NEIPv6Settings(
      addresses: ["fd00:5274:7074::1"],
      networkPrefixLengths: [128]
    )
    ipv6.includedRoutes = [NEIPv6Route.default()]
    return ipv6
  }

  /// Settings residual prefs: IPv4 always ON; IPv6 defaults ON when unset.
  /// Reads App Group first (written by host setResidualStack), then standard.
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

  private func startPacketLoops() {
    guard let transport = engine?.transport, transport.fileDescriptor >= 0 else { return }

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
      } catch {}
    }
    source.resume()
    receiveSource = source

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
        } catch {}
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
