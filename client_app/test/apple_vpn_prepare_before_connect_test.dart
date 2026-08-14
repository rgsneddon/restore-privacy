/// Flutter Apple path: prepare-before-connect on macOS **and** iOS.
import 'dart:io';

import 'package:flutter/foundation.dart' show TargetPlatform;
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/connect_status.dart';
import 'package:restore_privacy_client/macos_vpn_permission_sequence.dart';

void main() {
  test('applePlatformNeedsVpnPrepare is true for macOS and iOS only', () {
    expect(applePlatformNeedsVpnPrepare(TargetPlatform.macOS), isTrue);
    expect(applePlatformNeedsVpnPrepare(TargetPlatform.iOS), isTrue);
    expect(applePlatformNeedsVpnPrepare(TargetPlatform.android), isFalse);
    expect(applePlatformNeedsVpnPrepare(TargetPlatform.windows), isFalse);
    expect(applePlatformNeedsVpnPrepare(TargetPlatform.linux), isFalse);
  });

  test('vpn_controller connect prepares on Apple via applePlatformNeedsVpnPrepare',
      () {
    final src = File('lib/vpn_controller.dart').readAsStringSync();
    // Must gate prepare on shared Apple helper (not macOS-only).
    expect(src.contains('applePlatformNeedsVpnPrepare'), isTrue);
    expect(src.contains('preparePacketTunnelSequenced'), isTrue);
    // Fail-fast: do not race startTunnel when prepare still needs Allow / re-sign.
    expect(src.contains('macosConnectShouldInvokeStartTunnel'), isTrue);
    expect(src.contains('Duration(seconds: 9)'), isTrue);
    expect(src.contains('macosConnectBlockedByPrepareMessage'), isTrue);
    // Forbidden: macOS-only prepare gate that excludes iOS.
    expect(
      RegExp(
        r"defaultTargetPlatform\s*==\s*TargetPlatform\.macOS\s*\)\s*\{\s*"
        r"await preparePacketTunnelSequenced",
        multiLine: true,
      ).hasMatch(src),
      isFalse,
      reason: 'connect must not prepare on macOS only',
    );
  });

  test('main.dart first-run prepare covers Apple (macOS + iOS)', () {
    final src = File('lib/main.dart').readAsStringSync();
    expect(src.contains('_prepareApplePacketTunnelBeforeConnect'), isTrue);
    expect(src.contains('applePlatformNeedsVpnPrepare'), isTrue);
    expect(src.contains('preparePacketTunnelSequenced'), isTrue);
    // iOS-specific Allow guidance present.
    expect(src.contains('iOS Settings'), isTrue);
    // Must not gate solely on MacWindowController for prepare path.
    final prepareStart = src.indexOf('_prepareApplePacketTunnelBeforeConnect');
    expect(prepareStart, greaterThanOrEqualTo(0));
    final body = src.substring(prepareStart, prepareStart + 900);
    expect(body.contains('applePlatformNeedsVpnPrepare'), isTrue);
    expect(
      body.contains('if (!MacWindowController.isSupported) return;'),
      isFalse,
      reason: 'Apple prepare must not early-return on non-macOS Apple hosts',
    );
  });

  test('prepared false when host NE missing / prepare failed (shipped helpers)',
      () {
    expect(
      isPrepareVpnSuccess({
        'ok': true,
        'prepared': true,
        'hostHasPacketTunnelEntitlement': false,
        'tunnelType': kProductVpnTunnelType,
      }),
      isFalse,
    );
    expect(
      isPrepareVpnSuccess({
        'ok': true,
        'prepared': true,
        'needsTeamResidualSign': true,
        'tunnelType': kProductVpnTunnelType,
      }),
      isFalse,
    );
    expect(
      isPrepareVpnSuccess({
        'ok': false,
        'prepared': false,
        'tunnelType': kProductVpnTunnelType,
      }),
      isFalse,
    );
    expect(
      isPrepareVpnSuccess({
        'ok': true,
        'prepared': true,
        'hostHasPacketTunnelEntitlement': true,
        'tunnelType': kProductVpnTunnelType,
      }),
      isTrue,
    );
    // iOS-style success (no host NE key) still accepted when ok+prepared.
    expect(
      isPrepareVpnSuccess({
        'ok': true,
        'prepared': true,
        'tunnelType': kProductVpnTunnelType,
        'providerBundleId': kProductVpnProviderBundleId,
      }),
      isTrue,
    );
  });

  test(
    'preparePacketTunnelSequenced classification: iOS maps open Settings / ready',
    () {
      // Real decision path used by VpnController.preparePacketTunnelSequenced
      // via macosVpnActionFromPrepareMap — iOS-shaped maps omit host NE key.
      final iosSuccess = {
        'ok': true,
        'prepared': true,
        'tunnelType': kProductVpnTunnelType,
        'providerBundleId': kProductVpnProviderBundleId,
        'message':
            'Restore Privacy Packet Tunnel registered in VPN preferences. '
            'If iOS asks to Allow VPN configuration, choose Allow.',
      };
      expect(isPrepareVpnSuccess(iosSuccess), isTrue);
      expect(prepareMapExplicitlyMissingHostNe(iosSuccess), isFalse);
      expect(
        macosVpnActionFromPrepareMap(
          iosSuccess,
          prepared: isPrepareVpnSuccess(iosSuccess),
        ),
        MacosVpnAfterPrepareAction.readyForConnect,
        reason: 'iOS ok+prepared without host NE key must be readyForConnect',
      );

      // iOS needsAllow (save failed / not allowed) — must open Settings, not hostMissing.
      final iosNeedsAllow = {
        'ok': false,
        'prepared': false,
        'tunnelType': kProductVpnTunnelType,
        'providerBundleId': kProductVpnProviderBundleId,
        'needsVpnSystemSettingsApproval': true,
        'message':
            'Could not pre-register Packet Tunnel VPN configuration: permission denied. '
            'Allow VPN for Restore Privacy in iOS Settings if prompted, then Connect.',
      };
      expect(isPrepareVpnSuccess(iosNeedsAllow), isFalse);
      expect(prepareMapExplicitlyMissingHostNe(iosNeedsAllow), isFalse);
      final needsAllow = iosNeedsAllow['needsVpnSystemSettingsApproval'] == true;
      expect(
        macosVpnActionFromPrepareMap(
          iosNeedsAllow,
          prepared: isPrepareVpnSuccess(iosNeedsAllow),
          needsVpnSystemSettingsApproval: needsAllow,
        ),
        MacosVpnAfterPrepareAction.openSystemSettingsThenConnect,
        reason:
            'iOS needsVpnSystemSettingsApproval must open Settings (not hostMissing)',
      );

      // Explicit host NE false (macOS catalog DevID) still routes to hostMissing.
      final macDevIdMissingNe = {
        'ok': false,
        'prepared': false,
        'hostHasPacketTunnelEntitlement': false,
        'needsTeamResidualSign': true,
        'needsVpnSystemSettingsApproval': true,
        'tunnelType': kProductVpnTunnelType,
        'message': 'missing host packet-tunnel-provider',
      };
      expect(
        macosVpnActionFromPrepareMap(
          macDevIdMissingNe,
          prepared: isPrepareVpnSuccess(macDevIdMissingNe),
          needsVpnSystemSettingsApproval: true,
        ),
        MacosVpnAfterPrepareAction.hostMissingNetworkExtension,
      );

      // vpn_controller must call macosVpnActionFromPrepareMap (not raw hasNe==true).
      final vc = File('lib/vpn_controller.dart').readAsStringSync();
      expect(vc.contains('macosVpnActionFromPrepareMap'), isTrue);
      // Forbidden regression: treat missing key as !hasNe / force needsSign.
      expect(
        RegExp(
          r"hostHasPacketTunnelEntitlement'\]\s*==\s*true",
        ).hasMatch(vc),
        isFalse,
        reason:
            'sequenced prepare must not require explicit true for host NE (kills iOS)',
      );
    },
  );
}
