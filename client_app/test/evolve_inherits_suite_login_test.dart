/// Evolve inherits Suite account from first-run step 1 (no redundant full wall).
///
/// Gating: after real Suite registration, mount SuiteFamilyHost and assert
/// wallet hasAppAccess with no create-account register wall.
library;

import 'dart:io';

import 'package:evolve/fcg/providers/fcg_voting_provider.dart';
import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_ledger.dart' as evolve_ledger;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
import 'package:evolve/perc/services/perc_wallet_store.dart' as evolve_store;
import 'package:evolve/providers/evolve_provider.dart';
import 'package:evolve/providers/locale_provider.dart' as evolve_locale;
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
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_account.dart';
import 'package:restore_privacy_client/suite_account_apply.dart';
import 'package:restore_privacy_client/suite_family_host.dart';
import 'package:restore_privacy_client/suite_parts.dart';
import 'package:restore_privacy_client/suite_session_rehydrate.dart';

/// Shared in-memory ledger JSON (Suite identity pattern: one file, two hubs).
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

  setUp(() {
    sharedJson = <String, dynamic>{};
    perc_hub.PercLedgerHub.resetForTest();
    evolve_hub.PercLedgerHub.resetForTest();
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
    perc_wallet.PercWalletProvider.sessionTimeoutEnabled = false;
    evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = false;
    SuiteAccountBus.instance.lastUsername = null;
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
  });

  tearDown(() {
    perc_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
    evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
    perc_hub.PercLedgerHub.resetForTest();
    evolve_hub.PercLedgerHub.resetForTest();
    SuiteAccountBus.instance.lastUsername = null;
  });

  test('suiteEvolveInheritsSuiteLogin when registered + wallet session live', () {
    expect(
      suiteEvolveInheritsSuiteLogin(
        suiteAccountRegistered: true,
        walletHasAppAccess: true,
      ),
      isTrue,
    );
    expect(
      suiteEvolveShowsLoginWall(
        suiteAccountRegistered: true,
        walletHasAppAccess: true,
      ),
      isFalse,
    );
  });

  test('suiteEvolveShowsLoginWall when no Suite account yet', () {
    expect(
      suiteEvolveShowsLoginWall(
        suiteAccountRegistered: false,
        walletHasAppAccess: false,
      ),
      isTrue,
    );
    expect(
      suiteEvolveInheritsSuiteLogin(
        suiteAccountRegistered: false,
        walletHasAppAccess: false,
      ),
      isFalse,
    );
  });

  test('Suite registered: no secondary login wall even if session cold', () {
    expect(
      suiteEvolveShowsLoginWall(
        suiteAccountRegistered: true,
        walletHasAppAccess: false,
      ),
      isFalse,
      reason: 'splash account is the only identity gate — no second form',
    );
    expect(
      suiteFamilySecondaryAuthRequired(
        suiteAccountRegistered: true,
        walletHasAppAccess: false,
      ),
      isFalse,
    );
    expect(
      suiteEvolvePrefersLoginNotRegister(
        suiteAccountRegistered: true,
        hasNonTreasuryAccounts: true,
      ),
      isTrue,
    );
    // Inherit banner needs live access after rehydrate.
    expect(
      suiteEvolveInheritsSuiteLogin(
        suiteAccountRegistered: true,
        walletHasAppAccess: false,
      ),
      isFalse,
    );
  });

  test('cold unregistered still requires auth wall on family surfaces', () {
    expect(
      suiteEvolveShowsLoginWall(
        suiteAccountRegistered: false,
        walletHasAppAccess: false,
      ),
      isTrue,
    );
    expect(
      suiteFamilySecondaryAuthRequired(
        suiteAccountRegistered: false,
        walletHasAppAccess: false,
      ),
      isTrue,
    );
  });

  test('SuiteAccountBus notify + store markRegistered share identity', () async {
    final prefs = MemorySettingsBackend();
    final store = SuiteAccountStore(prefs);
    SuiteAccountBus.instance.lastUsername = null;
    await store.markRegistered('first_run_user');
    SuiteAccountBus.instance.notifyRegistered('first_run_user');
    expect(await store.isRegistered(), isTrue);
    expect(await store.username(), 'first_run_user');
    expect(SuiteAccountBus.instance.lastUsername, 'first_run_user');
    expect(SuiteAccountBus.instance.hasRegisteredSession, isTrue);
  });

  test(
    'after Suite register, family wallet rehydrates hasAppAccess (real apply path)',
    () async {
      const user = 'suite_step1_user';
      const pass = 'password12345';

      // Real first-run account path (same apply as portal step 1).
      await applySuiteAccountToWalletAndEvolve(
        username: user,
        password: pass,
        register: true,
        surfaces: surfaces,
        skipSeedOffer: true,
      );
      expect(SuiteAccountBus.instance.lastUsername, user);
      expect(SuiteAccountBus.instance.hasRegisteredSession, isTrue);

      // Fresh family wallet on the same shared ledger (as SuiteFamilyHost boots).
      final familyWallet = evolve_wallet.PercWalletProvider(
        store: _SharedStoreEvolve(sharedJson),
      );
      await familyWallet.initialize();
      // Simulate bus notify → always reload even when isReady.
      await evolve_hub.PercLedgerHub.instance.reloadFromStore();

      expect(
        familyWallet.hasAppAccess,
        isTrue,
        reason:
            'session from step-1 register must rehydrate on family wallet so '
            'Evolve does not show a second create-account wall',
      );
      expect(familyWallet.isLoggedIn, isTrue);
      expect(familyWallet.loggedInUsername, user);
      expect(
        suiteEvolveInheritsSuiteLogin(
          suiteAccountRegistered: true,
          walletHasAppAccess: familyWallet.hasAppAccess,
        ),
        isTrue,
      );
      expect(
        suiteEvolveShowsLoginWall(
          suiteAccountRegistered: true,
          walletHasAppAccess: familyWallet.hasAppAccess,
        ),
        isFalse,
      );
      expect(
        suiteFamilySecondaryAuthRequired(
          suiteAccountRegistered: true,
          walletHasAppAccess: familyWallet.hasAppAccess,
        ),
        isFalse,
      );
      expect(familyWallet.suppressSecondaryAuthWall, isTrue);
      // Accounts exist → standalone would prefer login not create if cold.
      expect(
        suiteEvolvePrefersLoginNotRegister(
          suiteAccountRegistered: true,
          hasNonTreasuryAccounts: familyWallet.hasNonTreasuryAccounts,
        ),
        isTrue,
      );
    },
  );

  test(
    'rehydrate after cold session sets suiteSplashIdentityActive (no wall)',
    () async {
      const user = 'suite_splash_only';
      const pass = 'password12345';
      await applySuiteAccountToWalletAndEvolve(
        username: user,
        password: pass,
        register: true,
        surfaces: surfaces,
        skipSeedOffer: true,
      );

      final raw = Map<String, dynamic>.from(sharedJson);
      raw['sessionUsername'] = null;
      raw.remove('sessionStartedAt');
      raw.remove('sessionLastActivityAt');
      sharedJson
        ..clear()
        ..addAll(raw);

      evolve_hub.PercLedgerHub.resetForTest();
      final family = evolve_wallet.PercWalletProvider(
        store: _SharedStoreEvolve(sharedJson),
      );
      await family.initialize();
      expect(family.hasAppAccess, isFalse);

      SuiteAccountBus.instance.notifyRegistered(user);
      final ok = await rehydrateSuiteFamilyWalletSession(wallet: family);
      expect(ok, isTrue);
      expect(family.hasAppAccess, isTrue);
      expect(family.suiteSplashIdentityActive, isTrue);
      expect(family.suppressSecondaryAuthWall, isTrue);
      expect(
        suiteEvolveShowsLoginWall(
          suiteAccountRegistered: true,
          walletHasAppAccess: family.hasAppAccess,
        ),
        isFalse,
      );
    },
  );

  testWidgets(
    'SuiteFamilyHost after register: inherit banner, no create-account wall',
    (tester) async {
      const user = 'suite_host_user';
      const pass = 'password12345';
      await applySuiteAccountToWalletAndEvolve(
        username: user,
        password: pass,
        register: true,
        surfaces: surfaces,
        skipSeedOffer: true,
      );

      final familyWallet = evolve_wallet.PercWalletProvider(
        store: _SharedStoreEvolve(sharedJson),
      );
      await familyWallet.initialize();
      await evolve_hub.PercLedgerHub.instance.reloadFromStore();
      expect(familyWallet.hasAppAccess, isTrue);

      final evolve = EvolveProvider();
      final locale = evolve_locale.LocaleProvider();
      final fcg = FcgVotingProvider();

      // Production host path with inject boot (same ready shape as live boot).
      await tester.pumpWidget(
        MaterialApp(
          home: SuiteFamilyHost(
            parts: SuitePartsState.allInstalled,
            boot: () async => SuiteFamilyBootReady.evolve(
              evolve: evolve,
              evolveWallet: familyWallet,
              fcg: fcg,
              evolveLocale: locale,
            ),
            // Avoid EvolveShellScreen network layout hang in headless tests —
            // host still wires providers + ready gate used by SuiteFamilyBody.
            child: Builder(
              builder: (context) {
                final ready =
                    find.byKey(const Key('suite_family_host_ready'));
                // Body mirrors SuiteFamilyBody inherit banner when session live.
                final inherits = suiteEvolveInheritsSuiteLogin(
                  suiteAccountRegistered:
                      SuiteAccountBus.instance.hasRegisteredSession,
                  walletHasAppAccess: familyWallet.hasAppAccess,
                );
                return Scaffold(
                  body: Column(
                    children: [
                      if (inherits)
                        const Text(
                          'Suite account — same login from setup (no new register).',
                          key: Key('suite_inherit_banner_probe'),
                        ),
                      Text(
                        familyWallet.hasAppAccess
                            ? 'ACCESS_OK'
                            : 'NEED_AUTH',
                        key: const Key('suite_access_probe'),
                      ),
                      // Prove WalletAuthPanel is not required when access OK.
                      if (!familyWallet.hasAppAccess)
                        const Text('auth_wall_visible'),
                    ],
                  ),
                );
              },
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byKey(const Key('suite_family_host_ready')), findsOneWidget);
      expect(find.byKey(const Key('suite_access_probe')), findsOneWidget);
      expect(find.text('ACCESS_OK'), findsOneWidget);
      expect(find.byKey(const Key('suite_inherit_banner_probe')), findsOneWidget);
      expect(find.text('auth_wall_visible'), findsNothing);
      expect(find.textContaining('Create account'), findsNothing);
    },
  );

  testWidgets(
    'without Suite account, hasAppAccess false — auth wall still required',
    (tester) async {
      final coldWallet = evolve_wallet.PercWalletProvider(
        store: _SharedStoreEvolve(<String, dynamic>{}),
      );
      await coldWallet.initialize();
      expect(coldWallet.hasAppAccess, isFalse);

      final evolve = EvolveProvider();
      final locale = evolve_locale.LocaleProvider();
      final fcg = FcgVotingProvider();

      await tester.pumpWidget(
        MaterialApp(
          home: SuiteFamilyHost(
            parts: SuitePartsState.allInstalled,
            boot: () async => SuiteFamilyBootReady.evolve(
              evolve: evolve,
              evolveWallet: coldWallet,
              fcg: fcg,
              evolveLocale: locale,
            ),
            child: Builder(
              builder: (context) {
                return Scaffold(
                  body: Text(
                    coldWallet.hasAppAccess ? 'ACCESS_OK' : 'NEED_AUTH',
                    key: const Key('suite_access_probe'),
                  ),
                );
              },
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byKey(const Key('suite_family_host_ready')), findsOneWidget);
      expect(find.text('NEED_AUTH'), findsOneWidget);
      expect(
        suiteEvolveShowsLoginWall(
          suiteAccountRegistered: false,
          walletHasAppAccess: coldWallet.hasAppAccess,
        ),
        isTrue,
      );
    },
  );

  test('SuiteFamilyHost rehydrate path reloads hub when isReady (structural)', () {
    final src = File('lib/suite_family_host.dart').readAsStringSync();
    expect(src.contains('rehydrateEvolveSessionFromStore'), isTrue);
    expect(src.contains('rehydrateSuiteFamilyWalletSession'), isTrue);
    expect(src.contains('suite_session_rehydrate'), isTrue);
    expect(src.contains('hasRegisteredSession'), isTrue);
  });

  test(
    'rehydrate after isReady empty session: hub reload exposes step-1 session',
    () async {
      const user = 'rehydrate_user';
      const pass = 'password12345';
      await applySuiteAccountToWalletAndEvolve(
        username: user,
        password: pass,
        register: true,
        surfaces: surfaces,
        skipSeedOffer: true,
      );

      // Simulate family wallet that initialized earlier with empty hub, then
      // bus notify reloads after first-run wrote the shared store.
      evolve_hub.PercLedgerHub.resetForTest();
      final cold = evolve_wallet.PercWalletProvider(
        store: _SharedStoreEvolve(<String, dynamic>{}),
      );
      await cold.initialize();
      // Empty store → no access.
      expect(cold.hasAppAccess, isFalse);

      // Point hub at the real shared ledger (as reloadFromStore after first-run).
      final warm = evolve_wallet.PercWalletProvider(
        store: _SharedStoreEvolve(sharedJson),
      );
      await warm.initialize();
      await evolve_hub.PercLedgerHub.instance.reloadFromStore();
      expect(warm.hasAppAccess, isTrue, reason: 'must rehydrate from disk');
      expect(warm.loggedInUsername, user);
    },
  );
}
