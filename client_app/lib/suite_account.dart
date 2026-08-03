/// Shared optional Suite account for Perccent wallet + Evolve analyser.
///
/// Independent of VPN licence / keygen: [LicenceGate.mayConnect] must never
/// consult this store. One registration (or login) is recorded so both % and
/// EVOLVE tabs can hydrate from the shared Perc ledger without a second full
/// register wall during VPN setup.
library;

import 'package:flutter/widgets.dart';

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

/// Pure: whether a Suite account (username/password) prompt should appear.
///
/// **Product path (dedicated residual VPN):** always `false`. Username/password
/// and Suite identity prompts are not offered after KEYGEN/trial unlock.
/// Args are retained so call sites compile; they are intentionally ignored.
bool shouldOfferSuiteAccountPrompt({
  required bool vpnUnlocked,
  required bool deferred,
  required bool registered,
}) {
  // Dedicated VPN product — never offer Suite account register/sign-in.
  final _ = (vpnUnlocked, deferred, registered);
  return false;
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

/// Pure: Suite splash identity is live for family surfaces (banner / inherit).
///
/// After first-run account create/login, secondary Evolve/% walls are not
/// required — [walletHasAppAccess] is restored via rehydrate, not a second form.
bool suiteEvolveInheritsSuiteLogin({
  required bool suiteAccountRegistered,
  required bool walletHasAppAccess,
}) =>
    suiteAccountRegistered && walletHasAppAccess;

/// Pure: whether Evolve/% may show a **secondary** create-account or login form.
///
/// Splash / first-run is the only identity gate. Once Suite is registered (or
/// the wallet session is already live), family surfaces must not present a
/// second auth wall.
bool suiteEvolveShowsLoginWall({
  required bool suiteAccountRegistered,
  required bool walletHasAppAccess,
}) {
  if (walletHasAppAccess) return false;
  if (suiteAccountRegistered) return false;
  return true;
}

/// Pure: secondary family auth is required only when splash Suite identity is
/// absent and the wallet session is cold.
bool suiteFamilySecondaryAuthRequired({
  required bool suiteAccountRegistered,
  required bool walletHasAppAccess,
}) =>
    suiteEvolveShowsLoginWall(
      suiteAccountRegistered: suiteAccountRegistered,
      walletHasAppAccess: walletHasAppAccess,
    );

/// Pure: after Suite step-1 registration, auth UI must prefer sign-in over create
/// (standalone Evolve only — Suite embed suppresses the wall entirely).
bool suiteEvolvePrefersLoginNotRegister({
  required bool suiteAccountRegistered,
  required bool hasNonTreasuryAccounts,
}) =>
    suiteAccountRegistered || hasNonTreasuryAccounts;

/// Suite embed identity: first-run/splash account already done on this install.
///
/// When [suiteAccountRegistered] is true, Evolve/% [WalletScreen] / loading
/// auth panels must not force a second create/login form.
class SuiteSplashIdentityScope extends InheritedWidget {
  const SuiteSplashIdentityScope({
    super.key,
    required this.suiteAccountRegistered,
    this.username,
    required super.child,
  });

  final bool suiteAccountRegistered;
  final String? username;

  static SuiteSplashIdentityScope? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<SuiteSplashIdentityScope>();

  /// True when secondary Evolve/% auth wall must not be shown.
  bool get suppressSecondaryAuthWall => suiteAccountRegistered;

  @override
  bool updateShouldNotify(covariant SuiteSplashIdentityScope oldWidget) =>
      suiteAccountRegistered != oldWidget.suiteAccountRegistered ||
      username != oldWidget.username;
}

/// Result of the optional post-keygen Suite account sheet.
enum SuiteAccountPromptOutcome {
  deferred,
  registered,
  signedIn,
  dismissed,
}
