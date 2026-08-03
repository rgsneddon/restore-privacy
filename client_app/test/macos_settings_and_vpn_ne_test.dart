/// macOS Settings open + Packet Tunnel prepare path structural gates.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/settings_store.dart';

void main() {
  test('resolveSettingsStoreForOpen never returns null / silent empty', () {
    final mem = SettingsStore(MemorySettingsBackend());
    expect(resolveSettingsStoreForOpen(existing: mem), same(mem));

    final created = resolveSettingsStoreForOpen(
      existing: null,
      createPrimary: () => SettingsStore(MemorySettingsBackend()),
    );
    expect(created, isA<SettingsStore>());

    final fallback = resolveSettingsStoreForOpen(
      existing: null,
      createPrimary: () => throw StateError('prefs down'),
      createFallback: () => SettingsStore(MemorySettingsBackend()),
    );
    expect(fallback, isA<SettingsStore>());

    final lastResort = resolveSettingsStoreForOpen(
      existing: null,
      createPrimary: () => throw StateError('x'),
      createFallback: () => throw StateError('y'),
    );
    expect(lastResort, isA<SettingsStore>());
  });

  test('main.dart Settings control uses rootNavigator and no silent null store',
      () {
    final src = File('lib/main.dart').readAsStringSync();
    expect(src.contains("key: const Key('main_settings_button')"), isTrue);
    expect(src.contains('_openSettings'), isTrue);
    expect(src.contains('rootNavigator: true'), isTrue);
    expect(src.contains('resolveSettingsStoreForOpen'), isTrue);
    expect(src.contains('Settings could not open'), isTrue);
    expect(src.contains('product_settings_screen'), isTrue);
    // Extract _openSettings body and forbid silent null-store return.
    final start = src.indexOf('Future<void> _openSettings()');
    expect(start, greaterThanOrEqualTo(0));
    final end = src.indexOf('Future<void>', start + 10);
    final body = src.substring(start, end > start ? end : src.length);
    expect(
      body.contains('if (store == null) return;'),
      isFalse,
      reason: '_openSettings must not silent-return on null store',
    );
  });

  test('RptVpnChannel prepare always attempts loadOrCreateManager', () {
    final src =
        File('macos/NativePrep/RptVpnChannel.swift').readAsStringSync();
    // No early return before loadOrCreateManager on missing host NE alone.
    final prepareIdx = src.indexOf('private static func preparePacketTunnelConfiguration');
    expect(prepareIdx, greaterThanOrEqualTo(0));
    final endIdx = src.indexOf('private static func vpnSystemSettingsURLCandidates', prepareIdx);
    final body = src.substring(prepareIdx, endIdx > prepareIdx ? endIdx : src.length);
    expect(body.contains('loadOrCreateManager'), isTrue);
    // Forbidden short-circuit pattern: if !hostHas... { completion; return } before load
    expect(
      RegExp(
        r'if !hostHasPacketTunnelNetworkExtensionEntitlement\(\)\s*\{[^}]*completion\(map\)\s*return',
        multiLine: true,
      ).hasMatch(body),
      isFalse,
      reason: 'prepare must not short-circuit before loadOrCreateManager',
    );
    expect(body.contains('isEnabled = true'), isTrue);
    expect(body.contains('saveToPreferences'), isTrue);
  });

  test('loadOrCreateManager always calls loadAllFromPreferences (no host-NE gate)',
      () {
    final src =
        File('macos/NativePrep/RptVpnChannel.swift').readAsStringSync();
    final start = src.indexOf('private static func loadOrCreateManager');
    expect(start, greaterThanOrEqualTo(0));
    final end = src.indexOf('private static func startTunnel', start);
    final body = src.substring(start, end > start ? end : src.length);
    // Real path: must load preferences then save enabled product profile.
    expect(body.contains('NETunnelProviderManager.loadAllFromPreferences'), isTrue);
    expect(body.contains('saveToPreferences'), isTrue);
    expect(body.contains('isEnabled = true'), isTrue);
    // Forbidden: early-return solely on missing host NE before loadAll.
    expect(
      RegExp(
        r'if !hostHasPacketTunnelNetworkExtensionEntitlement\(\)\s*\{\s*'
        r'completion\(nil,\s*hostMissingNeEntitlementMessage\(\)\)\s*return',
        multiLine: true,
      ).hasMatch(body),
      isFalse,
      reason: 'loadOrCreateManager must not gate NE save on host entitlement probe',
    );
    // Host NE probe may annotate errors only — not skip the API.
    expect(body.contains('hostHasPacketTunnelNetworkExtensionEntitlement'), isTrue);
  });

  test('sign_and_notarize defaults openable DevID (no host NE) + launch probe',
      () {
    final script = File('../scripts/sign_and_notarize_macos.py');
    expect(script.existsSync(), isTrue);
    final src = script.readAsStringSync();
    // Default RPT_MACOS_HOST_NE is off — DevID side path must launch (not AMFI 137).
    expect(src.contains('RPT_MACOS_HOST_NE", "0"'), isTrue);
    expect(src.contains('DeveloperID.entitlements'), isTrue);
    expect(src.contains('launch_probe_alive'), isTrue);
    expect(src.contains('return 4'), isTrue); // fail closed on dead launch
    // Residual host NE on DevID remains opt-in only (AMFI without DevID NE profile).
    expect(src.contains('DeveloperIDResidual.entitlements'), isTrue);
  });

  test('build_suite_1.1.6 packages residual-team as monopin (host NE + launch)',
      () {
    final root = Directory.current.path;
    // flutter test cwd is client_app/
    final script = File('../scripts/build_suite_1.1.6.py');
    expect(script.existsSync(), isTrue, reason: 'from $root');
    final src = script.readAsStringSync();
    expect(src.contains('run_residual_team_resign'), isTrue);
    expect(src.contains('apple_ship_gates'), isTrue);
    // Catalog monopin is residual-capable, not unopenable DevID+host-NE.
    expect(src.contains('require_macos_zip_residual_capable'), isTrue);
    expect(src.contains('require=True'), isTrue);
    expect(src.contains('host_app_has_packet_tunnel_provider'), isTrue);
    expect(src.contains('launch_probe_app_alive'), isTrue);
    // Must not require Notarized DevID for residual monopin seal.
    expect(
      src.contains('require_macos_zip_developer_id_distribution(dest)'),
      isFalse,
      reason: 'residual monopin uses residual seal, not DevID-only audit',
    );
  });
}
