/// Apply one Suite username/password to Perccent wallet and Evolve ledger hubs.
///
/// Both packages share the same on-disk ledger filename under the Suite app
/// support directory. Registering once via Perccent, then loading/login on
/// Evolve, yields a single identity for both tabs.
library;

import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
import 'package:perccent_wallet/perc/providers/perc_wallet_provider.dart'
    as perc_wallet;
import 'package:perccent_wallet/perc/services/perc_ledger_hub.dart' as perc_hub;
import 'package:perccent_wallet/perc/services/perc_network_coordinator.dart'
    as perc_coord;

import 'settings_store.dart';
import 'suite_account.dart';
import 'suite_account_seed.dart';

/// Optional full-path override (legacy/tests that fully replace the apply body).
typedef SuiteAccountAuthRunner = Future<void> Function({
  required String username,
  required String password,
  required bool register,
});

/// Injectable package surfaces so tests can drive **real** providers with memory stores.
class SuiteAccountPackageSurfaces {
  const SuiteAccountPackageSurfaces({
    required this.createPercProvider,
    required this.createEvolveProvider,
    required this.reloadEvolveHub,
    required this.persistPercHub,
  });

  final perc_wallet.PercWalletProvider Function() createPercProvider;
  final evolve_wallet.PercWalletProvider Function() createEvolveProvider;
  final Future<void> Function() reloadEvolveHub;
  final Future<void> Function() persistPercHub;
}

/// Production surfaces (default file stores + package hubs).
SuiteAccountPackageSurfaces productionSuiteAccountSurfaces() {
  return SuiteAccountPackageSurfaces(
    createPercProvider: perc_wallet.PercWalletProvider.new,
    createEvolveProvider: evolve_wallet.PercWalletProvider.new,
    reloadEvolveHub: () => evolve_hub.PercLedgerHub.instance.reloadFromStore(),
    persistPercHub: () => perc_hub.PercLedgerHub.instance.persistLocal(),
  );
}

/// Production runner: register-or-login on Perccent, then hydrate Evolve.
///
/// Throws [StateError] if either package is not logged in with [username]
/// after apply — callers must not mark the Suite account registered on failure.
///
/// On first [register], [seedOffer] (when provided) presents the recovery seed
/// export opportunity before registration is finalized. Skip remains allowed.
Future<void> applySuiteAccountToWalletAndEvolve({
  required String username,
  required String password,
  required bool register,
  SuiteAccountAuthRunner? runner,
  SuiteAccountPackageSurfaces? surfaces,
  SuiteSeedOfferFn? seedOffer,
  bool skipSeedOffer = false,
  SettingsBackend? suitePrefsBackend,
  SettingsBackend? licenceBackend,
}) async {
  final u = username.trim();
  final p = password;
  if (u.isEmpty) {
    throw StateError('Username is required');
  }
  if (p.length < 8) {
    throw StateError('Password must be at least 8 characters');
  }
  if (runner != null) {
    await runner(username: u, password: p, register: register);
    SuiteAccountBus.instance.notifyRegistered(u);
    return;
  }

  final s = surfaces ?? productionSuiteAccountSurfaces();
  final prevPercLive = perc_coord.PercNetworkCoordinator.disableLiveNodesForTests;
  final prevEvolveLive =
      evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests;
  // Force offline-honest registration during Suite apply so a transient seed
  // network blip cannot leave a half-account that rejects later logins.
  // Live nodes remain disabled only for this apply window.
  perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
  evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
  List<String>? enabledSeedWords;
  try {
    final perc = s.createPercProvider();
    await perc.initialize();
    // Ensure local treasury exists so register can mint a password-verifiable account.
    if (perc.needsTreasuryPassword) {
      await perc.setupTreasuryPassword(p);
      await perc.logout();
    }
    await authWalletSurface(
      login: perc.login,
      register: perc.register,
      completeSeed: perc.completeRegistrationSeedSetup,
      generateSeed: perc.generateRegistrationSeed,
      isPendingSeed: () => perc.pendingSeedSetup,
      isLoggedIn: () => perc.isLoggedIn,
      loggedInUsername: () => perc.loggedInUsername,
      lastError: () => perc.errorMessage,
      attachSeed: perc.refreshSeedRecoveryEnvelope,
      username: u,
      password: p,
      preferRegister: register,
      surfaceLabel: 'Perccent wallet',
      seedOffer: seedOffer,
      skipSeedOffer: skipSeedOffer,
      onSeedEnabled: (words) => enabledSeedWords = words,
    );
    await s.persistPercHub();

    final evolve = s.createEvolveProvider();
    await evolve.initialize();
    await s.reloadEvolveHub();
    if (!evolve.isLoggedIn ||
        (evolve.loggedInUsername ?? '').trim() != u) {
      await authWalletSurface(
        login: evolve.login,
        register: evolve.register,
        completeSeed: evolve.completeRegistrationSeedSetup,
        generateSeed: evolve.generateRegistrationSeed,
        isPendingSeed: () => evolve.pendingSeedSetup,
        isLoggedIn: () => evolve.isLoggedIn,
        loggedInUsername: () => evolve.loggedInUsername,
        lastError: () => evolve.errorMessage,
        username: u,
        password: p,
        // Account should already exist on the shared ledger after Perccent apply.
        preferRegister: false,
        surfaceLabel: 'Evolve analyser',
        skipSeedOffer: true,
      );
    }
    await evolve_hub.PercLedgerHub.instance.persistLocal();
    requireWalletSurfaceLoggedIn(
      surfaceLabel: 'Perccent wallet',
      isLoggedIn: perc.isLoggedIn,
      loggedInUsername: perc.loggedInUsername,
      username: u,
      lastError: perc.errorMessage,
    );
    requireWalletSurfaceLoggedIn(
      surfaceLabel: 'Evolve analyser',
      isLoggedIn: evolve.isLoggedIn,
      loggedInUsername: evolve.loggedInUsername,
      username: u,
      lastError: evolve.errorMessage,
    );

    // Seed export: publish envelope for clean-install words-only restore.
    // Live nodes are restored in finally *before* publish so rendezvous is not no-op'd.
    final words = enabledSeedWords;
    final env = (words != null && words.isNotEmpty)
        ? (suiteSeedEnvelopeB64FromPerc(perc) ??
            suiteSeedEnvelopeB64FromWallet(evolve))
        : null;

    SuiteAccountBus.instance.notifyRegistered(u);

    // Ensure session is on disk before bus listeners rehydrate Evolve family host.
    try {
      await s.persistPercHub();
      await evolve_hub.PercLedgerHub.instance.persistLocal();
    } catch (_) {}

    // Restore live-node flags, then publish seed envelope (network + inject store).
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = prevPercLive;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests =
        prevEvolveLive;
    if (words != null &&
        words.isNotEmpty &&
        env != null &&
        env.isNotEmpty) {
      await publishSuiteSeedAfterExport(
        words: words,
        username: u,
        envelopeB64: env,
        suitePrefsBackend: suitePrefsBackend,
        licenceBackend: licenceBackend,
      );
    }
  } finally {
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = prevPercLive;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests =
        prevEvolveLive;
  }
}

