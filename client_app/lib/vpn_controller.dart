import 'dart:async';

import 'package:flutter/services.dart';

import 'connect_status.dart';
import 'rpt_config.dart';
import 'theme.dart';

/// Platform channel to Android VpnService / Windows plugin hooks.
class VpnController {
  static const MethodChannel _channel = MethodChannel('restore_privacy/vpn');

  /// How often to refresh the Connecting status line while native work runs.
  static const Duration connectingProgressInterval = Duration(seconds: 3);

  final void Function(String) onStatus;

  VpnController({required this.onStatus});

  /// Compile-time default is off; runtime Settings may enable autoconnect.
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

  /// Pre-Connect (macOS): register the product **Packet Tunnel** profile in OS VPN
  /// preferences so configuration exists before Connect. Does not start the tunnel.
  /// Never configures L2TP / Cisco IPsec / IKEv2.
  ///
  /// Returns true when native reports prepared/ok. Permission failures still return
  /// false but set [onStatus] with Allow guidance.
  Future<bool> preparePacketTunnelConfiguration() async {
    try {
      final result = await _channel.invokeMethod<dynamic>('prepareVpn', {
        'host': RptConfig.host,
        'port': RptConfig.port,
        'fullTunnel': true,
        'sessionName': RptConfig.sessionName,
      });
      final msg = mapPrepareVpnStatusMessage(result);
      // Only treat dual ok+prepared as success (failed NE save is never prepared).
      if (isPrepareVpnSuccess(result)) {
        onStatus(msg);
        return isProductPacketTunnelPrepareResult(result);
      }
      onStatus(msg);
      if (shouldPromptOpenVpnSystemSettings(result)) {
        final already =
            result is Map && result['openedVpnSettings'] == true;
        if (!already) {
          await openVpnSystemSettings(reportStatus: false);
        }
      }
      return false;
    } on MissingPluginException {
      // Non-macOS / host without channel — nothing to prepare.
      return false;
    } on PlatformException catch (e) {
      onStatus(
        'Could not pre-register Packet Tunnel (${e.message ?? e.code}). '
        'Allow Restore Privacy under VPN & Filters if asked — not L2TP/IKEv2.',
      );
      return false;
    }
  }

  /// Product Connect: keep **Connecting** status until native full-tunnel result.
  ///
  /// Android HELLO + TUN can take tens of seconds on mobile UDP — do not drop
  /// the Connecting line early. Progress ticks update the subtitle only.
  Future<bool> connect() async {
    Timer? progress;
    final started = DateTime.now();
    void tickConnecting() {
      final elapsed = DateTime.now().difference(started).inSeconds;
      onStatus(
        connectingStatusMessage(
          host: RptConfig.host,
          port: RptConfig.port,
          elapsedSeconds: elapsed > 0 ? elapsed : null,
        ),
      );
    }

    try {
      tickConnecting();
      progress = Timer.periodic(connectingProgressInterval, (_) {
        tickConnecting();
      });
      final result = await _channel.invokeMethod<dynamic>('connect', {
        'host': RptConfig.host,
        'port': RptConfig.port,
        'fullTunnel': RptConfig.fullTunnel,
        'sessionName': RptConfig.sessionName,
        'route': RptConfig.defaultRoute,
        'autoConnect': false,
      });
      progress.cancel();
      progress = null;

      // If native says still connecting (double-tap / race), keep waiting via status.
      if (isConnectingInProgress(result) && !isConnectSuccess(result)) {
        onStatus(mapConnectStatusMessage(result));
        final ok = await _waitForFullTunnel();
        return ok;
      }

      final ok = isConnectSuccess(result);
      // Keep residual-honest failure/success as product status — never overwrite
      // with open-settings feedback (that would hide Open VPN settings UI).
      onStatus(mapConnectStatusMessage(result));
      // macOS NE permission / host-only HELLO: native usually opens Settings;
      // if not, open without replacing the failure status (log-only feedback).
      if (!ok && shouldPromptOpenVpnSystemSettings(result)) {
        final already =
            result is Map && result['openedVpnSettings'] == true;
        if (!already) {
          await openVpnSystemSettings(reportStatus: false);
        }
      }
      return ok;
    } on PlatformException catch (e) {
      progress?.cancel();
      onStatus('VPN error: ${e.message ?? e.code}');
      return false;
    } on MissingPluginException {
      progress?.cancel();
      onStatus(
        'Native VPN channel not bound on this platform build. '
        'Android/Windows: use the release installer. '
        'iOS/macOS: wire restore_privacy/vpn + Packet Tunnel on a Mac '
        '(see client_app/APPLE_BUILD.md).',
      );
      return false;
    } finally {
      progress?.cancel();
    }
  }

