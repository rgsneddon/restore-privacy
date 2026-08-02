/// Honest first-run portal seed path: real BIP39 + attach/publish (no wordNN).
library;

import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_ledger.dart' as evolve_ledger;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
import 'package:evolve/perc/services/perc_network_rendezvous.dart'
    as evolve_rendezvous;
import 'package:evolve/perc/services/perc_seed_recovery.dart';
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
import 'package:restore_privacy_client/first_run_gate.dart';
import 'package:restore_privacy_client/first_run_portal.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_account.dart';
import 'package:restore_privacy_client/suite_account_apply.dart';
import 'package:restore_privacy_client/suite_account_seed.dart';

/// Shared in-memory ledger JSON for Perccent + Evolve (suite identity pattern).
class _SharedStorePerc implements perc_store.PercWalletStore {
  _SharedStorePerc(this.json);
  final Map<String, dynamic> json;

  @override
  Future<perc_ledger.PercLedger?> load() async {
    if (json.isEmpty) return null;
    return perc_ledger.PercLedger.fromJson(Map<String, dynamic>.from(json));
  }

  @override
  Future<void> save(perc_ledger.PercLedger ledger) async {
    json
      ..clear()
      ..addAll(ledger.toJson());
  }
}

class _SharedStoreEvolve implements evolve_store.PercWalletStore {
  _SharedStoreEvolve(this.json);
  final Map<String, dynamic> json;

  @override
  Future<evolve_ledger.PercLedger?> load() async {
    if (json.isEmpty) return null;
    return evolve_ledger.PercLedger.fromJson(Map<String, dynamic>.from(json));
  }