/// Authenticates one wallet surface and **requires** a logged-in session.
///
/// [PercWalletProvider.login]/[register] often swallow errors into
/// [errorMessage] without throwing — so we always re-check [isLoggedIn].
Future<void> authWalletSurface({
  required Future<void> Function(String, String) login,
  required Future<void> Function(String, String) register,
  required Future<void> Function({required bool enableSeed}) completeSeed,
  required bool Function() isLoggedIn,
  required String? Function() loggedInUsername,
  required String? Function() lastError,
  required String username,
  required String password,
  required bool preferRegister,
  required String surfaceLabel,
  Future<List<String>> Function()? generateSeed,
  bool Function()? isPendingSeed,
  /// Attach recovery envelope after a durable offline register (no network).
  Future<void> Function(List<String> words)? attachSeed,
  SuiteSeedOfferFn? seedOffer,
  bool skipSeedOffer = false,
  void Function(List<String> words)? onSeedEnabled,
}) async {
  if (isLoggedIn()) {
    final cur = (loggedInUsername() ?? '').trim();
    if (cur == username) return;
  }
  if (preferRegister) {
    await register(username, password);
    final pending = isPendingSeed?.call() ?? false;
    List<String>? seedWords;
    if (pending) {
      if (!skipSeedOffer && seedOffer != null && generateSeed != null) {
        final offer = await seedOffer(generateSeed);
        if (offer.enableSeed) {
          final words = offer.words;
          if (words == null || words.isEmpty) {
            throw StateError('Seed export requires generated words');
          }
          seedWords = List<String>.from(words);
          onSeedEnabled?.call(seedWords);
        }
      }
      // Always finalize offline first (enableSeed:true path can hang on seed
      // network publish). Attach the recovery envelope after login succeeds.
      await completeSeed(enableSeed: false);
    } else {
      // sessionTimeoutEnabled=false path auto-completed with enableSeed:false.
      await completeSeed(enableSeed: false);
    }
    if (!isLoggedIn() || (loggedInUsername() ?? '').trim() != username) {
      // Username may already exist (swallowed "already taken") — try login.
      await login(username, password);
    }
    if (seedWords != null &&
        seedWords.isNotEmpty &&
        isLoggedIn() &&
        attachSeed != null) {
      await attachSeed(seedWords);
    }
  } else {
    await login(username, password);
  }
  requireWalletSurfaceLoggedIn(
    surfaceLabel: surfaceLabel,
    isLoggedIn: isLoggedIn(),
    loggedInUsername: loggedInUsername(),
    username: username,
    lastError: lastError(),
  );
}

/// Pure assertion used by apply + unit tests.
void requireWalletSurfaceLoggedIn({
  required String surfaceLabel,
  required bool isLoggedIn,
  required String? loggedInUsername,
  required String username,
  required String? lastError,
}) {
  if (isLoggedIn && (loggedInUsername ?? '').trim() == username) {
    return;
  }
  final detail = (lastError ?? '').trim();
  throw StateError(
    detail.isEmpty
        ? '$surfaceLabel did not sign in as $username'
        : '$surfaceLabel did not sign in as $username ($detail)',
  );
}

/// After a Suite registration, reload in-memory hubs so open tabs drop auth walls.
Future<void> reloadSuiteAccountSessions() async {
  try {
    await perc_hub.PercLedgerHub.instance.reloadFromStore();
  } catch (_) {}
  try {
    await evolve_hub.PercLedgerHub.instance.reloadFromStore();
  } catch (_) {}
  SuiteAccountBus.instance.notifyRegistered(
    SuiteAccountBus.instance.lastUsername ?? '',
  );
}
