// iOS Flutter host — method channel for restore_privacy/vpn
//
// PREP: Add this file to the **Runner** target in Xcode, then register from
// AppDelegate after the Flutter engine is ready, e.g.:
//
//   RptVpnChannel.register(with: engine.binaryMessenger)
//
// When Packet Tunnel is ready, replace connect() body to start NETunnelProviderManager.

import Foundation
import Flutter

enum RptVpnChannel {
  static let name = "restore_privacy/vpn"

  static func register(with messenger: FlutterBinaryMessenger) {
    let channel = FlutterMethodChannel(name: name, binaryMessenger: messenger)
    channel.setMethodCallHandler { call, result in
      switch call.method {
      case "connect":
        let args = call.arguments as? [String: Any] ?? [:]
        let host = args["host"] as? String ?? "104.156.224.47"
        let port = args["port"] as? Int ?? 44044
        // TODO(Mac): Start signed Packet Tunnel with these args + RPT2 handshake.
        result([
          "ok": false,
          "message":
            "iOS Packet Tunnel not yet configured — add Network Extension on Mac "
            + "(see ios/BUILD_ON_MAC.md). Target \(host):\(port) RPT2.",
        ] as [String: Any])
      case "disconnect":
        // TODO(Mac): Stop tunnel provider session.
        result(["ok": true, "message": "Disconnected"] as [String: Any])
      default:
        result(FlutterMethodNotImplemented)
      }
    }
  }
}
