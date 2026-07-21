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

        // 4. Full-tunnel settings: assigned VPN IP + default route intent 0.0.0.0/0
        let settings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: self.endpointHost)
        let ipv4 = NEIPv4Settings(addresses: [session.vpnIp], subnetMasks: ["255.255.255.255"])
        let defaultRoute = NEIPv4Route.default()
        ipv4.includedRoutes = [defaultRoute]
        // Exclude RPT server host from tunnel to avoid recursive blackhole
        ipv4.excludedRoutes = [NEIPv4Route(destinationAddress: self.endpointHost, subnetMask: "255.255.255.255")]
        settings.ipv4Settings = ipv4
        // No IPv6 kill-switch / default-route blackhole: the node is IPv4 residual only.
        // Leaving NEIPv6Settings unset keeps ISP IPv6 available (honestly unprotected).
        settings.ipv6Settings = nil
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
          self.setTunnelNetworkSettingsDone(vpnIp: session.vpnIp)
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

  /// Store vpnIp so handleAppMessage / host can return criterion-3 maps.
  private func setTunnelNetworkSettingsDone(vpnIp: String) {
    if let proto = protocolConfiguration as? NETunnelProviderProtocol {
      var cfg = proto.providerConfiguration ?? [:]
      cfg["vpnIp"] = vpnIp
      cfg["ok"] = true
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
      let info: [String: Any] = [
        "ok": true,
        "message": "Connected — IPv4 via VPN; IPv6 not protected (\(s.vpnIp))",
        "vpnIp": s.vpnIp,
        "ipv6Protected": false,
        "fullTunnelActive": true,
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

  private func startKeepalive() {
    let timer = DispatchSource.makeTimerSource(queue: pathQueue)
    timer.schedule(deadline: .now() + 30, repeating: 30)
    timer.setEventHandler { [weak self] in
      guard let self, let engine = self.engine else { return }
      do {
        try engine.sendKeepalive()
      } catch {}
    }
    timer.resume()
    keepaliveTimer = timer
  }

  /// Product residual cover traffic (RPTC) at productCoverIntervalS — default on.
  private func startCoverTraffic() {
    guard RptTrafficShape.productCover else { return }
    let interval = max(0.2, RptTrafficShape.productCoverIntervalS)
    let timer = DispatchSource.makeTimerSource(queue: pathQueue)
    timer.schedule(deadline: .now() + interval, repeating: 0.25)
    timer.setEventHandler { [weak self] in
      guard let self, self.running, let engine = self.engine else { return }
      guard RptTrafficShape.productCover else { return }
      let now = Date()
      if now.timeIntervalSince(self.lastCoverSent) < RptTrafficShape.productCoverIntervalS {
        return
      }
      do {
        try engine.sendCoverFrame()
        self.lastCoverSent = now
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
