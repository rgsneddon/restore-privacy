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
}
