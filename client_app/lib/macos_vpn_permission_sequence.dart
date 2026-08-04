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
