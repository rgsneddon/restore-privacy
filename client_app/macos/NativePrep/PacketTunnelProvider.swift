// macOS Packet Tunnel skeleton — add to a Network Extension target.
// Protocol outline: ios/NativePrep/RPT_PROTOCOL.md

import NetworkExtension

class PacketTunnelProvider: NEPacketTunnelProvider {
  override func startTunnel(options: [String: NSObject]?, completionHandler: @escaping (Error?) -> Void) {
    let err = NSError(
      domain: "com.restoreprivacy.tunnel",
      code: 1,
      userInfo: [
        NSLocalizedDescriptionKey:
          "macOS PacketTunnelProvider stub — implement RPT2 on Mac (BUILD_ON_MAC.md)",
      ]
    )
    completionHandler(err)
  }

  override func stopTunnel(with reason: NEProviderStopReason, completionHandler: @escaping () -> Void) {
    completionHandler()
  }
}