  /// Open System Settings → Network / VPN so the user can Allow the configuration.
  ///
  /// macOS: native `openVpnSettings` (NSWorkspace deep-link). Other platforms: no-op.
  ///
  /// By default **does not** call [onStatus] — open feedback must stay log-only so the
  /// residual NE failure status (and Open VPN settings control) remain visible.
  /// Pass [reportStatus]: true only for callers that intentionally replace the card.
  Future<bool> openVpnSystemSettings({bool reportStatus = false}) async {
    try {
      final result = await _channel.invokeMethod<dynamic>('openVpnSettings');
      if (result is Map) {
        final opened = result['opened'] == true || result['ok'] == true;
        if (reportStatus) {
          final msg = result['message']?.toString().trim();
          if (msg != null && msg.isNotEmpty) {
            onStatus(msg);
          } else {
            onStatus(
              opened
                  ? kOpenVpnSettingsOpenedFeedback
                  : kOpenVpnSettingsFailedFeedback,
            );
          }
        }
        return opened;
      }
      if (reportStatus) onStatus(kOpenVpnSettingsFailedFeedback);
      return false;
    } on MissingPluginException {
      if (reportStatus) {
        onStatus(
          'Open System Settings → Network → VPN & Filters, Allow Restore Privacy, then Connect again.',
        );
      }
      return false;
    } on PlatformException catch (e) {
      if (reportStatus) {
        onStatus(
          'Could not open System Settings (${e.message ?? e.code}). '
          'Manually: System Settings → Network → VPN & Filters.',
        );
      }
      return false;
    }
  }

  /// Poll native session until full tunnel is up or give up (Android in-progress).
  Future<bool> _waitForFullTunnel({
    Duration maxWait = const Duration(seconds: 75),
    Duration pollEvery = const Duration(seconds: 2),
  }) async {
    final deadline = DateTime.now().add(maxWait);
    while (DateTime.now().isBefore(deadline)) {
      await Future<void>.delayed(pollEvery);
      final snap = await querySession();
      if (snap.connected) {
        onStatus(
          snap.message ??
              plainConnectedStatus(vpnIp: snap.vpnIp, residual: true),
        );
        return true;
      }
      if (snap.connecting) {
        onStatus(
          snap.message ??
              connectingStatusMessage(
                host: RptConfig.host,
                port: RptConfig.port,
              ),
        );
        continue;
      }
      // Not connected and not connecting — failed or idle
      if ((snap.message ?? '').toLowerCase().contains('fail')) {
        onStatus(snap.message!);
        return false;
      }
    }
    onStatus(
      'Connect timed out waiting for full tunnel — check network/UDP to '
      '${RptConfig.host}:${RptConfig.port}, then try Connect again.',
    );
    return false;
  }

  /// Stop system VPN (explicit Disconnect only — not on minimize).
  ///
  /// Native path must tear down the OS Packet Tunnel so Network settings
  /// toggles off with the app. Polls status briefly so UI does not claim
  /// disconnected while the system tunnel is still Connected.
  Future<void> disconnect() async {
    try {
      final result = await _channel.invokeMethod<dynamic>('disconnect');
      // Confirm system tunnel is down (status channel / residual still-live).
      for (var i = 0; i < 15; i++) {
        final snap = await querySession();
        if (!snap.connected && !snap.connecting) break;
        await Future<void>.delayed(const Duration(milliseconds: 150));
        if (i == 7) {
          // Second native stop if still live mid-poll.
          try {
            await _channel.invokeMethod<dynamic>('disconnect');
          } catch (_) {}
        }
      }
      final still = await querySession();
      if (still.connected || still.connecting) {
        onStatus(
          'Disconnect issued but system VPN may still be active — '
          'toggle off Restore Privacy in System Settings → Network → VPN & Filters, '
          'or press Disconnect again.',
        );
        return;
      }
      if (result is Map) {
        final msg = result['message']?.toString().trim();
        final stopped = result['systemVpnStopped'];
        if (stopped == false) {
          onStatus(
            (msg != null && msg.isNotEmpty)
                ? msg
                : 'Disconnect issued but system VPN may still be active.',
          );
          return;
        }
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
        final connecting = result['connecting'] == true ||
            isConnectingInProgress(result);
        final ok = !connecting &&
            (result['connected'] == true || isConnectSuccess(result));
        final ip = result['vpnIp']?.toString().trim() ?? '';
        final msg = result['message']?.toString().trim() ?? '';
        return VpnSessionSnapshot(
          connected: ok,
          connecting: connecting,
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
  final bool connecting;
  final String? vpnIp;
  final String? message;

  const VpnSessionSnapshot({
    required this.connected,
    this.connecting = false,
    this.vpnIp,
    this.message,
  });
}
