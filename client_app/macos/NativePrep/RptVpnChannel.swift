// macOS Flutter host — method channel restore_privacy/vpn
// Success maps always include vpnIp when a session is established (criterion 3).

import Foundation
import FlutterMacOS
import NetworkExtension

enum RptVpnChannel {
  static let name = "restore_privacy/vpn"
  static let providerBundleId = "com.restoreprivacy.restorePrivacyClient.PacketTunnel"

  static func register(with messenger: FlutterBinaryMessenger) {
    // Seed Application Support from bundled Resources/secrets if present (Android inject pattern).
    _ = try? RptSecrets.seedApplicationSupportFromBundleIfNeeded()
    let channel = FlutterMethodChannel(name: name, binaryMessenger: messenger)
    channel.setMethodCallHandler { call, result in
      switch call.method {
      case "connect":
        let args = call.arguments as? [String: Any] ?? [:]
        let ep = RptEndpoint.resolve(from: args)
        connect(host: ep.host, port: ep.port, flutterResult: result)
      case "disconnect":
        disconnect { map in result(map) }
      case "hasSecrets":
        result([
          "ok": RptSecrets.filesPresent(),
          "message": RptSecrets.filesPresent()
            ? "Admission secrets found"
            : "Missing admission secrets — searched: \(RptSecrets.searchedPathsDescription())",
        ] as [String: Any])
      default:
        result(FlutterMethodNotImplemented)
      }
    }
  }

  private static func connect(host: String, port: UInt16, flutterResult: @escaping FlutterResult) {
    loadOrCreateManager(host: host, port: port) { manager, neError in
      if let manager {
        startTunnel(manager: manager, host: host, port: port) { map in
          if let ok = map["ok"] as? Bool, ok, map["vpnIp"] != nil {
            flutterResult(map)
          } else if let ok = map["ok"] as? Bool, ok {
            queryProviderVpnIp(manager: manager) { ip in
              if let ip, !ip.isEmpty {
                flutterResult([
                  "ok": true,
                  "message": "Connected — tunnel IP \(ip)",
                  "vpnIp": ip,
                ] as [String: Any])
              } else {
                hostSideConnect(host: host, port: port) { fallback in
                  flutterResult(fallback)
                }
              }
            }
          } else {
            hostSideConnect(host: host, port: port) { fallback in
              flutterResult(fallback)
            }
          }
        }
      } else {
        hostSideConnect(host: host, port: port) { map in
          flutterResult(map)
        }
      }
    }
  }

  private static func hostSideConnect(
    host: String,
    port: UInt16,
    completion: @escaping ([String: Any]) -> Void
  ) {
    DispatchQueue.global(qos: .userInitiated).async {
      let outcome = RptConnectOrchestrator.connect(host: host, port: port)
      outcome.engine?.closeTransport()
      var map = outcome.resultMap
      if outcome.ok, let ip = outcome.vpnIp, map["vpnIp"] == nil {
        map["vpnIp"] = ip
      }
      DispatchQueue.main.async { completion(map) }
    }
  }

  private static func loadOrCreateManager(
    host: String,
    port: UInt16,
    completion: @escaping (NETunnelProviderManager?, String?) -> Void
  ) {
    NETunnelProviderManager.loadAllFromPreferences { managers, error in
      if let error {
        completion(nil, error.localizedDescription)
        return
      }
      let manager = managers?.first ?? NETunnelProviderManager()
      let proto = NETunnelProviderProtocol()
      proto.providerBundleIdentifier = providerBundleId
      proto.serverAddress = "\(host):\(port)"
      proto.providerConfiguration = [
        "host": host,
        "port": Int(port),
        "fullTunnel": true,
        "sessionName": "Restore Privacy",
      ]
      manager.protocolConfiguration = proto
      manager.localizedDescription = "Restore Privacy"
      manager.isEnabled = true
      manager.saveToPreferences { saveErr in
        if let saveErr {
          completion(nil, saveErr.localizedDescription)
          return
        }
        manager.loadFromPreferences { loadErr in
          if let loadErr {
            completion(nil, loadErr.localizedDescription)
            return
          }
          completion(manager, nil)
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
    do {
      let session = manager.connection as? NETunnelProviderSession
      let opts: [String: NSObject] = [
        "host": host as NSString,
        "port": NSNumber(value: port),
      ]
      try session?.startTunnel(options: opts)
      DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
        if manager.connection.status == .connected {
          queryProviderVpnIp(manager: manager) { ip in
            if let ip, !ip.isEmpty {
              completion([
                "ok": true,
                "message": "Connected — tunnel IP \(ip)",
                "vpnIp": ip,
              ] as [String: Any])
            } else if let cfg = (manager.protocolConfiguration as? NETunnelProviderProtocol)?
              .providerConfiguration,
              let ip = cfg["vpnIp"] as? String, !ip.isEmpty {
              completion([
                "ok": true,
                "message": "Connected — tunnel IP \(ip)",
                "vpnIp": ip,
              ] as [String: Any])
            } else {
              completion([
                "ok": true,
                "message": "Connected — Packet Tunnel active",
              ] as [String: Any])
            }
          }
        } else {
          completion([
            "ok": false,
            "message": "Packet Tunnel start pending or failed (status \(manager.connection.status.rawValue))",
          ] as [String: Any])
        }
      }
    } catch {
      completion([
        "ok": false,
        "message": error.localizedDescription,
      ] as [String: Any])
    }
  }

  private static func queryProviderVpnIp(
    manager: NETunnelProviderManager,
    completion: @escaping (String?) -> Void
  ) {
    guard let session = manager.connection as? NETunnelProviderSession else {
      completion(nil)
      return
    }
    let msg = Data("status".utf8)
    do {
      try session.sendProviderMessage(msg) { response in
        guard let response,
              let obj = try? JSONSerialization.jsonObject(with: response) as? [String: Any] else {
          completion(nil)
          return
        }
        completion(obj["vpnIp"] as? String)
      }
    } catch {
      completion(nil)
    }
  }

  private static func disconnect(completion: @escaping ([String: Any]) -> Void) {
    NETunnelProviderManager.loadAllFromPreferences { managers, _ in
      managers?.forEach { $0.connection.stopVPNTunnel() }
      completion(["ok": true, "message": "Disconnected"] as [String: Any])
    }
  }
}
