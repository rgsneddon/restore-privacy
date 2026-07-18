import 'package:flutter/services.dart';

import 'connect_status.dart';
import 'rpt_config.dart';

/// Platform channel to Android VpnService / Windows plugin hooks.
class VpnController {
  static const MethodChannel _channel = MethodChannel('restore_privacy/vpn');

  final void Function(String) onStatus;

  VpnController({required this.onStatus});

  /// Primary launch path — auto-connect to RPT node with full VPN intent.
  Future<bool> autoConnectOnLaunch() async {
    onStatus('Auto-connect on launch…');
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
        'autoConnect': true,
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

  /// Stop system Packet Tunnel (same native path as app-quit hooks).
  Future<void> disconnect() async {
    try {
      final result = await _channel.invokeMethod<dynamic>('disconnect');
      if (result is Map) {
        final msg = result['message']?.toString().trim();
        onStatus(
          (msg != null && msg.isNotEmpty)
              ? msg
              : 'Disconnected — system VPN stopped; residual public IP restored',
        );
      } else {
        onStatus('Disconnected — system VPN stopped; residual public IP restored');
      }
    } catch (_) {
      onStatus('Disconnected — system VPN stopped; residual public IP restored');
    }
  }
}
