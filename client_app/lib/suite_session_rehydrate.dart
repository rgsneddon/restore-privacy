/// Rehydrate Suite family wallet session after unified first-run account create.
///
/// Product bug: main-bar icons (Analysis/Voting) flash then collapse because
/// family boot published `hasAppAccess=false` after a just-created session was
/// cleared as "expired" (missing session stamps) or not re-applied from disk.
library;

import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_auth.dart' as evolve_auth;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;

import 'suite_account.dart';

/// Pure: whether nav should keep Analysis/Voting for a rehydrated Suite user.
bool suiteNavKeepsFamilyAccessIcons({
  required bool evolveInstalled,
  required bool hasAppAccess,
}) {
  if (!evolveInstalled) return false;
  return hasAppAccess;
}

/// Pure: incomplete session stamps must not count as expired.
bool suiteSessionStampsIncomplete({
  required String? sessionUsername,
  required DateTime? sessionStartedAt,
  required DateTime? sessionLastActivityAt,
}) {
  if (sessionUsername == null || sessionUsername.trim().isEmpty) return false;
  return sessionStartedAt == null || sessionLastActivityAt == null;
}

/// After hub reload: if Suite registered username has an address on the ledger
/// but session is cold, restore local session (same trust as persisted login).
///
/// Returns true when [wallet] ends with [hasAppAccess].
Future<bool> rehydrateSuiteFamilyWalletSession({
  required evolve_wallet.PercWalletProvider wallet,
  String? preferredUsername,
}) async {
  try {
    await evolve_hub.PercLedgerHub.instance.reloadFromStore();
  } catch (_) {}

  if (wallet.hasAppAccess) return true;

  final busUser = (SuiteAccountBus.instance.lastUsername ?? '').trim();
  final preferred = (preferredUsername ?? '').trim();
  final candidates = <String>[
    if (preferred.isNotEmpty) preferred,
    if (busUser.isNotEmpty) busUser,
  ];

  final ledger = evolve_hub.PercLedgerHub.instance.ledger;
  String? restoreUser;
  for (final raw in candidates) {
    final u = evolve_auth.PercAuth.normalizeUsername(raw);
    final acc = ledger.account(u);
    if (acc != null && acc.address.isNotEmpty) {
      restoreUser = u;
      break;
    }
  }
  // Fall back: any non-treasury account with address (single-user install).
  if (restoreUser == null) {
    for (final e in ledger.accounts.entries) {
      if (e.key == 'treasury' || e.key.startsWith('treasury')) continue;
      if (e.value.address.isNotEmpty) {
        restoreUser = e.key;
        break;
      }
    }
  }
  if (restoreUser == null) return wallet.hasAppAccess;

  final t = DateTime.now().toUtc();
  ledger.sessionUsername = restoreUser;
  ledger.sessionStartedAt ??= t;
  ledger.sessionLastActivityAt = t;
  try {
    // Hub notifyListeners → wallet _onHubLedgerChanged → hasAppAccess updates.
    await evolve_hub.PercLedgerHub.instance.persistLocal();
  } catch (_) {
    evolve_hub.PercLedgerHub.instance.notifyListeners();
  }
  return wallet.hasAppAccess;
}
