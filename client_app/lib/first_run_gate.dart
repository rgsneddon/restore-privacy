/// VPN-only first-use / return-visit entry policy (no username/password).
///
/// First use: licence (scroll-to-accept) → KEYGEN or continue trial → main VPN.
/// Return: entitlement check (trial remaining or KEYGEN) → main VPN.
/// Residual Connect still requires trial or KEYGEN after entry.
library;

import 'settings_store.dart';

/// Durable flag: first-use flow finished (licence accepted + unlocked once).
const String kKeyFirstRunVpnEntryDone = 'first_run_vpn_entry_done';

/// Legacy flags (ignored for product path; kept so old installs do not crash).
const String kKeyFirstRunSeedDone = 'first_run_seed_done';

const String kFirstRunLicenceStepTitle = 'Accept end-user licence';
const String kFirstRunCompleteHint =
    'You can use Restore Privacy residual VPN. Residual Connect: free 3-day '
    '(72-hour) trial on this device (no card). After the trial ends, a paid '
    'KEYGEN / active subscription is required.';

const String kFirstRunKeygenStepTitle = 'Enter KEYGEN or continue trial';
const String kFirstRunKeygenStepBody =
    'Paste the KEYGEN from your fulfilment email (RPT-KEY-…), or continue the '
    'free 3-day residual trial if it is still active on this device.';

const String kContinueTrialButtonLabel = 'Click to continue trial';
const String kContinueTrialExpiredHint =
    'Your free 3-day trial has ended. Enter a valid KEYGEN to continue.';

/// Product first-use / return steps (no account or seed).
enum FirstRunStep {
  licence,
  keygenOrTrial,
  complete,
}

/// Snapshot of first-use progress (pure / testable).
class FirstRunState {
  const FirstRunState({
    required this.licenceAccepted,
    this.entryUnlockDone = false,
  });

  final bool licenceAccepted;

  /// User finished first-use unlock path at least once (trial or KEYGEN).
  final bool entryUnlockDone;

  FirstRunState copyWith({
    bool? licenceAccepted,
    bool? entryUnlockDone,
  }) =>
      FirstRunState(
        licenceAccepted: licenceAccepted ?? this.licenceAccepted,
        entryUnlockDone: entryUnlockDone ?? this.entryUnlockDone,
      );
}

/// First-use complete when licence accepted and entry unlock done once.
bool firstRunComplete(FirstRunState s) =>
    s.licenceAccepted && s.entryUnlockDone;

/// Next incomplete first-use step.
FirstRunStep nextFirstRunStep(FirstRunState s) {
  if (!s.licenceAccepted) return FirstRunStep.licence;
  if (!s.entryUnlockDone) return FirstRunStep.keygenOrTrial;
  return FirstRunStep.complete;
}

/// Shell (main VPN) allowed after first-use complete **and** residual entitled.
bool mayEnterVpnShell({
  required bool firstRunDone,
  required bool trialOrKeygenOk,
}) =>
    firstRunDone && trialOrKeygenOk;

/// Alias used by older call sites (VPN shell, not multi-product Suite).
bool mayEnterSuiteShell({
  required bool firstRunDone,
  bool trialOrKeygenOk = true,
}) =>
    firstRunDone && trialOrKeygenOk;

/// Residual permissions / tunnel prep after first-use licence+unlock.
bool mayRequestResidualPermissions({required bool firstRunDone}) =>
    firstRunDone;

/// Residual Connect: first-use done and trial or paid KEYGEN OK.
bool mayResidualConnectAfterFirstRun({
  required bool firstRunDone,
  required bool trialOrKeygenOk,
}) =>
    firstRunDone && trialOrKeygenOk;

/// Pure: may skip KEYGEN when trial is still active.
bool mayContinueTrialInsteadOfKeygen({required bool trialActive}) =>
    trialActive;

/// Pure: after licence, require KEYGEN when trial expired / inactive.
bool mustEnterKeygen({
  required bool licenceAccepted,
  required bool trialActive,
  required bool keygenOk,
}) {
  if (!licenceAccepted) return false;
  if (keygenOk) return false;
  return !trialActive;
}

/// Pure: return-visit entry may open VPN shell.
bool mayEnterVpnShellOnReturn({
  required bool licenceAccepted,
  required bool trialActive,
  required bool keygenOk,
}) {
  if (!licenceAccepted) return false;
  return trialActive || keygenOk;
}

/// Durable first-use store (licence + entry unlock flag).
class FirstRunStore {
  FirstRunStore({
    required this.backend,
    required this.hasAcceptedLicence,
    /// Legacy Suite account hook — ignored (no username/password gate).
    Future<bool> Function()? isAccountRegistered,
  });

  final SettingsBackend backend;
  final Future<bool> Function() hasAcceptedLicence;

  Future<bool> isSeedDone() async =>
      (await backend.getBool(kKeyFirstRunSeedDone)) == true;

  Future<void> markSeedDone() async {
    // No-op product path — seed gate removed.
    await backend.setBool(kKeyFirstRunSeedDone, true);
  }

  Future<bool> isEntryUnlockDone() async =>
      (await backend.getBool(kKeyFirstRunVpnEntryDone)) == true;

  Future<void> markEntryUnlockDone() async {
    await backend.setBool(kKeyFirstRunVpnEntryDone, true);
  }

  Future<FirstRunState> load() async {
    final lic = await hasAcceptedLicence();
    final unlock = await isEntryUnlockDone();
    return FirstRunState(
      licenceAccepted: lic,
      entryUnlockDone: unlock,
    );
  }

  Future<bool> isComplete() async => firstRunComplete(await load());
}
