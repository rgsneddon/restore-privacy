/// First-run licence: full scrollable justified text, scroll-to-bottom accept.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/first_run_gate.dart';
import 'package:restore_privacy_client/first_run_portal.dart';
import 'package:restore_privacy_client/full_end_user_licence.dart';
import 'package:restore_privacy_client/legal_links.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/settings_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MemorySettingsBackend prefs;
  late LicenceGate gate;
  late FirstRunStore firstRun;

  setUp(() {
    prefs = MemorySettingsBackend();
    gate = LicenceGate(MemoryLicenceBackend({}));
    firstRun = FirstRunStore(
      backend: prefs,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );
  });

  testWidgets(
    'licence accept disabled until scroll-to-bottom; link targets public licence',
    (tester) async {
      Uri? opened;
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            // Short height forces scroll on licence body.
            data: const MediaQueryData(size: Size(390, 640)),
            child: FirstRunPortal(
              onComplete: () {},
              licenceGate: gate,
              firstRunStore: firstRun,
              openLicenceUrl: (uri) async {
                opened = uri;
                return true;
              },
              initialState: const FirstRunState(
                licenceAccepted: false,
                entryUnlockDone: false,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text(kFirstRunLicenceStepTitle), findsOneWidget);
      expect(find.byKey(kFirstRunLicenceScrollKey), findsOneWidget);
      // Full product LICENSE (not short summary only) + residual disclaimer.
      expect(
        find.textContaining('PROPRIETARY FULL COPYRIGHT LICENCE'),
        findsOneWidget,
      );
      expect(find.textContaining('1. DEFINITIONS'), findsOneWidget);
      expect(find.textContaining('Client Package'), findsWidgets);
      expect(find.textContaining('residual VPN'), findsWidgets);
      expect(find.textContaining('END OF LICENCE'), findsOneWidget);
      expect(find.textContaining('STRONG DISCLAIMER'), findsOneWidget);

      // Justified body text.
      final licenceText = tester.widget<Text>(
        find.descendant(
          of: find.byKey(kFirstRunLicenceScrollKey),
          matching: find.byType(Text),
        ).first,
      );
      expect(licenceText.textAlign, TextAlign.justify);

      // Bounded pane: Expanded licence region must leave room for chrome.
      final scrollBox = tester.renderObject<RenderBox>(
        find.byKey(kFirstRunLicenceScrollKey),
      );
      expect(scrollBox.size.height, lessThan(640));
      expect(scrollBox.size.height, greaterThan(80));

      final acceptBefore = tester.widget<FilledButton>(
        find.byKey(kFirstRunLicenceAcceptKey),
      );
      expect(acceptBefore.onPressed, isNull);

      // Public licence link.
      expect(find.byKey(kFirstRunLicenceLinkKey), findsOneWidget);
      expect(find.text(kEndUserLicenceLabel), findsOneWidget);
      await tester.tap(find.byKey(kFirstRunLicenceLinkKey));
      await tester.pump();
      expect(opened, isNotNull);
      expect(opened.toString(), contains('/LICENSE'));
      expect(opened.toString(), contains('restoreprivacy.online'));

      // Scroll the licence pane to the bottom (real ScrollController path).
      final scrollable = find.descendant(
        of: find.byKey(kFirstRunLicenceScrollKey),
        matching: find.byType(Scrollable),
      );
      final pos = tester.state<ScrollableState>(scrollable).position;
      expect(
        pos.maxScrollExtent,
        greaterThan(500),
        reason: 'full LICENSE body must require substantial scroll',
      );
      pos.jumpTo(pos.maxScrollExtent);
      await tester.pumpAndSettle();
      expect(pos.pixels, greaterThanOrEqualTo(pos.maxScrollExtent - 12));

      final acceptAfter = tester.widget<FilledButton>(
        find.byKey(kFirstRunLicenceAcceptKey),
      );
      expect(
        acceptAfter.onPressed,
        isNotNull,
        reason: 'accept must enable after scroll-to-bottom',
      );

      await tester.ensureVisible(find.byKey(kFirstRunLicenceAcceptKey));
      await tester.tap(find.byKey(kFirstRunLicenceAcceptKey));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(await gate.hasAcceptedLicence(), isTrue);

      // After accept, KEYGEN/trial step (not account/seed).
      await tester.pumpAndSettle();
      expect(find.text(kFirstRunKeygenStepTitle), findsOneWidget);
      expect(find.byKey(kFirstRunContinueTrialKey), findsOneWidget);
      expect(find.byKey(kFirstRunKeygenContinueKey), findsOneWidget);
    },
  );

  test('public licence URI is status-host LICENSE path', () {
    expect(kFirstRunPublicLicenceUri.host, 'restoreprivacy.online');
    expect(kFirstRunPublicLicenceUri.path, '/LICENSE');
  });

  test('full EULA is residual-VPN scoped (no multi-product Suite grant)', () {
    final body = kFullEndUserLicenceText;
    expect(body, contains('residual VPN'));
    expect(body, contains('CLIENT PACKAGES / VPN USE ONLY'));
    // Forbidden multi-product product-grant framing.
    expect(body.contains('USE OF RESTORE PRIVACY SUITE'), isFalse);
    expect(body.contains('Suite installers'), isFalse);
    expect(body.contains('Restore Privacy Suite residual Connect'), isFalse);
    // May mention Suite only to deny multi-product rights.
    expect(body, contains('residual VPN use only'));
  });
}
