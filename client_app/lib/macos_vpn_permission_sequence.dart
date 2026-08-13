/// Pure Apple residual VPN permission sequencing (no simultaneous popup burst).
///
/// Product bug: prepare + auto-open System Settings + Connect re-register all
/// raced OS dialogs so the Packet Tunnel → System Settings allow step was missed.
/// This module defines an ordered plan so callers await each step distinctly.
///
/// Used on **macOS and iOS** (both register Packet Tunnel NE before Connect).
library;

import 'package:flutter/foundation.dart'
    show TargetPlatform, defaultTargetPlatform, kIsWeb;

/// True when the shared client must run native prepare before Connect.
///
/// macOS and iOS both save product Packet Tunnel into system VPN preferences.
/// Other platforms use different tunnels (Android VpnService, Windows, etc.).
bool applePlatformNeedsVpnPrepare([TargetPlatform? platform]) {
  if (kIsWeb) return false;
  final p = platform ?? defaultTargetPlatform;
  return p == TargetPlatform.macOS || p == TargetPlatform.iOS;
}

/// Ordered steps for macOS VPN profile allow / System Settings.
enum MacosVpnPermissionStep {
  /// Register Packet Tunnel NE profile only (may show one Allow dialog).
  prepareProfile,

  /// Wait for prepare callback — do not open Settings in the same tick.
  awaitPrepareResult,

  /// Open System Settings → Network / VPN only if prepare reported needsAllow.
  openSystemSettingsIfNeeded,

  /// Start tunnel only after prepare (and optional Settings) completed.
  connectTunnel,
}

/// Canonical order — never open Settings before prepare finishes.
List<MacosVpnPermissionStep> macosVpnPermissionSequenceOrder() => const [
      MacosVpnPermissionStep.prepareProfile,
      MacosVpnPermissionStep.awaitPrepareResult,
      MacosVpnPermissionStep.openSystemSettingsIfNeeded,
      MacosVpnPermissionStep.connectTunnel,
    ];

/// True when System Settings open must wait until prepare returns (not mid-dialog).
bool macosShouldDeferOpenSettingsUntilAfterPrepare() => true;

/// Pure: next action after a prepare result map (native or Dart-normalized).
enum MacosVpnAfterPrepareAction {
  /// Profile ready — user may Connect (no Settings).
  readyForConnect,

  /// Open System Settings for Allow, then Connect.
  openSystemSettingsThenConnect,

  /// Prepare failed without permission class — retry prepare, do not open Settings.
  retryPrepare,

  /// Host missing NE entitlement — do not open Settings as a fix.
  hostMissingNetworkExtension,
}

/// Decide post-prepare action from native-style result fields.
///
/// [hostHasPacketTunnelEntitlement] defaults **true** (not applicable / present).
/// Only an explicit `false` (catalog macOS DevID without host NE) routes to
/// [MacosVpnAfterPrepareAction.hostMissingNetworkExtension]. Missing/null must
/// **not** be treated as missing — iOS prepare maps omit the key entirely.
MacosVpnAfterPrepareAction macosVpnActionAfterPrepare({
  required bool prepared,
  required bool ok,
  bool needsVpnSystemSettingsApproval = false,
  bool needsTeamResidualSign = false,
  bool hostHasPacketTunnelEntitlement = true,
}) {
  if (needsTeamResidualSign || !hostHasPacketTunnelEntitlement) {
    return MacosVpnAfterPrepareAction.hostMissingNetworkExtension;
  }
  if (prepared && ok) {
    return MacosVpnAfterPrepareAction.readyForConnect;
  }
  if (needsVpnSystemSettingsApproval) {
    return MacosVpnAfterPrepareAction.openSystemSettingsThenConnect;
  }
  return MacosVpnAfterPrepareAction.retryPrepare;
}

/// True only when native map **explicitly** reports host Packet Tunnel NE missing.
///
/// Matches [isPrepareVpnSuccess] honesty: `hostHasPacketTunnelEntitlement == false`
/// rejects; null/absent means the field is not applicable (iOS, residual-capable).
bool prepareMapExplicitlyMissingHostNe(Map? raw) {
  if (raw == null) return false;
  return raw['hostHasPacketTunnelEntitlement'] == false;
}

