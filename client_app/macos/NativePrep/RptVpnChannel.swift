// macOS Flutter host — method channel restore_privacy/vpn
//
// PREP: Add to **Runner** target. Register from AppDelegate after FlutterViewController exists:
//
//   if let controller = mainFlutterWindow?.contentViewController as? FlutterViewController {
//     RptVpnChannel.register(with: controller.engine.binaryMessenger)
//   }

import Foundation
import FlutterMacOS

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
        result([
          "ok": false,
          "message":
            "macOS Packet Tunnel not yet configured — add Network Extension on Mac "
            + "(see macos/BUILD_ON_MAC.md). Target \(host):\(port) RPT2.",
        ] as [String: Any])
      case "disconnect":
        result(["ok": true, "message": "Disconnected"] as [String: Any])
      default:
        result(FlutterMethodNotImplemented)
      }
    }
  }
}
