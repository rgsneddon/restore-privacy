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

  test('build_suite_1.1.6 invokes residual team resign every macOS ship', () {
    final root = Directory.current.path;
    // flutter test cwd is client_app/
    final script = File('../scripts/build_suite_1.1.6.py');
    expect(script.existsSync(), isTrue, reason: 'from $root');
    final src = script.readAsStringSync();
    expect(src.contains('run_residual_team_resign'), isTrue);
    expect(src.contains('apple_ship_gates'), isTrue);
  });
}
