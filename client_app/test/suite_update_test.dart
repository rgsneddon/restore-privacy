/// Residual push-receive / Suite self-update removed — fail-closed product path.
///
/// Catalog upgrade banner remains (manual update). These tests drive shipped
/// [suiteSelfUpdateEnabled], [receiveAndStoreSuiteUpdate], Settings absence of
/// self-update switch, and [handleProductionUpdatePush] skip.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/settings_screen.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_update.dart';
import 'package:restore_privacy_client/upgrade_banner.dart';
import 'package:restore_privacy_client/vpn_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('self-update permanently off', () {
    test('suiteSelfUpdateEnabled always false even when prefs true', () {
      expect(suiteSelfUpdateDefaultIsOff(), isTrue);
      expect(suiteSelfUpdateEnabled(ProductSettings.defaults), isFalse);
      expect(
        suiteSelfUpdateEnabled(const ProductSettings(checkBreadcrumbs: true)),
        isFalse,
      );
    });

    test('receiveAndStoreSuiteUpdate never stores pending', () async {
      const on = ProductSettings(checkBreadcrumbs: true);
      final mem = <String, String>{};
      final r = await receiveAndStoreSuiteUpdate(
        settings: on,
        payload: {
          'version': '1.0.1',
          'url': 'https://example.test/suite-1.0.1.pkg',
          'message': 'Please upgrade Suite',
          'kind': 'rpt_suite_update',
        },
        memory: mem,
      );
      expect(r['skipped'], isTrue);
      expect(r['store'], isNull);
      expect(r['may_unpack'], isFalse);
      expect(mem.containsKey(kPendingUpdateVersionKey), isFalse);
    });

    test('handleProductionUpdatePush skips', () async {
      final r = await handleProductionUpdatePush(
        settings: const ProductSettings(checkBreadcrumbs: true),
        rawPayload: {
          'version': '1.0.2',
          'url': 'https://example.test/x',
          'message': 'x',
        },
        memory: <String, String>{},
      );
      expect(r['store'], isNull);
      expect(r['skipped'] == true || r['ok'] == true, isTrue);
    });

    test('VpnController pollAndApplyUpdatePush is disabled', () async {
      final vpn = VpnController(onStatus: (_) {});
      final r = await vpn.pollAndApplyUpdatePush(
        settings: const ProductSettings(checkBreadcrumbs: true),
      );
      expect(r['skipped'], isTrue);
      expect(r['store'], isNull);
      expect(r['disabled'], isTrue);
    });
  });

  group('Settings UI no self-update switch', () {
    testWidgets('SettingsScreen has no self-update switch marker', (tester) async {
      final store = SettingsStore(MemorySettingsBackend());
      await tester.pumpWidget(
        MaterialApp(
          home: SettingsScreen(
            store: store,
            initial: ProductSettings.defaults,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byKey(const Key(kSuiteUpdateSettingsSwitchMarker)), findsNothing);
      expect(find.textContaining('Allow Suite self-update'), findsNothing);
    });
  });

  group('upgrade banner (manual update notice)', () {
    test('versionIsBehind and banner text for old monopin', () {
      expect(versionIsBehind('1.1.2', '1.1.3'), isTrue);
      expect(versionIsBehind('1.1.3', '1.1.3'), isFalse);
      final text = upgradeBannerText(running: '1.1.2', latest: '1.1.3');
      expect(text, isNotNull);
      expect(text!.toLowerCase(), contains('new version available'));
      expect(text, contains('1.1.2'));
      expect(text, contains('1.1.3'));
    });
  });
}
