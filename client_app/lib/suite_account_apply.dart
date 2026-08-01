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

/// Optional hooks for tests (inject memory providers / skip network).
typedef SuiteAccountAuthRunner = Future<void> Function({
  required String username,
  required String password,
  required bool register,
});

/// Production runner: register-or-login on Perccent, then hydrate Evolve.
Future<void> applySuiteAccountToWalletAndEvolve({
  required String username,
  required String password,
  required bool register,
  SuiteAccountAuthRunner? runner,
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

  // Keep boot responsive if seed is offline (same pattern as package boot).
  final prevPercLive = perc_coord.PercNetworkCoordinator.disableLiveNodesForTests;
  final prevEvolveLive =
      evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests;
  try {
    // Prefer live nodes in production; tests set disableLiveNodesForTests=true.
    final perc = perc_wallet.PercWalletProvider();
    await perc.initialize();
    await _authOne(
      login: perc.login,
      register: perc.register,
      completeSeed: perc.completeRegistrationSeedSetup,
      isLoggedIn: () => perc.isLoggedIn,
      loggedInUsername: () => perc.loggedInUsername,
      username: u,
      password: p,
      preferRegister: register,
    );
    // Persist is handled inside login/register; force disk read for Evolve hub.
    await perc_hub.PercLedgerHub.instance.persistLocal();

    final evolve = evolve_wallet.PercWalletProvider();
    await evolve.initialize();
    await evolve_hub.PercLedgerHub.instance.reloadFromStore();
    if (!evolve.isLoggedIn) {
      await _authOne(
        login: evolve.login,
        register: evolve.register,
        completeSeed: evolve.completeRegistrationSeedSetup,
        isLoggedIn: () => evolve.isLoggedIn,
        loggedInUsername: () => evolve.loggedInUsername,
        username: u,
        password: p,
        preferRegister: false, // account should already exist on shared ledger
      );
    }
    SuiteAccountBus.instance.notifyRegistered(u);
  } finally {
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = prevPercLive;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests =
        prevEvolveLive;
  }
}

Future<void> _authOne({
  required Future<void> Function(String, String) login,
  required Future<void> Function(String, String) register,
  required Future<void> Function({required bool enableSeed}) completeSeed,
  required bool Function() isLoggedIn,
  required String? Function() loggedInUsername,
  required String username,
  required String password,
  required bool preferRegister,
}) async {
  if (isLoggedIn()) {
    final cur = (loggedInUsername() ?? '').trim();
    if (cur == username) return;
  }
  if (preferRegister) {
    try {
      await register(username, password);
      await completeSeed(enableSeed: false);
      return;
    } catch (e) {
      final msg = e.toString().toLowerCase();
      if (msg.contains('already taken') || msg.contains('already registered')) {
        await login(username, password);
        return;
      }
      rethrow;
    }
  }
  await login(username, password);
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
