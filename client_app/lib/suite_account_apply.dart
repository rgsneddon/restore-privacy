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

import 'suite_account.dart';

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
Future<void> applySuiteAccountToWalletAndEvolve({
  required String username,
  required String password,
  required bool register,
  SuiteAccountAuthRunner? runner,
  SuiteAccountPackageSurfaces? surfaces,
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
  try {
    final perc = s.createPercProvider();
    await perc.initialize();
    await authWalletSurface(
      login: perc.login,
      register: perc.register,
      completeSeed: perc.completeRegistrationSeedSetup,
      isLoggedIn: () => perc.isLoggedIn,
      loggedInUsername: () => perc.loggedInUsername,
      lastError: () => perc.errorMessage,
      username: u,
      password: p,
      preferRegister: register,
      surfaceLabel: 'Perccent wallet',
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
        isLoggedIn: () => evolve.isLoggedIn,
        loggedInUsername: () => evolve.loggedInUsername,
        lastError: () => evolve.errorMessage,
        username: u,
        password: p,
        // Account should already exist on the shared ledger after Perccent apply.
        preferRegister: false,
        surfaceLabel: 'Evolve analyser',
      );
    }
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
    SuiteAccountBus.instance.notifyRegistered(u);
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
}) async {
  if (isLoggedIn()) {
    final cur = (loggedInUsername() ?? '').trim();
    if (cur == username) return;
  }
  if (preferRegister) {
    await register(username, password);
    // Completes deferred seed setup when register left pending (default
    // sessionTimeoutEnabled=true). No-op if register already completed.
    await completeSeed(enableSeed: false);
    if (!isLoggedIn() || (loggedInUsername() ?? '').trim() != username) {
      // Username may already exist (swallowed "already taken") — try login.
      await login(username, password);
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
