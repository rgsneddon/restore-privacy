import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/first_run_gate.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_account.dart';

void main() {
  test('first-run order is account → seed → licence → complete', () {
    var s = const FirstRunState(
      accountDone: false,
      seedDone: false,
      licenceAccepted: false,
    );
    expect(nextFirstRunStep(s), FirstRunStep.account);
    expect(firstRunComplete(s), isFalse);
    expect(mayEnterSuiteShell(firstRunDone: false), isFalse);
    expect(mayRequestResidualPermissions(firstRunDone: false), isFalse);

    s = s.copyWith(accountDone: true);
    expect(nextFirstRunStep(s), FirstRunStep.seed);
    // Account alone still blocks shell and residual permission/tunnel prep.
    expect(firstRunComplete(s), isFalse);
    expect(mayEnterSuiteShell(firstRunDone: firstRunComplete(s)), isFalse);
    expect(
      mayRequestResidualPermissions(firstRunDone: firstRunComplete(s)),
      isFalse,
    );

    s = s.copyWith(seedDone: true);
    expect(nextFirstRunStep(s), FirstRunStep.licence);
    // Account+seed without licence still blocks residual paths.
    expect(firstRunComplete(s), isFalse);
    expect(mayEnterSuiteShell(firstRunDone: firstRunComplete(s)), isFalse);
    expect(
      mayRequestResidualPermissions(firstRunDone: firstRunComplete(s)),
      isFalse,
    );

    s = s.copyWith(licenceAccepted: true);
    expect(nextFirstRunStep(s), FirstRunStep.complete);
    expect(firstRunComplete(s), isTrue);
    expect(mayEnterSuiteShell(firstRunDone: true), isTrue);
    expect(mayRequestResidualPermissions(firstRunDone: true), isTrue);
  });

  test('out-of-order flags still advance through account then seed then licence',
      () {
    // Licence accepted early must not skip account/seed steps.
    final s = const FirstRunState(
      accountDone: false,
      seedDone: false,
      licenceAccepted: true,
    );
    expect(nextFirstRunStep(s), FirstRunStep.account);
    expect(firstRunComplete(s), isFalse);
    expect(mayRequestResidualPermissions(firstRunDone: false), isFalse);

    final seedOnly = const FirstRunState(
      accountDone: false,
      seedDone: true,
      licenceAccepted: false,
    );
    expect(nextFirstRunStep(seedOnly), FirstRunStep.account);

    final accountAndLicence = const FirstRunState(
      accountDone: true,
      seedDone: false,
      licenceAccepted: true,
    );
    expect(nextFirstRunStep(accountAndLicence), FirstRunStep.seed);
    expect(firstRunComplete(accountAndLicence), isFalse);
  });

  test('residual permission/tunnel helpers stay false until first-run complete',
      () {
    const partials = [
      FirstRunState(
        accountDone: false,
        seedDone: false,
        licenceAccepted: false,
      ),
      FirstRunState(
        accountDone: true,
        seedDone: false,
        licenceAccepted: false,
      ),
      FirstRunState(
        accountDone: true,
        seedDone: true,
        licenceAccepted: false,
      ),
      FirstRunState(
        accountDone: true,
        seedDone: false,
        licenceAccepted: true,
      ),
      FirstRunState(
        accountDone: false,
        seedDone: true,
        licenceAccepted: true,
      ),
    ];
    for (final s in partials) {
      final done = firstRunComplete(s);
      expect(done, isFalse, reason: '$s');
      expect(mayEnterSuiteShell(firstRunDone: done), isFalse);
      expect(mayRequestResidualPermissions(firstRunDone: done), isFalse);
      expect(
        mayResidualConnectAfterFirstRun(
          firstRunDone: done,
          trialOrKeygenOk: true,
        ),
        isFalse,
        reason: 'trial alone cannot open residual before first-run: $s',
      );
    }
    const full = FirstRunState(
      accountDone: true,
      seedDone: true,
      licenceAccepted: true,
    );
    expect(firstRunComplete(full), isTrue);
    expect(mayRequestResidualPermissions(firstRunDone: true), isTrue);
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

  test('FirstRunStore marks seed and loads complete', () async {
    final b = MemorySettingsBackend();
    final accounts = SuiteAccountStore(b);
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
      isAccountRegistered: accounts.isRegistered,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );
    expect(await store.isComplete(), isFalse);
    await accounts.markRegistered('alice');
    expect(nextFirstRunStep(await store.load()), FirstRunStep.seed);
    await store.markSeedDone();
    expect(nextFirstRunStep(await store.load()), FirstRunStep.licence);
    await gate.acceptLicence();
    expect(await store.isComplete(), isTrue);
  });

  test('seed write-down copy is strong offline advice', () {
    expect(kFirstRunSeedBody.toLowerCase(), contains('write'));
    expect(kFirstRunSeedBody.toLowerCase(), contains('12'));
    expect(kFirstRunSeedConfirmLabel.toLowerCase(), contains('wrote'));
    expect(kFirstRunAccountTitle.toLowerCase(), contains('suite'));
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
}
