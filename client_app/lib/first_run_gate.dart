/// First-run ordered gates: Suite account → 12-word seed → licence → shell.
///
/// Residual device permissions (VPN / Packet Tunnel) and Connect must not run
/// until [firstRunComplete]. Connect still requires trial or KEYGEN after entry.
library;

import 'settings_store.dart';

/// Durable flag: user finished seed export/confirm (or restore) on this install.
const String kKeyFirstRunSeedDone = 'first_run_seed_done';

/// User-facing portal titles (Evolve-style Suite account).
const String kFirstRunAccountTitle = 'Create your Restore Privacy Suite account';
const String kFirstRunAccountBody =
    'Set a username and password once for your Suite identity. This is the only '
    'sign-in — Perccent wallet (%) and Evolve use the same account on this '
    'device with no second login. Credentials stay on your device — they are '
    'not uploaded to residual nodes.';
const String kFirstRunSeedTitle = 'Backup: 12-word recovery phrase';
const String kFirstRunSeedBody =
    'Write these 12 words offline (paper). They restore your Suite account, '
    '% wallet, and Evolve identity on a new install. Never share them. '
    'Do not skip if you want recovery later.';
const String kFirstRunSeedConfirmLabel = 'I wrote the words down — continue';
const String kFirstRunLicenceStepTitle = 'Accept end-user licence';
const String kFirstRunCompleteHint =
    'You can use the Suite. Residual Connect: free 3-day (72-hour) trial on '
    'this device (no card). After the trial ends, a paid KEYGEN / active '
    'subscription is required.';

enum FirstRunStep {
  account,
  seed,
  licence,
  complete,
}

/// Snapshot of first-run progress (pure / testable).
class FirstRunState {
  const FirstRunState({
    required this.accountDone,
    required this.seedDone,
    required this.licenceAccepted,
  });

  final bool accountDone;
  final bool seedDone;
  final bool licenceAccepted;

  FirstRunState copyWith({
    bool? accountDone,
    bool? seedDone,
    bool? licenceAccepted,
  }) =>
      FirstRunState(
        accountDone: accountDone ?? this.accountDone,
        seedDone: seedDone ?? this.seedDone,
        licenceAccepted: licenceAccepted ?? this.licenceAccepted,
      );
}

/// True when all first-run gates are satisfied.
bool firstRunComplete(FirstRunState s) =>
    s.accountDone && s.seedDone && s.licenceAccepted;

/// Next incomplete step (account → seed → licence → complete).
FirstRunStep nextFirstRunStep(FirstRunState s) {
  if (!s.accountDone) return FirstRunStep.account;
  if (!s.seedDone) return FirstRunStep.seed;
  if (!s.licenceAccepted) return FirstRunStep.licence;
  return FirstRunStep.complete;
}

/// Shell (tabs) is allowed only after first-run completes.
bool mayEnterSuiteShell({required bool firstRunDone}) => firstRunDone;

/// Residual permissions / tunnel prep must wait until first-run is done.
bool mayRequestResidualPermissions({required bool firstRunDone}) =>
    firstRunDone;

/// Residual Connect after first-run: trial active or paid KEYGEN OK.
bool mayResidualConnectAfterFirstRun({
  required bool firstRunDone,
  required bool trialOrKeygenOk,
}) =>
    firstRunDone && trialOrKeygenOk;

/// Durable first-run seed flag + account/licence sources.
class FirstRunStore {
  FirstRunStore({
    required this.backend,
    required this.isAccountRegistered,
    required this.hasAcceptedLicence,
  });

  final SettingsBackend backend;
  final Future<bool> Function() isAccountRegistered;
  final Future<bool> Function() hasAcceptedLicence;

  Future<bool> isSeedDone() async =>
      (await backend.getBool(kKeyFirstRunSeedDone)) == true;

  Future<void> markSeedDone() async {
    await backend.setBool(kKeyFirstRunSeedDone, true);
  }

  Future<FirstRunState> load() async {
    final account = await isAccountRegistered();
    final seed = await isSeedDone();
    final lic = await hasAcceptedLicence();
    return FirstRunState(
      accountDone: account,
      seedDone: seed,
      licenceAccepted: lic,
    );
  }

  Future<bool> isComplete() async => firstRunComplete(await load());
}
