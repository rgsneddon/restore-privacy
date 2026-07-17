import 'dart:async';

import 'package:flutter/services.dart';

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
      if (result is Map) {
        final ok = result['ok'] == true;
        onStatus(result['message']?.toString() ?? (ok ? 'Connected' : 'Failed'));
        return ok;
      }
      onStatus('Connected');
      return true;
    } on PlatformException catch (e) {
      onStatus('VPN error: ${e.message}');
      return false;
    } on MissingPluginException {
      // Desktop/iOS prep without native plugin yet — surface honest status
      onStatus(
        'Native VPN channel not bound on this platform build; '
        'RPT full-tunnel plugin will attach on Android/Windows release builds.',
      );
      return false;
    }
  }

  Future<void> disconnect() async {
    try {
      await _channel.invokeMethod<void>('disconnect');
      onStatus('Disconnected');
    } catch (_) {
      onStatus('Disconnected');
    }
  }
}
