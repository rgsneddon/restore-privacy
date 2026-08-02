/// Suite unified identity + seed export/import + re-login after timeout.
library;

import 'dart:io';

import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_ledger.dart' as evolve_ledger;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
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
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_account.dart';
import 'package:restore_privacy_client/suite_account_apply.dart';
import 'package:restore_privacy_client/suite_account_prompt.dart';
import 'package:restore_privacy_client/suite_account_seed.dart';
import 'package:restore_privacy_client/theme.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Map<String, dynamic> sharedJson;
  late SuiteAccountPackageSurfaces surfaces;
  late perc_wallet.PercWalletProvider lastPerc;
  late evolve_wallet.PercWalletProvider lastEvolve;

  setUp(() {
    sharedJson = <String, dynamic>{};
    perc_hub.PercLedgerHub.resetForTest();
    evolve_hub.PercLedgerHub.resetForTest();
    SuiteSeedEnvelopeStore.resetForTest();
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
    perc_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
    evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
    surfaces = SuiteAccountPackageSurfaces(
      createPercProvider: () {
        lastPerc = perc_wallet.PercWalletProvider(
          store: _SharedStorePerc(sharedJson),
        );
        return lastPerc;
      },
      createEvolveProvider: () {
        lastEvolve = evolve_wallet.PercWalletProvider(
          store: _SharedStoreEvolve(sharedJson),
        );
        return lastEvolve;
      },
      reloadEvolveHub: () => evolve_hub.PercLedgerHub.instance.reloadFromStore(),
      persistPercHub: () => perc_hub.PercLedgerHub.instance.persistLocal(),
    );
  });

  tearDown(() {
    perc_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
    evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
    SuiteSeedEnvelopeStore.resetForTest();
    perc_hub.PercLedgerHub.resetForTest();
    evolve_hub.PercLedgerHub.resetForTest();
  });

  group('unified Suite identity', () {
    test('one register yields same username on Perccent + Evolve', () async {
      await applySuiteAccountToWalletAndEvolve(
        username: 'suite_user',
        password: 'password12345',
        register: true,
        surfaces: surfaces,
        skipSeedOffer: true,
      );
      expect(lastPerc.isLoggedIn, isTrue);
      expect(lastPerc.loggedInUsername, 'suite_user');
      expect(lastEvolve.isLoggedIn, isTrue);
      expect(lastEvolve.loggedInUsername, 'suite_user');
      expect(SuiteAccountBus.instance.lastUsername, 'suite_user');
    });
  });

  group('re-login after timeout / logout', () {
    test('same password works after logout (session timeout class)', () async {
      await applySuiteAccountToWalletAndEvolve(
        username: 'timeout_user',
        password: 'password12345',
        register: true,
        surfaces: surfaces,
        skipSeedOffer: true,
      );

      // Family-host style provider on shared store after apply.
      final family = evolve_wallet.PercWalletProvider(
        store: _SharedStoreEvolve(sharedJson),
      );
      await family.initialize();
      await evolve_hub.PercLedgerHub.instance.reloadFromStore();
      if (!family.isLoggedIn) {
        await family.login('timeout_user', 'password12345');
      }
      expect(family.isLoggedIn, isTrue);

      await family.logout();
      expect(family.isLoggedIn, isFalse);

      await family.login('timeout_user', 'password12345');
      expect(
        family.isLoggedIn,
        isTrue,
        reason: family.errorMessage ?? 're-login failed after logout',
      );
      expect(family.loggedInUsername, 'timeout_user');
      expect(family.hasAppAccess, isTrue);
    });
  });

  group('seed export + import restore', () {
    test(
      'clean install: words-only restore via published envelope (no prefs inject)',
      () async {
        // Simulate network rendezvous with a published map (not Suite prefs).
        final published = <String, SuiteSeedPublishedRecovery>{};
        SuiteSeedEnvelopeStore.publishHandler = (fp, recovery) async {
          published[fp] = recovery;
        };
        SuiteSeedEnvelopeStore.fetchHandler =
            (fp) async => published[fp];

        final exportPrefs = MemorySettingsBackend();
        final licenceExport = MemorySettingsBackend();
        // Pre-seed licence/KEYGEN that must be sealed and restored.
        await licenceExport.setBool(kKeyLicenceAccepted, true);
        await licenceExport.setString(kKeyLicenceId, kCurrentLicenceId);
        await licenceExport.setString(kKeyPaymentStatus, kPaymentStatusActive);
        await licenceExport.setString(
          kKeyPaymentKeygen,
          'RPT-KEY-SEED-TEST-AAAA-BBBB',
        );

        late List<String> offeredWords;
        await applySuiteAccountToWalletAndEvolve(
          username: 'seed_user',
          password: 'password12345',
          register: true,
          surfaces: surfaces,
          suitePrefsBackend: exportPrefs,
          licenceBackend: licenceExport,
          seedOffer: (generate) async {
            offeredWords = await generate();
            expect(offeredWords.length, PercSeedRecovery.wordCount);
            return SuiteSeedOfferResult.enable(offeredWords);
          },
        );

        final fp = PercSeedRecovery.fingerprint(offeredWords);
        expect(published.containsKey(fp), isTrue, reason: 'export must publish');
        expect(published[fp]!.envelopeB64, isNotEmpty);
        expect(published[fp]!.metaBlobB64, isNotNull);

        // True clean install: wipe ledger, hubs, and ALL suite prefs.
        // Do NOT pass localEnvelopeB64; do NOT reuse exportPrefs.
        perc_hub.PercLedgerHub.resetForTest();
        evolve_hub.PercLedgerHub.resetForTest();
        sharedJson.clear();
        final cleanAccount = SuiteAccountStore(MemorySettingsBackend());
        final cleanPrefs = MemorySettingsBackend(); // empty
        final cleanLicence = MemorySettingsBackend(); // empty
        expect(await cleanAccount.isRegistered(), isFalse);
        expect(await cleanLicence.getString(kKeyPaymentKeygen), isNull);

        final restored = await restoreSuiteIdentityFromSeed(
          words: offeredWords,
          accountStore: cleanAccount,
          surfaces: surfaces,
          suitePrefsBackend: cleanPrefs,
          licenceBackend: cleanLicence,
          // intentionally no localEnvelopeB64
        );
        expect(restored, 'seed_user');
        expect(await cleanAccount.isRegistered(), isTrue);
        expect(await cleanAccount.username(), 'seed_user');
        expect(lastEvolve.isLoggedIn, isTrue);
        expect(lastEvolve.loggedInUsername, 'seed_user');
        // Sealed licence/KEYGEN rehydrated from published meta.
        expect(await cleanLicence.getBool(kKeyLicenceAccepted), isTrue);
        expect(await cleanLicence.getString(kKeyPaymentStatus), kPaymentStatusActive);
        expect(
          await cleanLicence.getString(kKeyPaymentKeygen),
          'RPT-KEY-SEED-TEST-AAAA-BBBB',
        );
      },
    );

    test('parseSuiteSeedPhrase validates 12 words', () {
      final words = PercSeedRecovery.generateMnemonic();
      final parsed = parseSuiteSeedPhrase(words.join('  '));
      expect(parsed, words);
      expect(() => parseSuiteSeedPhrase('too few'), throwsFormatException);
    });
  });

  group('seed export offer UI', () {
    testWidgets('prompt shows restore toggle and seed import field',
        (tester) async {
      final store = SuiteAccountStore(MemorySettingsBackend());

      await tester.pumpWidget(
        MaterialApp(
          theme: buildSuiteThemeDark(),
          home: Scaffold(
            body: Builder(
              builder: (context) {
                return FilledButton(
                  key: const Key('open_prompt'),
                  onPressed: () {
                    showSuiteAccountPrompt(
                      context,
                      store: store,
                      applyCredentials: ({
                        required String username,
                        required String password,
                        required bool register,
                      }) async {},
                      offerSeedOnRegister: true,
                    );
                  },
                  child: const Text('open'),
                );
              },
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.tap(find.byKey(const Key('open_prompt')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('suite_account_prompt_title')), findsOneWidget);
      // Import entry on clean install / first-run sheet.
      expect(find.byKey(const Key('suite_account_toggle_restore')), findsOneWidget);
      await tester.ensureVisible(find.byKey(const Key('suite_account_toggle_restore')));
      await tester.tap(find.byKey(const Key('suite_account_toggle_restore')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('suite_account_seed_import')), findsOneWidget);
      expect(find.text(kSuiteSeedImportTitle), findsOneWidget);
      expect(find.text(kSuiteSeedExportTitle), findsNothing);
    });

    test('prompt source wires seed export offer on production register path',
        () {
      final src = File('lib/suite_account_prompt.dart').readAsStringSync();
      expect(src.contains('suite_seed_export_dialog'), isTrue);
      expect(src.contains('seedOffer'), isTrue);
      expect(src.contains('kSuiteSeedExportTitle'), isTrue);
      expect(src.contains('restoreSuiteIdentityFromSeed'), isTrue);
      expect(src.contains('suite_account_toggle_restore'), isTrue);
      final applySrc = File('lib/suite_account_apply.dart').readAsStringSync();
      expect(applySrc.contains('refreshSeedRecoveryEnvelope'), isTrue);
      expect(applySrc.contains('publishSuiteSeedAfterExport'), isTrue);
      expect(applySrc.contains('disableLiveNodesForTests = true'), isTrue);
      final mainSrc = File('lib/main.dart').readAsStringSync();
      expect(mainSrc.contains('licenceBackend: store.backend'), isTrue);
      expect(mainSrc.contains('suitePrefsBackend: store.backend'), isTrue);
      final rpaiSrc = File('lib/suite_rpai_tab.dart').readAsStringSync();
      expect(rpaiSrc.contains('licenceBackend: prefsBackend'), isTrue);
    });
  });

  group('licence meta seal (optional KEYGEN rehydrate)', () {
    test('seal/unseal roundtrip preserves keygen fields', () {
      final words = PercSeedRecovery.generateMnemonic();
      final blob = sealSuiteSeedMeta(
        words: words,
        username: 'meta_user',
        licenceAccepted: true,
        licenceId: kCurrentLicenceId,
        paymentStatus: kPaymentStatusActive,
        paymentKeygen: 'RPT-KEY-TEST-AAAA-BBBB-CCCC',
      );
      final map = unsealSuiteSeedMeta(words: words, blobB64: blob);
      expect(map['username'], 'meta_user');
      expect(map['payment_keygen'], 'RPT-KEY-TEST-AAAA-BBBB-CCCC');
      expect(map['licence_accepted'], isTrue);
    });
  });
}

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
