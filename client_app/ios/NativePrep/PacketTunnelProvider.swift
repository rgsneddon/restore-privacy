// iOS Packet Tunnel — full RPT2 path (secrets → handshake → full tunnel → DATA loops).
// HELLO and DATA share one long-lived UDP socket (node binds session.client_addr to HELLO source).
// No public-IP geo admission (device keys + crypto only).

import Foundation
import NetworkExtension

class PacketTunnelProvider: NEPacketTunnelProvider {
  private var engine: RptClientEngine?
  private var session: RptClientEngine.Session?
  private var keepaliveTimer: DispatchSourceTimer?
  private var receiveSource: DispatchSourceRead?
  private var pathQueue = DispatchQueue(label: "com.restoreprivacy.tunnel.io")
  private var endpointHost = RptEndpoint.host
  private var endpointPort = RptEndpoint.port
  private var running = false

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
        // 1. Load secrets (client_ed25519.priv + node_elgamal.pub only — never node_elgamal.priv)
        let material = try RptSecrets.loadAdmissionMaterial()
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
        // IPv6: claim default IPv6 route into the tunnel so residual IPv6 is not
        // left on the ISP path (may blackhole until node carries IPv6 — privacy first).
        let ipv6 = NEIPv6Settings(addresses: ["fd00:7274::2"], networkPrefixLengths: [128 as NSNumber])
        ipv6.includedRoutes = [NEIPv6Route.default()]
        settings.ipv6Settings = ipv6
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
        "message": "Connected — tunnel IP \(s.vpnIp)",
        "vpnIp": s.vpnIp,
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

    // UDP → open → packetFlow (on HELLO socket)
    let source = DispatchSource.makeReadSource(
      fileDescriptor: transport.fileDescriptor,
      queue: pathQueue
    )
    source.setEventHandler { [weak self] in
      guard let self, self.running, let engine = self.engine else { return }
      do {
        let data = try engine.receiveFrame(timeout: 0.0)
        if RptProtocol.peekType(data) == .data {
          let plain = try engine.openPacket(data)
          self.packetFlow.writePackets([plain], withProtocols: [NSNumber(value: AF_INET)])
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

    // packetFlow → seal → UDP (HELLO socket)
    readPackets()
  }

  private func readPackets() {
    guard running else { return }
    packetFlow.readPackets { [weak self] packets, _ in
      guard let self, self.running, let engine = self.engine else { return }
      for packet in packets {
        do {
          // sendSealedPacket uses the same transport as CLIENT_HELLO
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

  private static func error(_ message: String, code: Int) -> NSError {
    NSError(
      domain: "com.restoreprivacy.tunnel",
      code: code,
      userInfo: [NSLocalizedDescriptionKey: message]
    )
  }
}
