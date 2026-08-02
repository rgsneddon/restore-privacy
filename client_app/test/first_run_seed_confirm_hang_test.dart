/// Seed confirm after “I’ve written them down” must not hang unbounded.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/first_run_gate.dart';
import 'package:restore_privacy_client/first_run_portal.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_account.dart';
import 'package:restore_privacy_client/suite_account_seed.dart';

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
    'slow attach surfaces timeout error and leaves seed step (no infinite busy)',
    (tester) async {
      await accounts.markRegistered('seed_user');
      final hang = Completer<void>();
      await tester.pumpWidget(
        MaterialApp(
          home: FirstRunPortal(
            onComplete: () {},
            licenceGate: gate,
            accountStore: accounts,
            firstRunStore: firstRun,
            seedConfirmTimeout: const Duration(milliseconds: 80),
            initialState: const FirstRunState(
              accountDone: true,
              seedDone: false,
              licenceAccepted: false,
            ),
            generateSeedWords: () async => List.generate(
              12,
              (i) => [
                'abandon',
                'ability',
                'able',
                'about',
                'above',
                'absent',
                'absorb',
                'abstract',
                'absurd',
                'abuse',
                'access',
                'accident',
              ][i],
            ),
            attachAndPublishSeed: (_) => hang.future,
          ),
        ),
      );
      await tester.pump();
      await tester.pump();

      expect(find.text(kFirstRunSeedTitle), findsOneWidget);
      await tester.tap(find.byKey(kFirstRunSeedGenerateKey));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 20));
      expect(find.byKey(kFirstRunSeedConfirmKey), findsOneWidget);

      await tester.tap(find.byKey(kFirstRunSeedConfirmKey));
      await tester.pump();
      // Advance fake time past seedConfirmTimeout.
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump();

      expect(find.textContaining('timed out'), findsOneWidget);
      expect(find.byKey(kFirstRunSeedConfirmKey), findsOneWidget);
      expect(await firstRun.isSeedDone(), isFalse);
      // Button re-enabled (not stuck Please wait forever).
      final btn = tester.widget<FilledButton>(
        find.byKey(kFirstRunSeedConfirmKey),
      );
      expect(btn.onPressed, isNotNull);
      hang.complete();
    },
  );

  testWidgets(
    'successful attach advances to licence step',
    (tester) async {
      await accounts.markRegistered('seed_user');
      await tester.pumpWidget(
        MaterialApp(
          home: FirstRunPortal(
            onComplete: () {},
            licenceGate: gate,
            accountStore: accounts,
            firstRunStore: firstRun,
            seedConfirmTimeout: const Duration(seconds: 5),
            initialState: const FirstRunState(
              accountDone: true,
              seedDone: false,
              licenceAccepted: false,
            ),
            generateSeedWords: () async => List.generate(
              12,
              (i) => [
                'abandon',
                'ability',
                'able',
                'about',
                'above',
                'absent',
                'absorb',
                'abstract',
                'absurd',
                'abuse',
                'access',
                'accident',
              ][i],
            ),
            attachAndPublishSeed: (_) async {},
          ),
        ),
      );
      await tester.pump();
      await tester.tap(find.byKey(kFirstRunSeedGenerateKey));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 20));
      expect(find.byKey(kFirstRunSeedConfirmKey), findsOneWidget);
      await tester.tap(find.byKey(kFirstRunSeedConfirmKey));
      for (var i = 0; i < 20; i++) {
        await tester.pump(const Duration(milliseconds: 50));
        if (find.text(kFirstRunLicenceStepTitle).evaluate().isNotEmpty) break;
      }

      expect(await firstRun.isSeedDone(), isTrue);
      expect(find.text(kFirstRunLicenceStepTitle), findsOneWidget);
    },
  );

  test('kSuiteSeedConfirmTimeout is finite and positive', () {
    expect(kSuiteSeedConfirmTimeout.inSeconds, greaterThan(0));
    expect(kSuiteSeedConfirmTimeout.inSeconds, lessThanOrEqualTo(120));
  });
}
