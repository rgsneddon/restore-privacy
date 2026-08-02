/// Shared optional Suite account for Perccent wallet + Evolve analyser.
///
/// Independent of VPN licence / keygen: [LicenceGate.mayConnect] must never
/// consult this store. One registration (or login) is recorded so both % and
/// EVOLVE tabs can hydrate from the shared Perc ledger without a second full
/// register wall during VPN setup.
library;

import 'settings_store.dart';

const String kKeySuiteAccountDeferred = 'suite_account_prompt_deferred';
const String kKeySuiteAccountRegistered = 'suite_account_registered';
const String kKeySuiteAccountUsername = 'suite_account_username';

const String kSuiteAccountPromptTitle = 'Register for % wallet & Evolve?';
const String kSuiteAccountPromptBody =
    'Optionally create one account for Perccent wallet and Evolve analyser. '
    'VPN Connect already works with your KEYGEN — this is not required for residual protection.';
const String kSuiteAccountDeferLabel = 'Not now — use VPN only';
const String kSuiteAccountRegisterLabel = 'Create account';
const String kSuiteAccountLoginLabel = 'Sign in';
const String kSuiteAccountUsernameLabel = 'Username';
const String kSuiteAccountPasswordLabel = 'Password';

/// Pure: whether the post-keygen Suite account prompt should appear.
bool shouldOfferSuiteAccountPrompt({
  required bool vpnUnlocked,
  required bool deferred,
  required bool registered,
}) {
  if (!vpnUnlocked) return false;
  if (registered) return false;
  if (deferred) return false;
  return true;
}

/// Pure: VPN Connect eligibility is never gated on Suite account state.
bool suiteAccountBlocksVpnConnect({
  required bool licenceMayConnect,
  required bool suiteRegistered,
  required bool suiteDeferred,
}) {
  // Suite account flags are intentionally ignored for VPN Connect.
  assert(suiteRegistered || !suiteRegistered);
  assert(suiteDeferred || !suiteDeferred);
  return !licenceMayConnect;
}

/// Durable Suite-account flags (SharedPreferences / memory backend).
class SuiteAccountStore {
  SuiteAccountStore(this.backend);

  final SettingsBackend backend;

  Future<bool> isDeferred() async =>
      (await backend.getBool(kKeySuiteAccountDeferred)) == true;

  Future<bool> isRegistered() async =>
      (await backend.getBool(kKeySuiteAccountRegistered)) == true;

  Future<String?> username() async {
    final u = await backend.getString(kKeySuiteAccountUsername);
    if (u == null || u.trim().isEmpty) return null;
    return u.trim();
  }

  Future<void> markDeferred() async {
    await backend.setBool(kKeySuiteAccountDeferred, true);
  }

  Future<void> markRegistered(String username) async {
    final u = username.trim();
    await backend.setBool(kKeySuiteAccountRegistered, true);
    await backend.setBool(kKeySuiteAccountDeferred, false);
    if (u.isNotEmpty) {
      await backend.setString(kKeySuiteAccountUsername, u);
    }
  }

  Future<void> clearForTest() async {
    await backend.setBool(kKeySuiteAccountDeferred, false);
    await backend.setBool(kKeySuiteAccountRegistered, false);
    await backend.setString(kKeySuiteAccountUsername, '');
  }
}

/// In-process bus so % / EVOLVE tabs can reload the shared ledger after one
/// Suite registration without each forcing its own register wall.
class SuiteAccountBus {
  SuiteAccountBus._();
  static final SuiteAccountBus instance = SuiteAccountBus._();

  final List<void Function()> _listeners = <void Function()>[];
  String? lastUsername;

  void addListener(void Function() listener) {
    _listeners.add(listener);
  }

  void removeListener(void Function() listener) {
    _listeners.remove(listener);
  }

  void notifyRegistered(String username) {
    lastUsername = username.trim();
    for (final l in List<void Function()>.from(_listeners)) {
      l();
    }
  }

  /// True when first-run / apply already established a Suite identity this process.
  bool get hasRegisteredSession {
    final u = (lastUsername ?? '').trim();
    return u.isNotEmpty;
  }
}

/// Pure: Evolve/% must not force a full create-account wall when Suite already
/// registered **and** the shared wallet session is live on this install.
bool suiteEvolveInheritsSuiteLogin({
  required bool suiteAccountRegistered,
  required bool walletHasAppAccess,
}) =>
    suiteAccountRegistered && walletHasAppAccess;

/// Pure: whether Evolve should still show an auth surface.
bool suiteEvolveShowsLoginWall({
  required bool suiteAccountRegistered,
  required bool walletHasAppAccess,
}) {
  if (walletHasAppAccess) return false;
  return true;
}

/// Result of the optional post-keygen Suite account sheet.
enum SuiteAccountPromptOutcome {
  deferred,
  registered,
  signedIn,
  dismissed,
}
