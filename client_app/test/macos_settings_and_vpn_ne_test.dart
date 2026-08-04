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
    // Settings must stay openable during Connect (not gated by _busy).
    expect(
      src.contains("onPressed: () => unawaited(_openSettings())"),
      isTrue,
      reason: 'Settings button must not disable while _busy',
    );
    expect(
      src.contains(
        "onPressed: _busy ? null : () => unawaited(_openSettings())",
      ),
      isFalse,
    );
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
    // End at next private static after prepare (name may vary).
    final after = src.substring(prepareIdx + 10);
    final nextFn = RegExp(r'\n  private static func \w+').firstMatch(after);
    final endIdx = nextFn != null
        ? prepareIdx + 10 + nextFn.start
        : src.indexOf('private static func vpnSystemSettingsURLCandidates', prepareIdx);
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
    // Save errors must not be ignored; success stamp only after save OK + host NE.
    expect(body.contains('if let saveErr'), isTrue);
    expect(body.contains('lastSuccessfulPrepareAt = Date()'), isTrue);
    expect(body.contains('lastSuccessfulPrepareAt = nil'), isTrue);
    // Debounce only when host NE present (not catalog DevID false prepared).
    expect(body.contains('if hostHasNe,'), isTrue);
    // prepared:true requires host NE
    expect(
      body.contains('if !hostHasNe'),
      isTrue,
      reason: 'must refuse prepared without host packet-tunnel-provider',
    );
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

  test('sign_and_notarize free monopin residual NE when DevID profiles present',
      () {
    final script = File('../scripts/sign_and_notarize_macos.py');
    expect(script.existsSync(), isTrue);
    final src = script.readAsStringSync();
    // Free monopin uses DevID residual NE when MAC_APP_DIRECT profiles exist.
    expect(src.contains('devid_ne_profiles_available'), isTrue);
    expect(src.contains('embed_devid_ne_profiles'), isTrue);
    expect(src.contains('DeveloperIDResidual.entitlements'), isTrue);
    expect(src.contains('PacketTunnelDeveloperID.entitlements'), isTrue);
    expect(src.contains('launch_probe_alive'), isTrue);
    expect(src.contains('return 4'), isTrue); // fail closed on dead launch
    // Fallback without profiles still uses DeveloperID.entitlements (no host NE).
    expect(src.contains('DeveloperID.entitlements'), isTrue);
    // Must keep MAC_APP_DIRECT profiles (not strip-all).
    expect(src.contains('keeping distribution profile'), isTrue);
  });

  test('build_suite_1.1.10 monopin is Notarized DevID residual-capable free path',
      () {
    final root = Directory.current.path;
    // flutter test cwd is client_app/
    final script = File('../scripts/build_suite_1.1.10.py');
    expect(script.existsSync(), isTrue, reason: 'from $root');
    final src = script.readAsStringSync();
    // Residual re-sign is side path only (best-effort).
    expect(src.contains('run_residual_team_resign'), isTrue);
    expect(src.contains('apple_ship_gates'), isTrue);
    expect(src.contains('require=False'), isTrue);
    // Catalog monopin must be Gatekeeper-openable DevID + notary.
    expect(src.contains('sign_and_notarize_macos.py'), isTrue);
    expect(src.contains('require_macos_zip_developer_id_distribution'), isTrue);
    expect(src.contains('RPT_MACOS_HOST_NE'), isTrue);
    // Free monopin prefers residual host NE for first-use VPN registration.
    expect(src.contains('RPT_MACOS_HOST_NE"] = "1"') || src.contains("RPT_MACOS_HOST_NE'] = '1'"), isTrue);
    // Must not seal residual-team as monopin basename.
    expect(
      src.contains('require_macos_zip_residual_capable(dest)'),
      isFalse,
      reason: 'monopin uses DevID distribution seal, not residual-only audit',
    );
    expect(src.contains('Apple could not verify') || src.contains('Gatekeeper'), isTrue);
  });

  test('DevID residual entitlements use systemextension NE tokens', () {
    final host = File('macos/Runner/DeveloperIDResidual.entitlements').readAsStringSync();
    final tun =
        File('macos/PacketTunnel/PacketTunnelDeveloperID.entitlements').readAsStringSync();
    expect(host.contains('packet-tunnel-provider-systemextension'), isTrue);
    expect(tun.contains('packet-tunnel-provider-systemextension'), isTrue);
    // Bare packet-tunnel-provider alone under DevID is AMFI without profile match.
    expect(
      host.contains('<string>packet-tunnel-provider</string>'),
      isFalse,
      reason: 'DevID residual must use systemextension NE entitlement string',
    );
    final profDir = Directory('macos/Provisioning/DeveloperID');
    expect(profDir.existsSync(), isTrue);
    expect(File('${profDir.path}/host.provisionprofile').existsSync(), isTrue);
    expect(
      File('${profDir.path}/PacketTunnel.provisionprofile').existsSync(),
      isTrue,
    );
  });

  test(
    'hostHasPacketTunnel accepts free monopin systemextension NE token (not exact-only)',
    () {
      final src =
          File('macos/NativePrep/RptVpnChannel.swift').readAsStringSync();
      // Pure classifier used by hostHasPacketTunnelNetworkExtensionEntitlement.
      expect(
        src.contains('networkExtensionListIncludesPacketTunnel'),
        isTrue,
        reason: 'shipped pure NE list classifier required for free monopin',
      );
      expect(
        src.contains('packet-tunnel-provider-systemextension'),
        isTrue,
        reason: 'must explicitly accept DevID free monopin host NE token',
      );
      // hostHas… must call the classifier (not exact Array.contains alone).
      final hostFn = src.indexOf(
        'static func hostHasPacketTunnelNetworkExtensionEntitlement',
      );
      expect(hostFn, greaterThanOrEqualTo(0));
      final hostBody = src.substring(
        hostFn,
        src.indexOf('static func hostMissingNeEntitlementMessage', hostFn),
      );
      expect(
        hostBody.contains('networkExtensionListIncludesPacketTunnel(ne)'),
        isTrue,
        reason: 'host probe must use classifier (systemextension free path)',
      );
      // Forbidden regression: exact-only contains on bare token as sole return.
      expect(
        RegExp(
          r'return ne\.contains\("packet-tunnel-provider"\)\s*$',
          multiLine: true,
        ).hasMatch(hostBody),
        isFalse,
        reason:
            'Array.contains exact match rejects packet-tunnel-provider-systemextension',
      );

      // Pure classifier body must treat systemextension as success.
      final cls = src.indexOf('static func networkExtensionListIncludesPacketTunnel');
      expect(cls, greaterThanOrEqualTo(0));
      final clsEnd = src.indexOf(
        'static func hostHasPacketTunnelNetworkExtensionEntitlement',
        cls,
      );
      final clsBody = src.substring(cls, clsEnd > cls ? clsEnd : src.length);
      expect(
        clsBody.contains('packet-tunnel-provider-systemextension'),
        isTrue,
      );
      expect(clsBody.contains('token == "packet-tunnel-provider"'), isTrue);
      // prepare stamps prepared after save only when hostHasNe — free monopin
      // must not force needsTeamResidualSign via false probe.
      final prep = src.indexOf('private static func preparePacketTunnelConfiguration');
      final prepEnd = src.indexOf('private static func devicePubHexMap', prep);
      final prepBody = src.substring(
        prep,
        prepEnd > prep ? prepEnd : src.length,
      );
      expect(prepBody.contains('hostHasPacketTunnelNetworkExtensionEntitlement()'), isTrue);
      expect(prepBody.contains('"prepared": true'), isTrue);
      expect(prepBody.contains('if !hostHasNe'), isTrue);
    },
  );
}
