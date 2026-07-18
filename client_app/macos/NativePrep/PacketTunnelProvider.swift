// macOS Packet Tunnel — full RPT2 path (UK gate → secrets → handshake → full tunnel → DATA loops).
// HELLO and DATA share one long-lived UDP socket (node binds session.client_addr to HELLO source).

import Foundation
import NetworkExtension

class PacketTunnelProvider: NEPacketTunnelProvider {
  private var engine: RptClientEngine?
  private var session: RptClientEngine.Session?
  private var keepaliveTimer: DispatchSourceTimer?
  private var receiveSource: DispatchSourceRead?
  private var pathQueue = DispatchQueue(label: "com.restoreprivacy.tunnel.io")
  private var endpointHost = "104.156.224.47"
  private var endpointPort: UInt16 = 44044
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
        // 1. UK public IP gate (fail closed)
        let gate = RptUkIpGate.checkUkPublicIp()
        guard gate.allowed else {
          completionHandler(Self.error(gate.message, code: 10))
          return
        }

        // 2. Load secrets (client_ed25519.priv + node_elgamal.pub only — never node_elgamal.priv)
        let material = try RptSecrets.loadAdmissionMaterial()
        let engine = try RptClientEngine(clientPrivRaw: material.clientPriv, nodeElgamalPubRaw: material.nodePub)

        // 3. RPT2 handshake on a long-lived connected UDP socket (kept open for DATA/KEEPALIVE)
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
        ipv4.excludedRoutes = [NEIPv4Route(destinationAddress: self.endpointHost, subnetMask: "255.255.255.255")]
        settings.ipv4Settings = ipv4
        settings.dnsSettings = NEDNSSettings(servers: ["1.1.1.1", "9.9.9.9"])
        settings.mtu = 1280

        self.setTunnelNetworkSettings(settings) { err in
          if let err {
            engine.closeTransport()
            completionHandler(err)
            return
          }
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
          let plain = try engine.openPacket(data)
          self.packetFlow.writePackets([plain], withProtocols: [NSNumber(value: AF_INET)])
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
          try engine.sendSealedPacket(packet)
        } catch {}
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
