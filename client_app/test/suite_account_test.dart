/// Suite optional account: VPN independence + unified register apply + prompt UX.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_account.dart';
import 'package:restore_privacy_client/suite_account_apply.dart';
import 'package:restore_privacy_client/suite_account_prompt.dart';
import 'package:restore_privacy_client/theme.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('shouldOfferSuiteAccountPrompt (pure)', () {
    test('offers only when VPN unlocked and not deferred/registered', () {
      expect(
        shouldOfferSuiteAccountPrompt(
          vpnUnlocked: true,
          deferred: false,
          registered: false,
        ),
        isTrue,
      );
      expect(
        shouldOfferSuiteAccountPrompt(
          vpnUnlocked: false,
          deferred: false,
          registered: false,
        ),
        isFalse,
      );
      expect(
        shouldOfferSuiteAccountPrompt(
          vpnUnlocked: true,
          deferred: true,
          registered: false,
        ),
        isFalse,
      );
      expect(
        shouldOfferSuiteAccountPrompt(
          vpnUnlocked: true,
          deferred: false,
          registered: true,
        ),
        isFalse,
      );
    });
  });

  group('suiteAccountBlocksVpnConnect (pure)', () {
    test('never blocks VPN when licence mayConnect is true', () {
      expect(
        suiteAccountBlocksVpnConnect(
          licenceMayConnect: true,
          suiteRegistered: false,
          suiteDeferred: false,
        ),
        isFalse,
      );
      expect(
        suiteAccountBlocksVpnConnect(
          licenceMayConnect: true,
          suiteRegistered: true,
          suiteDeferred: true,
        ),
        isFalse,
      );
    });

    test('blocks only when licence mayConnect is false', () {
      expect(
        suiteAccountBlocksVpnConnect(
          licenceMayConnect: false,
          suiteRegistered: true,
          suiteDeferred: true,
        ),
        isTrue,
      );
    });
  });

  group('SuiteAccountStore + LicenceGate independence', () {
    test('mayConnect ignores suite account flags', () async {
      final seed = <String, Object>{
        kKeyLicenceAccepted: true,
        kKeyLicenceId: kCurrentLicenceId,
        kKeyLicenceAcceptedAt: '1',
        kKeyPaymentStatus: kPaymentStatusActive,
        kKeyPaymentKeygen: 'RPT-KEY-AAAA-BBBB-CCCC-DDDD',
        kKeyPaymentSessionId: 'cs_test_suite_account',
      };
      final gate = LicenceGate(MemoryLicenceBackend(seed));
      final account = SuiteAccountStore(MemorySettingsBackend());

      expect(await gate.mayConnect(), isTrue);
      expect(await account.isRegistered(), isFalse);

      await account.markDeferred();
      expect(await gate.mayConnect(), isTrue);
      expect(
        suiteAccountBlocksVpnConnect(
          licenceMayConnect: await gate.mayConnect(),
          suiteRegistered: await account.isRegistered(),
          suiteDeferred: await account.isDeferred(),
        ),
        isFalse,
      );

      await account.markRegistered('alice');
      expect(await account.isRegistered(), isTrue);
      expect(await account.username(), 'alice');
      expect(await gate.mayConnect(), isTrue);
    });

    test('defer then register clears defer flag', () async {
      final account = SuiteAccountStore(MemorySettingsBackend());
      await account.markDeferred();
      expect(await account.isDeferred(), isTrue);
      await account.markRegistered('bob');
      expect(await account.isDeferred(), isFalse);
      expect(await account.isRegistered(), isTrue);
    });
  });

  group('applySuiteAccountToWalletAndEvolve (injected runner)', () {
    test('one apply notifies bus and records both-surface intent once', () async {
      final calls = <String>[];
      var busHits = 0;
      void onBus() => busHits++;
      SuiteAccountBus.instance.addListener(onBus);
      addTearDown(() {
        SuiteAccountBus.instance.removeListener(onBus);
      });

      await applySuiteAccountToWalletAndEvolve(
        username: 'carol',
        password: 'password1',
        register: true,
        runner: ({
          required String username,
          required String password,
          required bool register,
        }) async {
          calls.add('${register ? 'reg' : 'login'}:$username');
        },
      );

      expect(calls, ['reg:carol']);
      expect(busHits, 1);
      expect(SuiteAccountBus.instance.lastUsername, 'carol');

      // Second surface consumers only need the bus/store — no second register.
      final account = SuiteAccountStore(MemorySettingsBackend());
      await account.markRegistered('carol');
      expect(
        shouldOfferSuiteAccountPrompt(
          vpnUnlocked: true,
          deferred: await account.isDeferred(),
          registered: await account.isRegistered(),
        ),
        isFalse,
        reason: 'registered suite account must not re-prompt dual register',
      );
    });
  });

  group('showSuiteAccountPrompt widget', () {
    testWidgets('defer marks store and leaves VPN-facing outcome', (tester) async {
      final map = <String, dynamic>{};
      final store = SuiteAccountStore(MemorySettingsBackend(map));
      SuiteAccountPromptOutcome? outcome;

      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(scaffoldBackgroundColor: kChromeBg),
          home: Scaffold(
            body: Builder(
              builder: (context) {
                return TextButton(
                  key: const Key('open_prompt'),
                  onPressed: () async {
                    outcome = await showSuiteAccountPrompt(
                      context,
                      store: store,
                      applyCredentials: ({
                        required String username,
                        required String password,
                        required bool register,
                      }) async {},
                    );
                  },
                  child: const Text('open'),
                );
              },
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open_prompt')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('suite_account_prompt_title')), findsOneWidget);
      expect(find.byKey(const Key('suite_account_prompt_body')), findsOneWidget);
      expect(find.byKey(const Key('suite_account_defer')), findsOneWidget);
      // Singular form — one username/password, not two stacked panels.
      expect(find.byKey(const Key('suite_account_username')), findsOneWidget);
      expect(find.byKey(const Key('suite_account_password')), findsOneWidget);

      await tester.tap(find.byKey(const Key('suite_account_defer')));
      await tester.pumpAndSettle();

      expect(outcome, SuiteAccountPromptOutcome.deferred);
      expect(await store.isDeferred(), isTrue);
      expect(await store.isRegistered(), isFalse);
    });

    testWidgets('register path calls apply once and marks registered', (tester) async {
      final store = SuiteAccountStore(MemorySettingsBackend());
      var applyCount = 0;
      SuiteAccountPromptOutcome? outcome;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) {
                return TextButton(
                  key: const Key('open_prompt'),
                  onPressed: () async {
                    outcome = await showSuiteAccountPrompt(
                      context,
                      store: store,
                      applyCredentials: ({
                        required String username,
                        required String password,
                        required bool register,
                      }) async {
                        applyCount++;
                        expect(username, 'dave');
                        expect(password, 'password99');
                        expect(register, isTrue);
                      },
                    );
                  },
                  child: const Text('open'),
                );
              },
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open_prompt')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('suite_account_username')),
        'dave',
      );
      await tester.enterText(
        find.byKey(const Key('suite_account_password')),
        'password99',
      );
      await tester.tap(find.byKey(const Key('suite_account_submit')));
      await tester.pumpAndSettle();

      expect(applyCount, 1);
      expect(outcome, SuiteAccountPromptOutcome.registered);
      expect(await store.isRegistered(), isTrue);
      expect(await store.username(), 'dave');
    });
  });

  group('source structure (singular post-keygen prompt)', () {
    test('main wires one suite account prompt after keygen unlock', () {
      expect(kSuiteAccountPromptTitle.toLowerCase(), contains('wallet'));
      expect(kSuiteAccountPromptTitle.toLowerCase(), contains('evolve'));
      expect(kSuiteAccountDeferLabel.toLowerCase(), contains('vpn'));
      expect(kSuiteAccountPromptBody.toLowerCase(), contains('not required'));
    });

    test('shipped suite files mount singular optional account (not dual walls)',
        () {
      final mainSrc = _readSuiteSource('lib/main.dart');
      final walletSrc = _readSuiteSource('lib/suite_wallet_tab.dart');
      final evolveSrc = _readSuiteSource('lib/suite_evolve_tab.dart');

      expect(mainSrc.contains('_maybeShowSuiteAccountPrompt'), isTrue);
      expect(mainSrc.contains('showSuiteAccountPrompt'), isTrue);
      expect(mainSrc.contains('shouldOfferSuiteAccountPrompt'), isTrue);
      expect(
        '_maybeShowSuiteAccountPrompt'.allMatches(mainSrc).length,
        greaterThanOrEqualTo(1),
      );

      expect(walletSrc.contains('SuiteAccountBus'), isTrue);
      expect(evolveSrc.contains('SuiteAccountBus'), isTrue);
      // Tabs reload shared ledger; they do not each open a suite register sheet
      expect(walletSrc.contains('showSuiteAccountPrompt'), isFalse);
      expect(evolveSrc.contains('showSuiteAccountPrompt'), isFalse);
    });
  });
}

String _readSuiteSource(String relative) {
  for (final base in ['', 'client_app/']) {
    final f = File('$base$relative');
    if (f.existsSync()) return f.readAsStringSync();
  }
  // Relative to this test file: client_app/test/ → client_app/lib/
  final fromTest = File(
    '${Directory.current.path}${Platform.pathSeparator}$relative',
  );
  if (fromTest.existsSync()) return fromTest.readAsStringSync();
  throw StateError('cannot read $relative (cwd=${Directory.current.path})');
}