  @override
  Future<void> save(evolve_ledger.PercLedger ledger) async {
    json
      ..clear()
      ..addAll(ledger.toJson());
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Map<String, dynamic> sharedJson;
  late SuiteAccountPackageSurfaces surfaces;
  late MemorySettingsBackend prefs;
  late MemorySettingsBackend licenceBackend;
  late LicenceGate gate;
  late SuiteAccountStore accounts;
  late FirstRunStore firstRun;

  setUp(() {
    sharedJson = <String, dynamic>{};
    prefs = MemorySettingsBackend();
    licenceBackend = MemorySettingsBackend();
    perc_hub.PercLedgerHub.resetForTest();
    evolve_hub.PercLedgerHub.resetForTest();
    SuiteSeedEnvelopeStore.resetForTest();
    evolve_rendezvous.PercNetworkRendezvous.resetForTest();
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
    // Avoid pending FakeTimer after widget dispose (session timeout arm).
    perc_wallet.PercWalletProvider.sessionTimeoutEnabled = false;
    evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = false;
    surfaces = SuiteAccountPackageSurfaces(
      createPercProvider: () => perc_wallet.PercWalletProvider(
        store: _SharedStorePerc(sharedJson),
      ),
      createEvolveProvider: () => evolve_wallet.PercWalletProvider(
        store: _SharedStoreEvolve(sharedJson),
      ),
      reloadEvolveHub: () => evolve_hub.PercLedgerHub.instance.reloadFromStore(),
      persistPercHub: () => perc_hub.PercLedgerHub.instance.persistLocal(),
    );
    gate = LicenceGate(MemoryLicenceBackend({}));
    accounts = SuiteAccountStore(prefs);
    firstRun = FirstRunStore(
      backend: prefs,
      isAccountRegistered: accounts.isRegistered,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );
  });

  tearDown(() {
    perc_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
    evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
    SuiteSeedEnvelopeStore.resetForTest();
    evolve_rendezvous.PercNetworkRendezvous.resetForTest();
    perc_hub.PercLedgerHub.resetForTest();
    evolve_hub.PercLedgerHub.resetForTest();
  });

  test('generateSuiteSeedWords is real BIP39 not wordNN stub', () async {
    final words = await generateSuiteSeedWords();
    expect(words.length, PercSeedRecovery.wordCount);
    PercSeedRecovery.validateMnemonic(words);
    expect(isStubSuiteSeedWords(words), isFalse);
    // Full stub phrase must never appear as product output.
    final stub = List.generate(
      12,
      (i) => 'word${(i + 1).toString().padLeft(2, '0')}',
    ).join(' ');
    expect(words.join(' '), isNot(equals(stub)));
  });

  test('attachAndPublishSuiteSeedForUser writes restorable envelope', () async {
    await applySuiteAccountToWalletAndEvolve(
      username: 'seed_portal_user',
      password: 'password12345',
      register: true,
      surfaces: surfaces,
      skipSeedOffer: true,
      suitePrefsBackend: prefs,
      licenceBackend: licenceBackend,
    );
    final words = await generateSuiteSeedWords();
    await attachAndPublishSuiteSeedForUser(
      words: words,
      username: 'seed_portal_user',
      password: 'password12345',
      surfaces: surfaces,
      suitePrefsBackend: prefs,
      licenceBackend: licenceBackend,
    );
    final fp = PercSeedRecovery.fingerprint(words);
    final pub = await SuiteSeedEnvelopeStore.fetch(fp);
    expect(pub, isNotNull, reason: 'publish must stage restorable envelope');
    expect(pub!.envelopeB64, isNotEmpty);
    // Reject stub attach before BIP39 validate.
    await expectLater(
      attachAndPublishSuiteSeedForUser(
        words: List.generate(
          12,
          (i) => 'word${(i + 1).toString().padLeft(2, '0')}',
        ),
        username: 'x',
        password: 'password12345',
        surfaces: surfaces,
      ),
      throwsA(isA<StateError>()),
    );
  });

  testWidgets(
    'FirstRunPortal seed step uses real generate + attach (not wordNN)',
    (tester) async {
      var attachCalled = false;
      List<String>? shownWords;
      Object? attachError;

      Future<void> pumpUntil(bool Function() done, {int max = 200}) async {
        for (var i = 0; i < max; i++) {
          await tester.pump(const Duration(milliseconds: 50));
          if (done()) return;
        }
      }

      await tester.pumpWidget(
        MaterialApp(
          home: FirstRunPortal(
            onComplete: () {},
            licenceGate: gate,
            accountStore: accounts,
            firstRunStore: firstRun,
            surfaces: surfaces,
            suitePrefsBackend: prefs,
            licenceBackend: licenceBackend,
            initialState: const FirstRunState(
              accountDone: false,
              seedDone: false,
              licenceAccepted: false,
            ),
            // Drive real apply with injectable surfaces.
            applyCredentials: ({
              required String username,
              required String password,
              required bool register,
            }) =>
                applySuiteAccountToWalletAndEvolve(
                  username: username,
                  password: password,
                  register: register,
                  surfaces: surfaces,
                  skipSeedOffer: true,
                  suitePrefsBackend: prefs,
                  licenceBackend: licenceBackend,
                ),
            generateSeedWords: generateSuiteSeedWords,
            attachAndPublishSeed: (words) async {
              try {
                expect(isStubSuiteSeedWords(words), isFalse);
                PercSeedRecovery.validateMnemonic(words);
                await attachAndPublishSuiteSeedForUser(
                  words: words,
                  username: 'portal_user',
                  password: 'password12345',
                  surfaces: surfaces,
                  suitePrefsBackend: prefs,
                  licenceBackend: licenceBackend,
                );
                attachCalled = true;
                shownWords = List<String>.from(words);
              } catch (e) {
                attachError = e;
                rethrow;
              }
            },
          ),
        ),
      );
      await tester.pump();
      await tester.pump();

      // Account step
      expect(find.text(kFirstRunAccountTitle), findsOneWidget);
      await tester.enterText(find.byType(TextField).at(0), 'portal_user');
      await tester.enterText(find.byType(TextField).at(1), 'password12345');
      await tester.tap(find.byKey(kFirstRunAccountContinueKey));
      await pumpUntil(() => find.text(kFirstRunSeedTitle).evaluate().isNotEmpty);
      expect(
        find.text(kFirstRunSeedTitle),
        findsOneWidget,
        reason: 'register must advance to seed step',
      );

      // Generate real seed
      await tester.tap(find.byKey(kFirstRunSeedGenerateKey));
      await pumpUntil(
        () => find.byKey(kFirstRunSeedConfirmKey).evaluate().isNotEmpty,
      );
      expect(find.byKey(kFirstRunSeedConfirmKey), findsOneWidget);

      // Visible phrase must not be word01..word12
      final stubPhrase = List.generate(
        12,
        (i) => 'word${(i + 1).toString().padLeft(2, '0')}',
      ).join(' ');
      expect(find.text(stubPhrase), findsNothing);

      await tester.tap(find.byKey(kFirstRunSeedConfirmKey));
      await pumpUntil(
        () => find.text(kFirstRunLicenceStepTitle).evaluate().isNotEmpty ||
            attachError != null,
        max: 300,
      );

      expect(
        attachError,
        isNull,
        reason: 'attach must not throw: $attachError',
      );
      expect(attachCalled, isTrue, reason: 'confirm must invoke attach/publish');
      expect(shownWords, isNotNull);
      expect(isStubSuiteSeedWords(shownWords!), isFalse);
      PercSeedRecovery.validateMnemonic(shownWords!);
      expect(await firstRun.isSeedDone(), isTrue);
      expect(find.text(kFirstRunLicenceStepTitle), findsOneWidget);

      final fp = PercSeedRecovery.fingerprint(shownWords!);
      final pub = await SuiteSeedEnvelopeStore.fetch(fp);
      expect(
        pub,
        isNotNull,
        reason: 'portal confirm must publish restorable envelope',
      );
    },
  );
}
