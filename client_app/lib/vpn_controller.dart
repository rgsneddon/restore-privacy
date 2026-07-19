import 'package:flutter/services.dart';

import 'connect_status.dart';
import 'rpt_config.dart';

/// Platform channel to Android VpnService / Windows plugin hooks.
class VpnController {
  static const MethodChannel _channel = MethodChannel('restore_privacy/vpn');

  final void Function(String) onStatus;

  VpnController({required this.onStatus});

  /// Product policy: never auto-connect on launch (manual Connect only).
  static bool get autoConnectOnLaunchEnabled => RptConfig.autoConnectOnLaunch;

  /// Deprecated name kept for older call sites — always delegates to [connect]
  /// and must not be invoked on cold launch.
  @Deprecated('Use connect() from the Connect button only')
  Future<bool> autoConnectOnLaunch() async {
    onStatus('Connect from the button — auto-connect is disabled');
    if (!autoConnectOnLaunchEnabled) {
      return false;
    }
    return connect();
  }

  Future<bool> connect() async {
    try {
      onStatus('Connecting to ${RptConfig.host}:${RptConfig.port} (RPT2)…');
      final result = await _channel.invokeMethod<dynamic>('connect', {
        'host': RptConfig.host,
        'port': RptConfig.port,
        'fullTunnel': RptConfig.fullTunnel,
        'sessionName': RptConfig.sessionName,
        'route': RptConfig.defaultRoute,
        'autoConnect': false,
      });
      final ok = isConnectSuccess(result);
      onStatus(mapConnectStatusMessage(result));
      return ok;
    } on PlatformException catch (e) {
      onStatus('VPN error: ${e.message ?? e.code}');
      return false;
    } on MissingPluginException {
      onStatus(
        'Native VPN channel not bound on this platform build. '
        'Android/Windows: use the release installer. '
        'iOS/macOS: wire restore_privacy/vpn + Packet Tunnel on a Mac '
        '(see client_app/APPLE_BUILD.md).',
      );
      return false;
    }
  }

  /// Stop system VPN (explicit Disconnect only — not on minimize).
  Future<void> disconnect() async {
    try {
      final result = await _channel.invokeMethod<dynamic>('disconnect');
      if (result is Map) {
        final msg = result['message']?.toString().trim();
        onStatus(
          (msg != null && msg.isNotEmpty)
              ? msg
              : kDisconnectedResidualIpMessage,
        );
      } else {
        onStatus(kDisconnectedResidualIpMessage);
      }
    } catch (_) {
      onStatus(kDisconnectedResidualIpMessage);
    }
  }

  /// Rehydrate UI after resume/minimize — does **not** start or stop the tunnel.
  Future<VpnSessionSnapshot> querySession() async {
    try {
      final result = await _channel.invokeMethod<dynamic>('status');
      if (result is Map) {
        final ok = result['connected'] == true || isConnectSuccess(result);
        final ip = result['vpnIp']?.toString().trim() ?? '';
        final msg = result['message']?.toString().trim() ?? '';
        return VpnSessionSnapshot(
          connected: ok,
          vpnIp: ip.isEmpty ? null : ip,
          message: msg.isEmpty ? null : msg,
        );
      }
    } on MissingPluginException {
      // Host without native channel
    } catch (_) {}
    return const VpnSessionSnapshot(connected: false);
  }
}

/// Snapshot of native VPN session for UI rehydrate (minimize/resume).
class VpnSessionSnapshot {
  final bool connected;
  final String? vpnIp;
  final String? message;

  const VpnSessionSnapshot({
    required this.connected,
    this.vpnIp,
    this.message,
  });
}
