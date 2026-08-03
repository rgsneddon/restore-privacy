/// Suite optional account: VPN independence + unified register apply + prompt UX.
library;

import 'dart:io';

import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_ledger.dart' as evolve_ledger;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
import 'package:evolve/perc/services/perc_wallet_store.dart' as evolve_store;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:perccent_wallet/perc/providers/perc_wallet_provider.dart'
    as perc_wallet;
import 'package:perccent_wallet/perc/services/perc_ledger.dart' as perc_ledger;
import 'package:perccent_wallet/perc/services/perc_ledger_hub.dart' as perc_hub;
import 'package:perccent_wallet/perc/services/perc_network_coordinator.dart'
    as perc_coord;
import 'package:perccent_wallet/perc/services/perc_wallet_store.dart'
    as perc_store;
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_account.dart';
import 'package:restore_privacy_client/suite_account_apply.dart';
import 'package:restore_privacy_client/suite_account_prompt.dart';
import 'package:restore_privacy_client/theme.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('shouldOfferSuiteAccountPrompt (pure)', () {
    test('product path never offers Suite username/password prompt', () {
      // Dedicated residual VPN: always false regardless of flags.
      expect(
        shouldOfferSuiteAccountPrompt(
          vpnUnlocked: true,
          deferred: false,
          registered: false,
        ),
        isFalse,
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

  group('applySuiteAccountToWalletAndEvolve (real dual providers)', () {
    late _SharedJsonLedger shared;

    setUp(() {
      shared = _SharedJsonLedger();
      perc_hub.PercLedgerHub.resetForTest();
      evolve_hub.PercLedgerHub.resetForTest();
      perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
      evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
      perc_wallet.PercWalletProvider.sessionTimeoutEnabled = false;
      evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = false;
    });

    tearDown(() {
      perc_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
      evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
      perc_hub.PercLedgerHub.resetForTest();
      evolve_hub.PercLedgerHub.resetForTest();
    });

    test(
      'one register leaves Perccent and Evolve isLoggedIn as same user',
      () async {
        late perc_wallet.PercWalletProvider perc;
        late evolve_wallet.PercWalletProvider evolve;
        var busHits = 0;
        void onBus() => busHits++;
        SuiteAccountBus.instance.addListener(onBus);
        addTearDown(() => SuiteAccountBus.instance.removeListener(onBus));

        final surfaces = SuiteAccountPackageSurfaces(
          createPercProvider: () {
            perc = perc_wallet.PercWalletProvider(
              store: _PercSharedStore(shared),
            );
            return perc;
          },
          createEvolveProvider: () {
            evolve = evolve_wallet.PercWalletProvider(
              store: _EvolveSharedStore(shared),
            );
            return evolve;
          },
          reloadEvolveHub: () =>
              evolve_hub.PercLedgerHub.instance.reloadFromStore(),
          persistPercHub: () => perc_hub.PercLedgerHub.instance.persistLocal(),
        );

        await applySuiteAccountToWalletAndEvolve(
          username: 'carol',
          password: 'password12345',
          register: true,
          surfaces: surfaces,
        );

        // Real dual-surface assertion — not a no-op runner.
        expect(perc.isLoggedIn, isTrue, reason: 'Perccent must be signed in');
        expect(perc.loggedInUsername, 'carol');
        expect(perc.hasAppAccess, isTrue);
        expect(evolve.isLoggedIn, isTrue, reason: 'Evolve must be signed in');
        expect(evolve.loggedInUsername, 'carol');
        expect(evolve.hasAppAccess, isTrue);
        expect(busHits, 1);
        expect(SuiteAccountBus.instance.lastUsername, 'carol');

        final account = SuiteAccountStore(MemorySettingsBackend());
        await account.markRegistered('carol');
        expect(
          shouldOfferSuiteAccountPrompt(
            vpnUnlocked: true,
            deferred: await account.isDeferred(),
            registered: await account.isRegistered(),
          ),
          isFalse,
        );
      },
    );

    test('failed auth does not claim logged-in (requireWalletSurfaceLoggedIn)',
        () {
      expect(
        () => requireWalletSurfaceLoggedIn(
          surfaceLabel: 'Perccent wallet',
          isLoggedIn: false,
          loggedInUsername: null,
          username: 'x',
          lastError: 'bad_password',
        ),
        throwsA(
          isA<StateError>().having(
            (e) => e.message,
            'message',
            contains('Perccent wallet did not sign in'),
          ),
        ),
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

  group('source structure (VPN product: no post-keygen account prompt)', () {
    test('suite account copy remains optional-only if ever surfaced', () {
      expect(kSuiteAccountPromptTitle.toLowerCase(), contains('wallet'));
      expect(kSuiteAccountDeferLabel.toLowerCase(), contains('vpn'));
      expect(kSuiteAccountPromptBody.toLowerCase(), contains('not required'));
    });

    test('main never calls showSuiteAccountPrompt after KEYGEN unlock', () {
      final mainSrc = _readSuiteSource('lib/main.dart');
      final walletSrc = _readSuiteSource('lib/suite_wallet_tab.dart');
      final evolveSrc = _readSuiteSource('lib/suite_evolve_tab.dart');
      final accountSrc = _readSuiteSource('lib/suite_account.dart');

      // Product lock: no live showSuiteAccountPrompt on TunnelHome unlock path.
      expect(mainSrc.contains('showSuiteAccountPrompt('), isFalse);
      expect(mainSrc.contains('import \'suite_account_prompt.dart\''), isFalse);
      // Fail-closed helper still present (no-op / hard-false).
      expect(mainSrc.contains('shouldOfferSuiteAccountPrompt'), isTrue);
      expect(accountSrc.contains('return false;'), isTrue);
      // No residual account/seed first-run status copy.
      expect(mainSrc.contains('account, seed, licence'), isFalse);
      expect(
        mainSrc.contains('Accept the end-user licence'),
        isTrue,
      );

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
  final fromTest = File(
    '${Directory.current.path}${Platform.pathSeparator}$relative',
  );
  if (fromTest.existsSync()) return fromTest.readAsStringSync();
  throw StateError('cannot read $relative (cwd=${Directory.current.path})');
}

/// Shared on-disk ledger simulation for Perccent + Evolve package hubs in tests.
class _SharedJsonLedger {
  Map<String, dynamic>? json;
}

class _PercSharedStore implements perc_store.PercWalletStore {
  _PercSharedStore(this.shared);
  final _SharedJsonLedger shared;

  @override
  Future<perc_ledger.PercLedger?> load() async {
    final j = shared.json;
    if (j == null) return null;
    return perc_ledger.PercLedger.fromJson(j);
  }

  @override
  Future<void> save(perc_ledger.PercLedger ledger) async {
    shared.json = ledger.toJson();
  }
}

class _EvolveSharedStore implements evolve_store.PercWalletStore {
  _EvolveSharedStore(this.shared);
  final _SharedJsonLedger shared;

  @override
  Future<evolve_ledger.PercLedger?> load() async {
    final j = shared.json;
    if (j == null) return null;
    return evolve_ledger.PercLedger.fromJson(j);
  }

  @override
  Future<void> save(evolve_ledger.PercLedger ledger) async {
    shared.json = ledger.toJson();
  }
}
