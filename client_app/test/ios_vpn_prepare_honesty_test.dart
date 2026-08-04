/// iOS Packet Tunnel prepare/Connect honesty — structural gates on shipped Swift.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/connect_status.dart';

void main() {
  late String iosSrc;

  setUpAll(() {
    final f = File('ios/NativePrep/RptVpnChannel.swift');
    expect(f.existsSync(), isTrue, reason: 'iOS RptVpnChannel must ship');
    iosSrc = f.readAsStringSync();
  });

  test('iOS preparePacketTunnelConfiguration always loadOrCreate + save', () {
    expect(
      iosSrc.contains('private static func preparePacketTunnelConfiguration'),
      isTrue,
      reason: 'dedicated prepare path (parity with macOS honesty)',
    );
    final start = iosSrc.indexOf('private static func preparePacketTunnelConfiguration');
    final end = iosSrc.indexOf('private static func devicePubHexMap', start);
    final body = iosSrc.substring(start, end > start ? end : iosSrc.length);
    expect(body.contains('loadOrCreateManager'), isTrue);
    expect(body.contains('isEnabled = true'), isTrue);
    expect(body.contains('saveToPreferences'), isTrue);
    expect(body.contains('if let saveErr'), isTrue);
    // prepared success only after save OK
    expect(body.contains('"prepared": true'), isTrue);
    expect(body.contains('"prepared": false'), isTrue);
    // Save failure must not claim prepared:true
    final saveFail = body.indexOf('if let saveErr');
    expect(saveFail, greaterThanOrEqualTo(0));
    final afterSaveFail = body.substring(saveFail, saveFail + 600);
    expect(afterSaveFail.contains('"prepared": false'), isTrue);
    expect(afterSaveFail.contains('"ok": false'), isTrue);
    // Product Packet Tunnel identity, not L2TP/IKEv2
    expect(body.contains('productTunnelType') || body.contains('packet-tunnel'), isTrue);
    expect(body.toLowerCase(), isNot(contains('nwl2tp')));
    expect(body.toLowerCase(), isNot(contains('nevpnprotocolikev2')));
  });

  test('iOS channel registers prepareVpn / preparePacketTunnel handlers', () {
    expect(iosSrc.contains('"prepareVpn"'), isTrue);
    expect(iosSrc.contains('"preparePacketTunnel"'), isTrue);
    expect(iosSrc.contains('preparePacketTunnelConfiguration'), isTrue);
    // openSettingsOnDenial default false (Flutter sequences Settings)
    expect(iosSrc.contains('openSettingsOnDenial'), isTrue);
    expect(iosSrc.contains('openSettingsOnDenial: Bool = false'), isTrue);
    // Emit hostHasPacketTunnelEntitlement:true (never false) so Flutter does not
    // classify iOS prepare as macOS catalog DevID missing-NE.
    expect(iosSrc.contains('"hostHasPacketTunnelEntitlement": true'), isTrue);
    expect(iosSrc.contains('"hostHasPacketTunnelEntitlement": false'), isFalse);
    expect(iosSrc.contains('"needsTeamResidualSign": false'), isTrue);
  });

  test('iOS loadOrCreateManager loads preferences and saves enabled', () {
    final start = iosSrc.indexOf('private static func loadOrCreateManager');
    expect(start, greaterThanOrEqualTo(0));
    final end = iosSrc.indexOf('private static func startTunnel', start);
    final body = iosSrc.substring(start, end > start ? end : iosSrc.length);
    expect(body.contains('NETunnelProviderManager.loadAllFromPreferences'), isTrue);
    expect(body.contains('saveToPreferences'), isTrue);
    expect(body.contains('isEnabled = true'), isTrue);
    expect(body.contains('applyProductPacketTunnelProtocol'), isTrue);
  });

  test('iOS Connect re-registers profile before startTunnel', () {
    final start = iosSrc.indexOf('private static func enableProductVpnAndStartTunnel');
    expect(start, greaterThanOrEqualTo(0));
    final end = iosSrc.indexOf('private static func reloadProductManager', start);
    final body = iosSrc.substring(start, end > start ? end : iosSrc.length);
    expect(body.contains('loadOrCreateManager'), isTrue);
    expect(body.contains('needsVpnSystemSettingsApproval'), isTrue);
    // ensureEnabled always saves before start (macOS parity).
    final eStart = iosSrc.indexOf('private static func ensureEnabledThenStartTunnel');
    final eEnd = iosSrc.indexOf('private static func hostSideDiagnostic', eStart);
    final eBody = iosSrc.substring(eStart, eEnd > eStart ? eEnd : iosSrc.length);
    expect(eBody.contains('isEnabled = true'), isTrue);
    expect(eBody.contains('saveToPreferences'), isTrue);
    // Forbidden: early start() solely because already enabled *before* saveToPreferences.
    final saveIdx = eBody.indexOf('saveToPreferences');
    expect(saveIdx, greaterThanOrEqualTo(0));
    final beforeSave = eBody.substring(0, saveIdx);
    expect(
      RegExp(
        r'if manager\.isEnabled[^{]*\{\s*start\(\)\s*return',
        multiLine: true,
      ).hasMatch(beforeSave),
      isFalse,
      reason: 'must not startTunnel before re-save when already enabled',
    );
    // After saveErr, start() fallback when already enabled is OK.
    expect(eBody.contains('if let saveErr'), isTrue);
  });

  test('iOS prepare failure maps reject isPrepareVpnSuccess (shipped helper)', () {
    final failed = {
      'ok': false,
      'prepared': false,
      'tunnelType': kProductVpnTunnelType,
      'providerBundleId': kProductVpnProviderBundleId,
      'needsVpnSystemSettingsApproval': true,
      'message':
          'Could not pre-register Packet Tunnel VPN configuration: permission denied. '
          'Allow VPN for Restore Privacy in iOS Settings if prompted, then Connect.',
    };
    expect(isProductPacketTunnelPrepareResult(failed), isTrue);
    expect(isPrepareVpnSuccess(failed), isFalse);
    final msg = mapPrepareVpnStatusMessage(failed);
    expect(msg.toLowerCase(), contains('packet tunnel'));
    expect(productCopyDirectsToLegacyVpnTypes(msg), isFalse);
  });

  test('iOS prepared success map is honest only with ok+prepared', () {
    final prepared = {
      'ok': true,
      'prepared': true,
      'tunnelType': kProductVpnTunnelType,
      'providerBundleId': kProductVpnProviderBundleId,
      'message':
          'Restore Privacy Packet Tunnel registered in VPN preferences. '
          'If iOS asks to Allow VPN configuration, choose Allow.',
    };
    expect(isPrepareVpnSuccess(prepared), isTrue);
    // Partial maps must not count as prepared.
    expect(
      isPrepareVpnSuccess({
        'ok': true,
        'prepared': false,
        'tunnelType': kProductVpnTunnelType,
      }),
      isFalse,
    );
    expect(
      isPrepareVpnSuccess({
        'ok': false,
        'prepared': true,
        'tunnelType': kProductVpnTunnelType,
      }),
      isFalse,
    );
  });
}