/// True when native map explicitly requires Team residual re-sign (macOS catalog).
bool prepareMapNeedsTeamResidualSign(Map? raw) {
  if (raw == null) return false;
  return raw['needsTeamResidualSign'] == true;
}

/// Pure: classify a native prepareVpn channel map into the post-prepare action.
///
/// This is the real decision path used by [VpnController.preparePacketTunnelSequenced]
/// — tests must feed iOS-shaped maps (no host NE key) and macOS DevID maps here.
MacosVpnAfterPrepareAction macosVpnActionFromPrepareMap(
  Map? raw, {
  required bool prepared,
  bool? needsVpnSystemSettingsApproval,
}) {
  final needsAllow = needsVpnSystemSettingsApproval ??
      (raw?['needsVpnSystemSettingsApproval'] == true);
  final needsSign = prepareMapNeedsTeamResidualSign(raw);
  // Explicit false only — missing key is N/A (iOS), not host-NE failure.
  final hostHasNe = !prepareMapExplicitlyMissingHostNe(raw);
  return macosVpnActionAfterPrepare(
    prepared: prepared,
    ok: prepared,
    needsVpnSystemSettingsApproval: needsAllow,
    needsTeamResidualSign: needsSign,
    hostHasPacketTunnelEntitlement: hostHasNe,
  );
}

/// Whether native prepare should auto-open System Settings (product: **false**).
///
/// Flutter sequences open via [MacosVpnPermissionStep.openSystemSettingsIfNeeded]
/// after prepare completes so the Allow dialog is not lost in a burst.
bool macosPrepareShouldAutoOpenSystemSettings() => false;

/// Whether connect failure may open System Settings (only after prepare path done).
bool macosConnectMayOpenSystemSettingsOnPermissionDenial({
  required bool prepareSequenceCompleted,
}) =>
    prepareSequenceCompleted;

/// True only when prepare finished successfully and Connect may call startTunnel.
///
/// Product bug (1.2.2 free monopin): Connect always raced startTunnel after a
/// failed prepare (needs Allow / missing host NE). That stole focus from the
/// delayed Allow dialog and left residual "no Connect" after the user Allowed.
/// Fail-fast until [MacosVpnAfterPrepareAction.readyForConnect], then the user
/// presses Connect again after Allow.
bool macosConnectShouldInvokeStartTunnel(MacosVpnAfterPrepareAction action) =>
    action == MacosVpnAfterPrepareAction.readyForConnect;

/// Honest status when Connect stops because prepare is not ready for startTunnel.
String macosConnectBlockedByPrepareMessage(MacosVpnPrepOutcome prep) {
  final m = prep.message.trim();
  if (m.isNotEmpty) return m;
  switch (prep.action) {
    case MacosVpnAfterPrepareAction.openSystemSettingsThenConnect:
      return 'Allow Restore Privacy Packet Tunnel in System Settings → Network → '
          'VPN & Filters (choose Allow if macOS asks), then press Connect again.';
    case MacosVpnAfterPrepareAction.hostMissingNetworkExtension:
      return 'This build cannot register residual Packet Tunnel (missing host NE). '
          'Re-download the free macOS monopin or re-sign with Team residual.';
    case MacosVpnAfterPrepareAction.retryPrepare:
      return 'Packet Tunnel is not registered yet. Press Connect again after '
          'Allowing Restore Privacy if macOS asked.';
    case MacosVpnAfterPrepareAction.readyForConnect:
      return 'Restore Privacy Packet Tunnel is ready — press Connect.';
  }
}

/// Result of [VpnController.preparePacketTunnelSequenced].
class MacosVpnPrepOutcome {
  const MacosVpnPrepOutcome({
    required this.prepared,
    required this.openedSettings,
    required this.action,
    required this.message,
    this.needsVpnSystemSettingsApproval = false,
  });

  final bool prepared;
  final bool openedSettings;
  final MacosVpnAfterPrepareAction action;
  final String message;
  final bool needsVpnSystemSettingsApproval;
}
