// iOS Packet Tunnel skeleton — add to a **PacketTunnel** Network Extension target.
//
// Full RPT2 implementation: ios/NativePrep/RPT_PROTOCOL.md + client/connect.py

import NetworkExtension

class PacketTunnelProvider: NEPacketTunnelProvider {
  override func startTunnel(options: [String: NSObject]?, completionHandler: @escaping (Error?) -> Void) {
    // TODO(Mac):
    // 1. UK IP gate
    // 2. Load secrets (App Group)
    // 3. RPT2 handshake over UDP to host:port from options / provider config
    // 4. setTunnelNetworkSettings with assigned VPN IP + 0.0.0.0/0
    // 5. Start packetFlow + UDP DATA loops
    let err = NSError(
      domain: "com.restoreprivacy.tunnel",
      code: 1,
      userInfo: [
        NSLocalizedDescriptionKey:
          "PacketTunnelProvider stub — implement RPT2 on Mac (BUILD_ON_MAC.md)",
      ]
    )
    completionHandler(err)
  }

  override func stopTunnel(with reason: NEProviderStopReason, completionHandler: @escaping () -> Void) {
    // TODO(Mac): tear down UDP + session
    completionHandler()
  }

  override func handleAppMessage(_ messageData: Data, completionHandler: ((Data?) -> Void)?) {
    completionHandler?(nil)
  }
}
