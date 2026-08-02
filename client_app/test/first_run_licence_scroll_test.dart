/// First-run licence: full scrollable text, scroll-to-bottom accept, public link.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/first_run_gate.dart';
import 'package:restore_privacy_client/first_run_portal.dart';
import 'package:restore_privacy_client/legal_links.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_account.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MemorySettingsBackend prefs;
  late LicenceGate gate;
  late SuiteAccountStore accounts;
  late FirstRunStore firstRun;

  setUp(() {
    prefs = MemorySettingsBackend();
    gate = LicenceGate(MemoryLicenceBackend({}));
    accounts = SuiteAccountStore(prefs);
    firstRun = FirstRunStore(
      backend: prefs,
      isAccountRegistered: accounts.isRegistered,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );
  });

  testWidgets(
    'licence accept disabled until scroll-to-bottom; link targets public licence',
    (tester) async {
      await accounts.markRegistered('lic_user');
      await firstRun.markSeedDone();
      Uri? opened;
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            // Short height forces scroll on licence body.
            data: const MediaQueryData(size: Size(390, 640)),
            child: FirstRunPortal(
              onComplete: () {},
              licenceGate: gate,
              accountStore: accounts,
              firstRunStore: firstRun,
              openLicenceUrl: (uri) async {
                opened = uri;
                return true;
              },
              initialState: const FirstRunState(
                accountDone: true,
                seedDone: true,
                licenceAccepted: false,
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
      expect(find.textContaining('END OF LICENCE'), findsOneWidget);
      expect(find.textContaining('STRONG DISCLAIMER'), findsOneWidget);

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
      // Jump to end — full LICENSE is multi-page (~10k+ px).
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
    },
  );

  test('public licence URI is status-host LICENSE path', () {
    expect(kFirstRunPublicLicenceUri.host, 'restoreprivacy.online');
    expect(kFirstRunPublicLicenceUri.path, '/LICENSE');
  });
}
