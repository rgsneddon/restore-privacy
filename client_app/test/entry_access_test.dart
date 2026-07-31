import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:restore_privacy_client/entry_access.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/suite_shell.dart';
import 'package:restore_privacy_client/suite_version.dart';
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

  testWidgets('locked entry shows orange guidance on dark blue before shell',
      (tester) async {
    final gate = _memoryGate();

    await tester.pumpWidget(
      MaterialApp(
        home: AppEntryRoot(
          licenceGate: gate,
          initialUnlocked: false,
          child: const Scaffold(
            key: Key('main_shell_marker'),
            body: Text('MAIN_SHELL'),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.byKey(kEntryAccessScreenKey), findsOneWidget);
    expect(find.text(kEntryAccessGuidanceText), findsOneWidget);
    expect(find.text('MAIN_SHELL'), findsNothing);
    expect(find.byKey(const Key('main_shell_marker')), findsNothing);

    final scaffold = tester.widget<Scaffold>(find.byKey(kEntryAccessScreenKey));
    expect(scaffold.backgroundColor, kEntryAccessBg);

    final guidance = tester.widget<Text>(find.text(kEntryAccessGuidanceText));
    expect(guidance.style?.color, kEntryAccessOrange);
  });

  testWidgets('unlocked entry shows main shell without entry surface',
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
    expect(find.byKey(kEntryAccessScreenKey), findsNothing);
    expect(find.text(kEntryAccessGuidanceText), findsNothing);
  });

  testWidgets('successful keygen unlock reveals shell without process restart',
      (tester) async {
    final gate = _memoryGate(licenceAccepted: true);

    await tester.pumpWidget(
      MaterialApp(
        home: AppEntryRoot(
          licenceGate: gate,
          initialUnlocked: false,
          child: const Scaffold(body: Text('MAIN_SHELL_AFTER_UNLOCK')),
        ),
      ),
    );
    await tester.pump();
    expect(find.byKey(kEntryAccessScreenKey), findsOneWidget);

    // Real gate APIs (shipped path).
    await gate.recordPaymentSuccess(
      'cs_test_entry',
      keygen: 'RPT-KEY-TEST-ENTRY-AAAA',
    );
    final root = tester.state<AppEntryRootState>(find.byType(AppEntryRoot));
    await root.markUnlockedAndRefresh();
    await tester.pump();

    expect(find.text('MAIN_SHELL_AFTER_UNLOCK'), findsOneWidget);
    expect(find.byKey(kEntryAccessScreenKey), findsNothing);
  });

  testWidgets('RestorePrivacyApp mounts entry gate ahead of suite shell',
      (tester) async {
    await tester.pumpWidget(
      const RestorePrivacyApp(
        entryInitiallyUnlocked: false,
        walletTab: SizedBox.shrink(),
        evolveTab: SizedBox.shrink(),
      ),
    );
    await tester.pump();

    expect(find.byKey(kEntryAccessScreenKey), findsOneWidget);
    expect(find.text(kEntryAccessGuidanceText), findsOneWidget);
    expect(find.byType(SuiteShell), findsNothing);
    expect(find.text(kSuiteProductName), findsWidgets);
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
    expect(find.byKey(kEntryAccessScreenKey), findsNothing);
  });

  test('isAppEntryUnlocked follows paymentAllowsConnect', () async {
    final gate = _memoryGate(licenceAccepted: true);
    expect(await isAppEntryUnlocked(gate), isFalse);

    await gate.recordPaymentSuccess(
      'cs_ok',
      keygen: 'RPT-KEY-OK-OK-OK-OK',
    );
    expect(await isAppEntryUnlocked(gate), isTrue);
    expect(await isAppEntryUnlocked(null), isFalse);
  });
}
