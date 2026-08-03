import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:restore_privacy_client/entry_access.dart';
import 'package:restore_privacy_client/first_run_gate.dart';
import 'package:restore_privacy_client/first_run_portal.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_shell.dart';
import 'package:restore_privacy_client/theme.dart';

LicenceGate _memoryGate({bool licenceAccepted = false}) {
  final seed = <String, Object>{};
  if (licenceAccepted) {
    seed[kKeyLicenceAccepted] = true;
    seed[kKeyLicenceId] = kCurrentLicenceId;
    seed[kKeyLicenceAcceptedAt] = '1';
  }
  return LicenceGate(MemoryLicenceBackend(seed));
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('entry access copy has required phrases and omits paywall', () {
    expect(entryAccessCopyIsValid(kEntryAccessGuidanceText), isTrue);
    expect(kEntryAccessGuidanceText, contains('If you just paid'));
    expect(kEntryAccessGuidanceText, contains('fulfilment email'));
    expect(kEntryAccessGuidanceText, contains('Payment entitlement / keygen'));
    expect(kEntryAccessGuidanceText, contains('unlock dialog'));
    expect(kEntryAccessGuidanceText, contains('Connect again'));
    expect(kEntryAccessGuidanceText, contains('Windows Firewall'));
    expect(kEntryAccessGuidanceText, contains('AllowFirewall.bat'));
    expect(kEntryAccessGuidanceText.toLowerCase().contains('paywall'), isFalse);
    expect(kEntryAccessTitle.toLowerCase().contains('paywall'), isFalse);
    expect(kEntryAccessSubtitle.toLowerCase().contains('paywall'), isFalse);
    expect(kEntryAccessOrange, isNot(equals(kPrimaryDark)));
    expect(kEntryAccessBg.toARGB32(), equals(const Color(0xFF0A1628).toARGB32()));
  });

  test('source files gate entry and omit paywall wording', () {
    expect(kEntryAccessScreenKey, isNotNull);
    expect(kEntryAccessUnlockButtonKey, isNotNull);
    expect(kFirstRunPortalKey, isNotNull);
    expect(entryAccessCopyIsValid(kEntryAccessGuidanceText), isTrue);
    for (final s in [
      kEntryAccessGuidanceText,
      kEntryAccessTitle,
      kEntryAccessSubtitle,
      kEntryAccessUnlockLabel,
      kEntryAccessShopHint,
    ]) {
      expect(s.toLowerCase().contains('paywall'), isFalse, reason: s);
    }
  });

  testWidgets('locked entry shows first-run portal before shell', (tester) async {
    final gate = _memoryGate();
    final b = MemorySettingsBackend();
    final first = FirstRunStore(
      backend: b,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AppEntryRoot(
          licenceGate: gate,
          firstRunStore: first,
          initialUnlocked: false,
          child: const Scaffold(
            key: Key('main_shell_marker'),
            body: Text('MAIN_SHELL'),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump();

    // First-run portal (licence → KEYGEN/trial), not multi-product account.
    expect(find.byKey(kFirstRunPortalKey), findsOneWidget);
    expect(find.text(kFirstRunLicenceStepTitle), findsOneWidget);
    expect(find.text('MAIN_SHELL'), findsNothing);
    expect(find.byKey(const Key('main_shell_marker')), findsNothing);
    expect(find.byKey(kEntryAccessScreenKey), findsNothing);

    final scaffold = tester.widget<Scaffold>(find.byKey(kFirstRunPortalKey));
    expect(scaffold.backgroundColor, kEntryAccessBg);
  });

  testWidgets('unlocked entry shows main shell without first-run portal',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AppEntryRoot(
          initialUnlocked: true,
          child: const Scaffold(
            key: Key('main_shell_marker'),
            body: Text('MAIN_SHELL'),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('MAIN_SHELL'), findsOneWidget);
    expect(find.byKey(kFirstRunPortalKey), findsNothing);
    expect(find.byKey(kEntryAccessScreenKey), findsNothing);
  });

  testWidgets(
      'licence + KEYGEN unlock reveals shell; KEYGEN alone does not',
      (tester) async {
    final gate = _memoryGate();
    final b = MemorySettingsBackend();
    final first = FirstRunStore(
      backend: b,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AppEntryRoot(
          licenceGate: gate,
          firstRunStore: first,
          initialUnlocked: false,
          child: const Scaffold(body: Text('MAIN_SHELL_AFTER_UNLOCK')),
        ),
      ),
    );
    await tester.pump();
    expect(find.byKey(kFirstRunPortalKey), findsOneWidget);
    expect(find.text('MAIN_SHELL_AFTER_UNLOCK'), findsNothing);

    // KEYGEN / payment alone must not open the shell without licence.
    await gate.recordPaymentSuccess(
      'cs_test_entry',
      keygen: 'RPT-KEY-TEST-ENTRY-AAAA',
    );
    final root = tester.state<AppEntryRootState>(find.byType(AppEntryRoot));
    await root.markUnlockedAndRefresh();
    await tester.pump();
    expect(find.byKey(kFirstRunPortalKey), findsOneWidget);
    expect(find.text('MAIN_SHELL_AFTER_UNLOCK'), findsNothing);

    // Licence + entitlement opens shell.
    await gate.acceptLicence();
    await first.markEntryUnlockDone();
    await root.markUnlockedAndRefresh();
    await tester.pump();

    expect(find.text('MAIN_SHELL_AFTER_UNLOCK'), findsOneWidget);
    expect(find.byKey(kFirstRunPortalKey), findsNothing);
  });

  testWidgets('RestorePrivacyApp mounts first-run gate ahead of suite shell',
      (tester) async {
    await tester.pumpWidget(
      const RestorePrivacyApp(
        entryInitiallyUnlocked: false,
        walletTab: SizedBox.shrink(),
        evolveTab: SizedBox.shrink(),
      ),
    );
    await tester.pump();

    expect(find.byKey(kFirstRunPortalKey), findsOneWidget);
    expect(find.byType(SuiteShell), findsNothing);
    expect(find.byKey(kEntryAccessScreenKey), findsNothing);
  });

  testWidgets('RestorePrivacyApp shows suite when entry unlocked', (tester) async {
    await tester.pumpWidget(
      const RestorePrivacyApp(
        entryInitiallyUnlocked: true,
        walletTab: SizedBox(key: Key('wallet_tab_stub')),
        evolveTab: SizedBox(key: Key('evolve_tab_stub')),
      ),
    );
    await tester.pump();

    expect(find.byType(SuiteShell), findsOneWidget);
    expect(find.byKey(kFirstRunPortalKey), findsNothing);
  });

  test('isAppEntryUnlocked requires licence + entitlement not KEYGEN alone',
      () async {
    final gate = _memoryGate(licenceAccepted: false);
    final b = MemorySettingsBackend();
    final incomplete = FirstRunStore(
      backend: b,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );
    expect(
      await isAppEntryUnlocked(
        gate,
        firstRunStore: incomplete,
        backend: b,
      ),
      isFalse,
    );

    await gate.recordPaymentSuccess(
      'cs_ok',
      keygen: 'RPT-KEY-OK-OK-OK-OK',
    );
    // Payment/KEYGEN still does not open shell without licence.
    expect(
      await isAppEntryUnlocked(
        gate,
        firstRunStore: incomplete,
        backend: b,
      ),
      isFalse,
    );

    await gate.acceptLicence();
    expect(
      await isAppEntryUnlocked(
        gate,
        firstRunStore: incomplete,
        backend: b,
      ),
      isTrue,
    );
    expect(await isAppEntryUnlocked(null), isFalse);
  });

  test('return visit blocks when trial/KEYGEN not active', () async {
    final gate = _memoryGate(licenceAccepted: true);
    final b = MemorySettingsBackend();
    final first = FirstRunStore(
      backend: b,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );
    await first.markEntryUnlockDone();
    // No payment, no trial → locked.
    expect(
      await isAppEntryUnlocked(gate, firstRunStore: first, backend: b),
      isFalse,
    );
  });
}
