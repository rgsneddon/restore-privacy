/// Seed confirm hang suite retired: product has no seed first-use path.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/first_run_gate.dart';

void main() {
  test('seed first-use path removed — entry is licence then KEYGEN/trial', () {
    expect(nextFirstRunStep(const FirstRunState(licenceAccepted: false)),
        FirstRunStep.licence);
    expect(
      nextFirstRunStep(
        const FirstRunState(licenceAccepted: true, entryUnlockDone: false),
      ),
      FirstRunStep.keygenOrTrial,
    );
    expect(
      nextFirstRunStep(
        const FirstRunState(licenceAccepted: true, entryUnlockDone: true),
      ),
      FirstRunStep.complete,
    );
  });
}
