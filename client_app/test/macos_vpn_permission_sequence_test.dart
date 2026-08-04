/// macOS / Apple VPN permission prompts must be sequential, not a simultaneous burst.
library;

import 'dart:io';

import 'package:flutter/foundation.dart' show TargetPlatform;
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/macos_vpn_permission_sequence.dart';

void main() {
  test('permission sequence order is prepare → await → settings → connect', () {
    final order = macosVpnPermissionSequenceOrder();
    expect(order.length, 4);
    expect(order.first, MacosVpnPermissionStep.prepareProfile);
    expect(order[1], MacosVpnPermissionStep.awaitPrepareResult);
    expect(order[2], MacosVpnPermissionStep.openSystemSettingsIfNeeded);
    expect(order.last, MacosVpnPermissionStep.connectTunnel);
    // Settings never before prepare finishes.
    final settingsIdx = order.indexOf(
      MacosVpnPermissionStep.openSystemSettingsIfNeeded,
    );
    final prepareIdx = order.indexOf(MacosVpnPermissionStep.prepareProfile);
    expect(settingsIdx, greaterThan(prepareIdx));
    final connectIdx = order.indexOf(MacosVpnPermissionStep.connectTunnel);
    expect(connectIdx, greaterThan(settingsIdx));
  });

  test('prepare must not auto-open System Settings in the same tick', () {
    expect(macosShouldDeferOpenSettingsUntilAfterPrepare(), isTrue);
    expect(macosPrepareShouldAutoOpenSystemSettings(), isFalse);
  });

  test('after prepare: ready / settings / retry / missing NE actions', () {
    expect(
      macosVpnActionAfterPrepare(prepared: true, ok: true),
      MacosVpnAfterPrepareAction.readyForConnect,
    );
    expect(
      macosVpnActionAfterPrepare(
        prepared: false,
        ok: false,
        needsVpnSystemSettingsApproval: true,
      ),
      MacosVpnAfterPrepareAction.openSystemSettingsThenConnect,
    );
    expect(
      macosVpnActionAfterPrepare(prepared: false, ok: false),
      MacosVpnAfterPrepareAction.retryPrepare,
    );
    expect(
      macosVpnActionAfterPrepare(
        prepared: false,
        ok: false,
        needsTeamResidualSign: true,
        hostHasPacketTunnelEntitlement: false,
      ),
      MacosVpnAfterPrepareAction.hostMissingNetworkExtension,
    );
  });

  test('connect may open Settings only after prepare sequence completed', () {
    expect(
      macosConnectMayOpenSystemSettingsOnPermissionDenial(
        prepareSequenceCompleted: false,
      ),
      isFalse,
    );
    expect(
      macosConnectMayOpenSystemSettingsOnPermissionDenial(
        prepareSequenceCompleted: true,
      ),
      isTrue,
    );
  });

  test('native RptVpnChannel prepare gates openSettingsOnDenial', () {
    // Structural: Swift must accept openSettingsOnDenial and default false.
    final src = File('macos/NativePrep/RptVpnChannel.swift').readAsStringSync();
    expect(src.contains('openSettingsOnDenial'), isTrue);
    expect(src.contains('openSettingsOnDenial: Bool = false'), isTrue);
    // Must not unconditionally open settings on every permission failure.
    expect(
      src.contains('if permissionClass && openSettingsOnDenial'),
      isTrue,
    );
  });

  test('applePlatformNeedsVpnPrepare covers macOS and iOS', () {
    expect(applePlatformNeedsVpnPrepare(TargetPlatform.macOS), isTrue);
    expect(applePlatformNeedsVpnPrepare(TargetPlatform.iOS), isTrue);
    expect(applePlatformNeedsVpnPrepare(TargetPlatform.android), isFalse);
  });
}

