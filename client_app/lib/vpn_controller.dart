import 'dart:async';

import 'package:flutter/foundation.dart'
    show TargetPlatform, defaultTargetPlatform, kIsWeb;
import 'package:flutter/services.dart';

import 'connect_status.dart';
import 'leak_test.dart';
import 'macos_vpn_permission_sequence.dart';
import 'rpt_config.dart';
import 'settings_store.dart';
import 'suite_update.dart';
import 'theme.dart';

/// Platform channel to Android VpnService / Windows plugin hooks.
class VpnController {
  static const MethodChannel _channel = MethodChannel('restore_privacy/vpn');

  /// How often to refresh the Connecting status line while native work runs.
  static const Duration connectingProgressInterval = Duration(seconds: 3);

  final void Function(String) onStatus;

  /// Legacy residual UPDATE_PUSH callback (unused — push receive removed).
  void Function(dynamic rawPayload)? onUpdatePush;

  /// Current product settings for gated receive (set by TunnelHome).
  ProductSettings settingsForUpdatePush = ProductSettings.defaults;

  VpnController({required this.onStatus});

  /// Residual UPDATE_PUSH host handler removed (manual client update only).
  void installUpdatePushHandler() {
    // No-op: product does not receive or apply admin push packages.
  }

  /// Residual UPDATE_PUSH poll/apply removed — always skip.
  Future<Map<String, dynamic>> pollAndApplyUpdatePush({
    ProductSettings? settings,
  }) async {
    // settings ignored — push-receive removed
    return {
      'ok': true,
      'skipped': true,
      'reason': 'client update push disabled — update manually',
      'store': null,
      'disabled': true,
    };
  }

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
  ///
  /// By default does **not** auto-open System Settings in the same tick as prepare
  /// (see [macos_vpn_permission_sequence]) so the Allow dialog is not missed.
  /// Use [preparePacketTunnelSequenced] for the full ordered path.
  Future<bool> preparePacketTunnelConfiguration({
    bool openSettingsOnDenial = false,
  }) async {
    try {
      final result = await _channel.invokeMethod<dynamic>('prepareVpn', {
        'host': RptConfig.host,
        'port': RptConfig.port,
        'fullTunnel': true,
        'sessionName': RptConfig.sessionName,
        // Native must not race System Settings open during prepare.
        'openSettingsOnDenial': openSettingsOnDenial &&
            !macosShouldDeferOpenSettingsUntilAfterPrepare(),
      });
      final msg = mapPrepareVpnStatusMessage(result);
      // Only treat dual ok+prepared as success (failed NE save is never prepared).
      if (isPrepareVpnSuccess(result)) {
        onStatus(msg);
        return isProductPacketTunnelPrepareResult(result);
      }
      onStatus(msg);
      // Optional legacy path only when caller opts in AND sequence allows.
      if (openSettingsOnDenial &&
          !macosShouldDeferOpenSettingsUntilAfterPrepare() &&
          shouldAutoOpenVpnSystemSettings(result)) {
        await openVpnSystemSettings(reportStatus: false);
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

  /// Ordered macOS VPN readiness: prepare → await → open Settings if needed.
  ///
  /// Does **not** call Connect — that remains a separate user action so system
  /// popups never fire as a simultaneous burst.
  Future<MacosVpnPrepOutcome> preparePacketTunnelSequenced() async {
    // Step 1–2: prepare only (no Settings open in-band).
    Map<String, dynamic>? raw;
    try {
      final result = await _channel.invokeMethod<dynamic>('prepareVpn', {
        'host': RptConfig.host,
        'port': RptConfig.port,
        'fullTunnel': true,
        'sessionName': RptConfig.sessionName,
        'openSettingsOnDenial': false,
      });
      if (result is Map) {
        raw = Map<String, dynamic>.from(
          result.map((k, v) => MapEntry(k.toString(), v)),
        );
      }
    } on MissingPluginException {
      return const MacosVpnPrepOutcome(
        prepared: false,
        openedSettings: false,
        action: MacosVpnAfterPrepareAction.retryPrepare,
        message: 'VPN prepare not bound on this build',
      );
    } on PlatformException catch (e) {
      return MacosVpnPrepOutcome(
        prepared: false,
        openedSettings: false,
        action: MacosVpnAfterPrepareAction.retryPrepare,
        message: e.message ?? e.code,
      );
    }

    final prepared = isPrepareVpnSuccess(raw);
    final needsAllow = shouldAutoOpenVpnSystemSettings(raw) ||
        (raw?['needsVpnSystemSettingsApproval'] == true);
    final needsSign = raw?['needsTeamResidualSign'] == true;
    final hasNe = raw?['hostHasPacketTunnelEntitlement'] != false;
    final action = macosVpnActionAfterPrepare(
      prepared: prepared,
      ok: prepared,
      needsVpnSystemSettingsApproval: needsAllow,
      needsTeamResidualSign: needsSign,
      hostHasPacketTunnelEntitlement: hasNe,
    );
    final msg = mapPrepareVpnStatusMessage(raw);
    onStatus(msg);

    var opened = false;
    if (action == MacosVpnAfterPrepareAction.openSystemSettingsThenConnect) {
      // Step 3: open Settings only after prepare completed.
      opened = await openVpnSystemSettings(reportStatus: false);
    }
    return MacosVpnPrepOutcome(
      prepared: prepared,
      openedSettings: opened,
      action: action,
      message: msg,
      needsVpnSystemSettingsApproval: needsAllow,
    );
  }

  /// Product Connect: keep **Connecting** status until native full-tunnel result.
  ///
  /// Android HELLO + TUN can take tens of seconds on mobile UDP — do not drop
  /// the Connecting line early. Progress ticks update the subtitle only.
  Future<bool> connect({
    /// Optional residual stack override so Connect uses Flutter Settings, not stale native defaults.
    bool? residualIpv4,
    bool? residualIpv6,
    /// Privacy-scale (Android + Apple): lean residual defaults OFF when null/false.
    bool? privacyTrafficShape,
    bool? privacyOuterObfuscation,
    bool? privacyMultihop,
  }) async {
    Timer? progress;
    final started = DateTime.now();
    var latchedSuccess = false;
    void stopProgress() {
      progress?.cancel();
      progress = null;
    }

    void tickConnecting() {
      if (latchedSuccess) return;
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
      // macOS: register Packet Tunnel in System VPN prefs before start so the
      // OS can show Allow / install the configuration (not a silent no-op).
      if (!kIsWeb && defaultTargetPlatform == TargetPlatform.macOS) {
        await preparePacketTunnelSequenced();
      }
      // Push dual-stack + privacy-scale prefs before native tunnel starts.
      await syncProductSettingsToNative(
        residualIpv4: residualIpv4 ?? true,
        residualIpv6: residualIpv6 ?? true,
        privacyTrafficShape: privacyTrafficShape,
        privacyOuterObfuscation: privacyOuterObfuscation,
        privacyMultihop: privacyMultihop,
      );
      tickConnecting();
      progress = Timer.periodic(connectingProgressInterval, (_) {
        tickConnecting();
      });
      final result = await _channel.invokeMethod<dynamic>('connect', {
        'host': RptConfig.host,
        'port': RptConfig.port,
        // Wipe-drain / preferred-down: native tries these after preferred HELLO fails
        'alternateHosts': RptConfig.alternateHosts,
        'fullTunnel': RptConfig.fullTunnel,
        'sessionName': RptConfig.sessionName,
        'route': RptConfig.defaultRoute,
        'autoConnect': false,
        // Android privacy-scale lean defaults OFF unless Settings enabled.
        'trafficShape': privacyTrafficShape ?? false,
        'outerObfuscation': privacyOuterObfuscation ?? false,
      });
      // If native says still connecting (double-tap / race), keep waiting via status.
      if (isConnectingInProgress(result) && !isConnectSuccess(result)) {
        onStatus(mapConnectStatusMessage(result));
        final ok = await _waitForFullTunnel();
        if (ok) latchedSuccess = true;
        stopProgress();
        return ok;
      }

      final ok = isConnectSuccess(result);
      if (ok) latchedSuccess = true;
      stopProgress();
      // Keep residual-honest failure/success as product status — never overwrite
      // with open-settings feedback (that would hide Open VPN settings UI).
      onStatus(mapConnectStatusMessage(result));
      // Auto-open Settings only on strict NE permission denial — never on ordinary
      // tunnel start failure or missing host NE (Team residual re-sign).
      if (!ok && shouldAutoOpenVpnSystemSettings(result)) {
        await openVpnSystemSettings(reportStatus: false);
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

  /// Push product Settings dual-stack + privacy scale into native App Group
  /// so Packet Tunnel / Connect success maps match Flutter SharedPreferences.
  Future<void> syncProductSettingsToNative({
    required bool residualIpv4,
    required bool residualIpv6,
    bool? privacyTrafficShape,
    bool? privacyOuterObfuscation,
    bool? privacyMultihop,
  }) async {
    try {
      await _channel.invokeMethod<dynamic>('setResidualStack', {
        'ipv4': residualIpv4,
        'ipv6': residualIpv6,
      });
    } on MissingPluginException {
      // Non-Apple / host without channel.
    } catch (_) {
      // Best-effort — Connect still reads App Group defaults.
    }
    if (privacyTrafficShape == null &&
        privacyOuterObfuscation == null &&
        privacyMultihop == null) {
      return;
    }
    try {
      await _channel.invokeMethod<dynamic>('setPrivacyScale', {
        if (privacyTrafficShape != null) 'trafficShape': privacyTrafficShape,
        if (privacyOuterObfuscation != null)
          'outerObfuscation': privacyOuterObfuscation,
        if (privacyMultihop != null) 'multihop': privacyMultihop,
      });
    } on MissingPluginException {
    } catch (_) {}
  }

  /// Rehydrate UI after resume/minimize — does **not** start or stop the tunnel.
  Future<VpnSessionSnapshot> querySession() async {
    try {
      final result = await _channel.invokeMethod<dynamic>('status');
      if (result is Map) {
        // Residual success wins over a stale connecting flag / wait string.
        final ok = isConnectSuccess(result) ||
            (result['connected'] == true &&
                result['fullTunnelActive'] != false &&
                result['hostOnlySession'] != true);
        final connecting = !ok &&
            (result['connecting'] == true || isConnectingInProgress(result));
        final ip = result['vpnIp']?.toString().trim() ?? '';
        final rawMsg = result['message']?.toString().trim() ?? '';
        // Rebuild honesty from flags when present (status rehydrate contract).
        // Never re-surface "waiting for full tunnel" once residual is up.
        final msg = ok
            ? mapConnectStatusMessage(result)
            : (connecting
                ? (rawMsg.isNotEmpty
                    ? rawMsg
                    : connectingStatusMessage(
                        host: RptConfig.host,
                        port: RptConfig.port,
                      ))
                : rawMsg);
        bool? ipv6;
        if (result['ipv6Protected'] is bool) {
          ipv6 = result['ipv6Protected'] as bool;
        }
        bool? ipv4;
        if (result['ipv4Residual'] is bool) {
          ipv4 = result['ipv4Residual'] as bool;
        }
        final flags = parseNativeResidualStatus(result);
        final dnsOnly = resolveDnsTunnelOnly(flags: flags);
        return VpnSessionSnapshot(
          connected: ok,
          connecting: connecting,
          vpnIp: ip.isEmpty ? null : ip,
          message: msg.isEmpty ? null : msg,
          ipv6Protected: ipv6,
          ipv4Residual: ipv4,
          residualCaptureActive: flags.residualCaptureActive,
          dnsTunnelOnly: dnsOnly,
          fullTunnelActive: flags.fullTunnelActive,
          rawStatus: Map<String, dynamic>.from(
            result.map((k, v) => MapEntry(k.toString(), v)),
          ),
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
  final bool? ipv6Protected;
  final bool? ipv4Residual;

  /// Residual public-IP capture active (from native status parse).
  final bool residualCaptureActive;

  /// Live tunnel-DNS-only posture (native flag or product DNS plan).
  final bool dnsTunnelOnly;

  final bool fullTunnelActive;

  /// Raw status map when available (watchdog / leak-test).
  final Map<String, dynamic>? rawStatus;

  const VpnSessionSnapshot({
    required this.connected,
    this.connecting = false,
    this.vpnIp,
    this.message,
    this.ipv6Protected,
    this.ipv4Residual,
    this.residualCaptureActive = false,
    this.dnsTunnelOnly = false,
    this.fullTunnelActive = false,
    this.rawStatus,
  });
}
