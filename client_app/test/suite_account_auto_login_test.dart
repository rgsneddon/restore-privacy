/// After unified Suite account create, family wallet keeps hasAppAccess and nav icons.
library;

import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_ledger.dart' as evolve_ledger;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
import 'package:evolve/perc/services/perc_wallet_store.dart' as evolve_store;
import 'package:flutter_test/flutter_test.dart';
import 'package:perccent_wallet/perc/providers/perc_wallet_provider.dart'
    as perc_wallet;
import 'package:perccent_wallet/perc/services/perc_ledger.dart' as perc_ledger;
import 'package:perccent_wallet/perc/services/perc_ledger_hub.dart' as perc_hub;
import 'package:perccent_wallet/perc/services/perc_network_coordinator.dart'
    as perc_coord;
import 'package:perccent_wallet/perc/services/perc_wallet_store.dart'
    as perc_store;
import 'package:restore_privacy_client/suite_account.dart';
import 'package:restore_privacy_client/suite_account_apply.dart';
import 'package:restore_privacy_client/suite_nav.dart';
import 'package:restore_privacy_client/suite_parts.dart';
import 'package:restore_privacy_client/suite_session_rehydrate.dart';

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
    // Production default is true — exercise expiry-on-boot path.
    perc_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
    evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
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
    perc_hub.PercLedgerHub.resetForTest();
    evolve_hub.PercLedgerHub.resetForTest();
    SuiteAccountBus.instance.lastUsername = null;
  });

  test('missing session stamps are not treated as expired', () {
    expect(
      suiteSessionStampsIncomplete(
        sessionUsername: 'alice',
        sessionStartedAt: null,
        sessionLastActivityAt: null,
      ),
      isTrue,
    );
    final ledger = evolve_ledger.PercLedger.empty();
    // Simulate incomplete stamp after seed import / legacy serialize.
    ledger.sessionUsername = 'alice';
    ledger.sessionStartedAt = null;
    ledger.sessionLastActivityAt = null;
    expect(ledger.isWalletSessionExpired(), isFalse);
  });

  test('suiteNavDestinations keeps Analysis/Voting only when hasAppAccess', () {
    const parts = SuitePartsState(
      walletInstalled: true,
      evolveInstalled: true,
      rpaiInstalled: true,
    );
    final full = suiteNavDestinations(parts, hasAppAccess: true);
    expect(full, contains(SuiteNavDest.analysis));
    expect(full, contains(SuiteNavDest.voting));
    expect(full, contains(SuiteNavDest.wallet));
    expect(suiteNavKeepsFamilyAccessIcons(
      evolveInstalled: true,
      hasAppAccess: true,
    ), isTrue);

    final reduced = suiteNavDestinations(parts, hasAppAccess: false);
    expect(reduced, isNot(contains(SuiteNavDest.analysis)));
    expect(reduced, isNot(contains(SuiteNavDest.voting)));
    expect(reduced, contains(SuiteNavDest.wallet));
    expect(suiteNavKeepsFamilyAccessIcons(
      evolveInstalled: true,
      hasAppAccess: false,
    ), isFalse);
  });

  test(
    'after Suite register, family wallet rehydrate keeps hasAppAccess (sessionTimeout on)',
    () async {
      const user = 'auto_login_user';
      const pass = 'password12345';

      await applySuiteAccountToWalletAndEvolve(
        username: user,
        password: pass,
        register: true,
        surfaces: surfaces,
        skipSeedOffer: true,
      );
      expect(SuiteAccountBus.instance.lastUsername, user);

      // Strip timestamps from disk snapshot to reproduce the production bug.
      final raw = Map<String, dynamic>.from(sharedJson);
      raw.remove('sessionStartedAt');
      raw.remove('sessionLastActivityAt');
      sharedJson
        ..clear()
        ..addAll(raw);
      expect(sharedJson['sessionUsername'], isNotNull);

      evolve_hub.PercLedgerHub.resetForTest();
      final family = evolve_wallet.PercWalletProvider(
        store: _SharedStoreEvolve(sharedJson),
      );
      await family.initialize();
      // Without the stamp fix, isWalletSessionExpired cleared the session.
      expect(
        family.hasAppAccess,
        isTrue,
        reason:
            'family boot must keep hasAppAccess after Suite register even when '
            'sessionStartedAt/LastActivityAt were missing on disk',
      );
      expect(family.loggedInUsername, user);

      final dests = suiteNavDestinations(
        const SuitePartsState(evolveInstalled: true, walletInstalled: true),
        hasAppAccess: family.hasAppAccess,
      );
      expect(dests, contains(SuiteNavDest.analysis));
      expect(dests, contains(SuiteNavDest.voting));
      expect(dests, contains(SuiteNavDest.wallet));
    },
  );

  test(
    'rehydrateSuiteFamilyWalletSession restores cold session from Suite username',
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

      // Wipe session fields on disk while keeping account.
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
      expect(family.loggedInUsername, user);
      expect(family.suiteSplashIdentityActive, isTrue);
      expect(family.suppressSecondaryAuthWall, isTrue);
      expect(
        suiteEvolveShowsLoginWall(
          suiteAccountRegistered: true,
          walletHasAppAccess: family.hasAppAccess,
        ),
        isFalse,
      );

      final dests = suiteNavDestinations(
        const SuitePartsState(evolveInstalled: true, walletInstalled: true),
        hasAppAccess: family.hasAppAccess,
      );
      expect(dests, contains(SuiteNavDest.analysis));
      expect(dests, contains(SuiteNavDest.voting));
    },
  );

  test('cold empty store stays without access icons', () async {
    evolve_hub.PercLedgerHub.resetForTest();
    final cold = evolve_wallet.PercWalletProvider(
      store: _SharedStoreEvolve(<String, dynamic>{}),
    );
    await cold.initialize();
    expect(cold.hasAppAccess, isFalse);
    final dests = suiteNavDestinations(
      const SuitePartsState(evolveInstalled: true, walletInstalled: true),
      hasAppAccess: cold.hasAppAccess,
    );
    expect(dests, isNot(contains(SuiteNavDest.analysis)));
    expect(dests, isNot(contains(SuiteNavDest.voting)));
    expect(dests, contains(SuiteNavDest.wallet));
  });
}
