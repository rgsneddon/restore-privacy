import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/entry_access.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/prefs_backend.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_update.dart';
import 'package:restore_privacy_client/suite_update_panel.dart';
import 'package:restore_privacy_client/vpn_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('honesty copy', () {
    test('explainer includes required Suite update facts and no paywall', () {
      expect(suiteUpdateCopyIsValid(), isTrue);
      expect(kSuiteUpdateExplainerBody.toLowerCase(), contains('update itself when required'));
      expect(kSuiteUpdateExplainerBody.toLowerCase(), contains('unpack'));
      expect(kSuiteUpdateExplainerBody.toLowerCase(), contains('relaunch'));
      expect(kSuiteUpdateExplainerBody.toLowerCase(), contains('privacy is breached'));
      expect(kSuiteUpdateExplainerBody.toLowerCase(), contains('one time this happens'));
      expect(kSuiteUpdateExplainerBody.toLowerCase(), contains('settings of the vpn'));
      expect(kSuiteUpdateUnpackButtonLabel.toLowerCase(), contains('unpack'));
      expect(kSuiteUpdateUnpackButtonLabel.toLowerCase(), contains('relaunch'));
      final blob =
          '$kSuiteUpdateExplainerBody $kSuiteUpdateSettingsTitle $kEntryAccessGuidanceText'
              .toLowerCase();
      expect(blob.contains('paywall'), isFalse);
    });

    test('default self-update opt-in is off', () {
      expect(suiteSelfUpdateDefaultIsOff(), isTrue);
      expect(ProductSettings.defaults.checkBreadcrumbs, isFalse);
      expect(suiteSelfUpdateEnabled(ProductSettings.defaults), isFalse);
    });
  });

  group('Settings toggle persistence', () {
    test('round-trip checkBreadcrumbs via SettingsStore', () async {
      final shared = <String, dynamic>{};
      final store = SettingsStore(MemorySettingsBackend(shared));
      var s = await store.load();
      expect(s.checkBreadcrumbs, isFalse);

      await store.save(s.copyWith(checkBreadcrumbs: true));
      expect(shared[kKeyCheckBreadcrumbs], isTrue);
      s = await store.load();
      expect(s.checkBreadcrumbs, isTrue);
      expect(suiteSelfUpdateEnabled(s), isTrue);

      await store.save(s.copyWith(checkBreadcrumbs: false));
      s = await SettingsStore(MemorySettingsBackend(shared)).load();
      expect(s.checkBreadcrumbs, isFalse);
      expect(suiteSelfUpdateEnabled(s), isFalse);
    });
  });

  group('push receive + unpack gate', () {
    test('opt-in off refuses store and unpack', () async {
      const off = ProductSettings.defaults;
      final mem = <String, String>{};
      final r = await receiveAndStoreSuiteUpdate(
        settings: off,
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

      final prep = await prepareUnpackAndRelaunch(
        settings: off,
        pending: const PendingSuiteUpdate(
          version: '1.0.1',
          url: 'https://example.test/x',
        ),
      );
      expect(prep['ok'], isFalse);
      expect(prep['may_unpack'], isFalse);
      expect(mayUnpackSuiteUpdate(settings: off, pending: const PendingSuiteUpdate(version: '1.0.1')), isFalse);
    });

    test('opt-in on stores pending and prepare unpack succeeds', () async {
      const on = ProductSettings(checkBreadcrumbs: true);
      final mem = <String, String>{};
      final r = await receiveAndStoreSuiteUpdate(
        settings: on,
        payload: {
          'version': '1.0.1',
          'url': 'https://example.test/suite-1.0.1.pkg',
          'message': 'Suite package ready',
          'kind': 'rpt_suite_update',
        },
        memory: mem,
      );
      expect(r['ok'], isTrue);
      expect(r['skipped'], isFalse);
      expect(r['may_unpack'], isTrue);
      expect(mem[kPendingUpdateVersionKey], '1.0.1');
      expect(mem[kPendingUpdateUrlKey], contains('suite-1.0.1'));

      final pending = await loadPendingSuiteUpdate(memory: mem);
      expect(pending, isNotNull);
      expect(mayUnpackSuiteUpdate(settings: on, pending: pending), isTrue);

      final prep = await prepareUnpackAndRelaunch(
        settings: on,
        pending: pending,
        download: (url) async => utf8.encode('FIXTURE-SUITE-PKG'),
        stageDir: Directory.systemTemp.createTempSync('suite_upd_test_'),
      );
      expect(prep['ok'], isTrue);
      expect(prep['may_unpack'], isTrue);
      final handoff = prep['handoff'] as Map;
      expect(handoff['requires_user_click'], isTrue);
      expect(handoff['version'], '1.0.1');
      expect((handoff['package_path'] as String).isNotEmpty, isTrue);

      var relaunched = false;
      final exec = await executeUnpackAndRelaunchHandoff(
        settings: on,
        handoff: Map<String, dynamic>.from(handoff),
        openUri: (uri) async => true,
        relaunch: () => relaunched = true,
      );
      expect(exec['ok'], isTrue);
      expect(relaunched, isTrue);

      // Silent unpack refused
      final silent = await executeUnpackAndRelaunchHandoff(
        settings: on,
        handoff: {
          'requires_user_click': false,
          'version': '1.0.1',
          'url': 'https://example.test/x',
        },
        openUri: (uri) async => true,
      );
      expect(silent['ok'], isFalse);
    });

    test('parse Suite UPDATE_PUSH JSON shape', () {
      final raw = jsonEncode({
        'version': '1.0.1',
        'url': 'https://restoreprivacy.online/suite/download?platform=macos',
        'message': 'Push update to clients',
        'kind': 'rpt_client_update',
      });
      final blob = parseSuiteUpdatePushJson(raw);
      const on = ProductSettings(checkBreadcrumbs: true);
      final r = receiveSuiteUpdateDirective(settings: on, payload: blob);
      expect(r['ok'], isTrue);
      expect((r['store'] as Map)['pending_update_version'], '1.0.1');
    });

    test('production handleProductionUpdatePush stores pending when opt-in on',
        () async {
      const on = ProductSettings(checkBreadcrumbs: true);
      final mem = <String, String>{};
      final r = await handleProductionUpdatePush(
        settings: on,
        rawPayload: {
          'version': '1.0.2',
          'url': 'https://example.test/suite-1.0.2.pkg',
          'message': 'Push update to clients',
          'kind': 'rpt_suite_update',
        },
        memory: mem,
      );
      expect(r['ok'], isTrue);
      expect(mem[kPendingUpdateVersionKey], '1.0.2');
      expect(mayUnpackSuiteUpdate(
        settings: on,
        pending: await loadPendingSuiteUpdate(memory: mem),
      ), isTrue);
    });

    test('VpnController MethodChannel updatePush → production receive', () async {
      SharedPreferences.setMockInitialValues({});
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
        const MethodChannel('restore_privacy/vpn'),
        (call) async {
          // Dart→native polls not used in this test; host→Flutter is handler side.
          return null;
        },
      );
      final mem = <String, String>{};
      // Drive shipped handleProductionUpdatePush as installUpdatePushHandler does.
      const on = ProductSettings(checkBreadcrumbs: true);
      final vpn = VpnController(onStatus: (_) {});
      vpn.settingsForUpdatePush = on;
      dynamic captured;
      vpn.onUpdatePush = (raw) => captured = raw;
      vpn.installUpdatePushHandler();

      // Simulate host invoke of updatePush (same channel MethodCall path).
      final messenger =
          TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
      final codec = const StandardMethodCodec();
      final call = const MethodCall(kUpdatePushHostMethod, {
        'version': '1.0.3',
        'url': 'https://example.test/s-1.0.3.pkg',
        'message': 'operator push',
      });
      final data = codec.encodeMethodCall(call);
      // Channel handler is on Flutter side; use handlePlatformMessage.
      final completer = Completer<ByteData?>();
      messenger.handlePlatformMessage(
        'restore_privacy/vpn',
        data,
        (ByteData? reply) {
          completer.complete(reply);
        },
      );
      final reply = await completer.future;
      expect(reply, isNotNull);
      // Handler returns handleProductionUpdatePush result via encodeSuccessEnvelope
      final decoded = codec.decodeEnvelope(reply!);
      expect(decoded, isA<Map>());
      final map = Map<String, dynamic>.from(decoded as Map);
      // Persist via production path with memory for assertion
      final stored = await handleProductionUpdatePush(
        settings: on,
        rawPayload: {
          'version': '1.0.3',
          'url': 'https://example.test/s-1.0.3.pkg',
        },
        memory: mem,
      );
      expect(stored['ok'], isTrue);
      expect(mem[kPendingUpdateVersionKey], '1.0.3');
      expect(map['ok'], isTrue);
      expect(captured, isNotNull);

      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
        const MethodChannel('restore_privacy/vpn'),
        null,
      );
    });
  });

  group('entry then entitled shell', () {
    testWidgets('locked entry hides Suite update explainer', (tester) async {
      SharedPreferences.setMockInitialValues({});
      final gate = LicenceGate(MemoryLicenceBackend({}));
      await tester.pumpWidget(
        RestorePrivacyApp(
          licenceGate: gate,
          entryInitiallyUnlocked: false,
          settingsStore: SettingsStore(MemorySettingsBackend({})),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byKey(kEntryAccessScreenKey), findsOneWidget);
      expect(find.byKey(const Key(kSuiteUpdateExplainerMarker)), findsNothing);
      expect(find.textContaining('paywall'), findsNothing);
    });

    testWidgets('entitled shell shows update explainer after KEYGEN unlock',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final gate = LicenceGate(MemoryLicenceBackend({}));
      await tester.pumpWidget(
        RestorePrivacyApp(
          licenceGate: gate,
          entryInitiallyUnlocked: true,
          settingsStore: SettingsStore(MemorySettingsBackend({})),
        ),
      );
      // Avoid pumpAndSettle: Suite shell / VPN may have ongoing timers.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.byKey(kEntryAccessScreenKey), findsNothing);
      expect(find.byKey(const Key(kSuiteUpdateExplainerMarker)), findsOneWidget);
      expect(find.text(kSuiteUpdateExplainerHeading), findsOneWidget);
      expect(find.textContaining('privacy is breached'), findsOneWidget);
      expect(find.textContaining('Settings of the VPN'), findsOneWidget);
      expect(find.byKey(const Key(kSuiteUpdateUnpackButtonMarker)), findsOneWidget);
      final btn = tester.widget<FilledButton>(
        find.byKey(const Key(kSuiteUpdateUnpackButtonMarker)),
      );
      expect(btn.onPressed, isNull);
    });

    testWidgets('honesty panel enables unpack when opt-in + pending', (tester) async {
      final mem = <String, String>{
        kPendingUpdateVersionKey: '1.0.1',
        kPendingUpdateUrlKey: 'https://example.test/s.pkg',
        kPendingUpdateMessageKey: 'ready',
      };
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SuiteUpdateHonestyPanel(
              settings: const ProductSettings(checkBreadcrumbs: true),
              memoryPending: mem,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byKey(const Key(kSuiteUpdateExplainerMarker)), findsOneWidget);
      final btn = tester.widget<FilledButton>(
        find.byKey(const Key(kSuiteUpdateUnpackButtonMarker)),
      );
      expect(btn.onPressed, isNotNull);
    });
  });
}
