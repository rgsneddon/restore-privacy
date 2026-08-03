import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/first_run_gate.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/settings_store.dart';

void main() {
  test('first-use order is licence → keygenOrTrial → complete', () {
    var s = const FirstRunState(
      licenceAccepted: false,
      entryUnlockDone: false,
    );
    expect(nextFirstRunStep(s), FirstRunStep.licence);
    expect(firstRunComplete(s), isFalse);
    expect(
      mayEnterVpnShell(firstRunDone: false, trialOrKeygenOk: true),
      isFalse,
    );
    expect(mayRequestResidualPermissions(firstRunDone: false), isFalse);

    s = s.copyWith(licenceAccepted: true);
    expect(nextFirstRunStep(s), FirstRunStep.keygenOrTrial);
    expect(firstRunComplete(s), isFalse);
    expect(
      mayEnterVpnShell(firstRunDone: firstRunComplete(s), trialOrKeygenOk: true),
      isFalse,
    );

    s = s.copyWith(entryUnlockDone: true);
    expect(nextFirstRunStep(s), FirstRunStep.complete);
    expect(firstRunComplete(s), isTrue);
    expect(
      mayEnterVpnShell(firstRunDone: true, trialOrKeygenOk: true),
      isTrue,
    );
    expect(mayRequestResidualPermissions(firstRunDone: true), isTrue);
  });

  test('licence alone is not first-run complete', () {
    const s = FirstRunState(
      licenceAccepted: true,
      entryUnlockDone: false,
    );
    expect(nextFirstRunStep(s), FirstRunStep.keygenOrTrial);
    expect(firstRunComplete(s), isFalse);
  });

  test('return visit: trial or KEYGEN required for shell', () {
    expect(
      mayEnterVpnShellOnReturn(
        licenceAccepted: true,
        trialActive: true,
        keygenOk: false,
      ),
      isTrue,
    );
    expect(
      mayEnterVpnShellOnReturn(
        licenceAccepted: true,
        trialActive: false,
        keygenOk: true,
      ),
      isTrue,
    );
    expect(
      mayEnterVpnShellOnReturn(
        licenceAccepted: true,
        trialActive: false,
        keygenOk: false,
      ),
      isFalse,
    );
    expect(
      mayEnterVpnShellOnReturn(
        licenceAccepted: false,
        trialActive: true,
        keygenOk: false,
      ),
      isFalse,
    );
  });

  test('mustEnterKeygen when trial inactive and no KEYGEN', () {
    expect(
      mustEnterKeygen(
        licenceAccepted: true,
        trialActive: false,
        keygenOk: false,
      ),
      isTrue,
    );
    expect(
      mustEnterKeygen(
        licenceAccepted: true,
        trialActive: true,
        keygenOk: false,
      ),
      isFalse,
    );
    expect(
      mayContinueTrialInsteadOfKeygen(trialActive: true),
      isTrue,
    );
    expect(
      mayContinueTrialInsteadOfKeygen(trialActive: false),
      isFalse,
    );
  });

  test('residual Connect needs first-run and trial/keygen', () {
    expect(
      mayResidualConnectAfterFirstRun(
        firstRunDone: true,
        trialOrKeygenOk: true,
      ),
      isTrue,
    );
    expect(
      mayResidualConnectAfterFirstRun(
        firstRunDone: true,
        trialOrKeygenOk: false,
      ),
      isFalse,
    );
    expect(
      mayResidualConnectAfterFirstRun(
        firstRunDone: false,
        trialOrKeygenOk: true,
      ),
      isFalse,
    );
  });

  test('FirstRunStore marks entry unlock and loads complete', () async {
    final b = MemorySettingsBackend();
    final gate = LicenceGate(
      PrefsLicenceBackend(
        (k) async => b.getBool(k),
        (k, v) async {
          await b.setBool(k, v);
        },
        (k) async => b.getString(k),
        (k, v) async {
          await b.setString(k, v);
        },
      ),
    );
    final store = FirstRunStore(
      backend: b,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );
    expect(await store.isComplete(), isFalse);
    await gate.acceptLicence();
    expect(nextFirstRunStep(await store.load()), FirstRunStep.keygenOrTrial);
    await store.markEntryUnlockDone();
    expect(await store.isComplete(), isTrue);
  });

  test('VPN-only first-run copy has no username/password path', () {
    expect(kFirstRunKeygenStepTitle.toLowerCase(), contains('keygen'));
    expect(kContinueTrialButtonLabel.toLowerCase(), contains('trial'));
    expect(kFirstRunLicenceStepTitle.toLowerCase(), contains('licence'));
    expect(kFirstRunCompleteHint.toLowerCase(), contains('residual'));
    expect(kFirstRunKeygenStepBody.toLowerCase(), isNot(contains('password')));
    expect(kFirstRunKeygenStepBody.toLowerCase(), isNot(contains('username')));
  });

  test('trial and keygen still compose Connect after first-run', () {
    expect(
      connectAllowedTrialOrPaid(keygenOk: false, trialOk: true),
      isTrue,
    );
    expect(
      mayResidualConnectAfterFirstRun(
        firstRunDone: true,
        trialOrKeygenOk: connectAllowedTrialOrPaid(
          keygenOk: false,
          trialOk: false,
        ),
      ),
      isFalse,
    );
  });

  test('mayEnterSuiteShell alias requires entitlement when passed', () {
    expect(mayEnterSuiteShell(firstRunDone: true), isTrue);
    expect(
      mayEnterSuiteShell(firstRunDone: true, trialOrKeygenOk: false),
      isFalse,
    );
  });
}
