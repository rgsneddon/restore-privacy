/// VPN-only first-run portal: no account/seed; licence then KEYGEN/trial.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/first_run_gate.dart';
import 'package:restore_privacy_client/first_run_portal.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/settings_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('portal has no username/password or seed surfaces', (tester) async {
    final prefs = MemorySettingsBackend();
    final gate = LicenceGate(MemoryLicenceBackend({}));
    final first = FirstRunStore(
      backend: prefs,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunPortal(
          onComplete: () {},
          licenceGate: gate,
          firstRunStore: first,
          initialState: const FirstRunState(
            licenceAccepted: false,
            entryUnlockDone: false,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text(kFirstRunLicenceStepTitle), findsOneWidget);
    expect(find.textContaining('password'), findsNothing);
    expect(find.textContaining('Password'), findsNothing);
    expect(find.textContaining('Username'), findsNothing);
    expect(find.textContaining('username'), findsNothing);
    expect(find.textContaining('seed'), findsNothing);
    expect(find.textContaining('Seed'), findsNothing);
  });

  testWidgets('after licence, KEYGEN/trial step — no account continue',
      (tester) async {
    final prefs = MemorySettingsBackend();
    final gate = LicenceGate(MemoryLicenceBackend({
      kKeyLicenceAccepted: true,
      kKeyLicenceId: kCurrentLicenceId,
      kKeyLicenceAcceptedAt: '1',
    }));
    final first = FirstRunStore(
      backend: prefs,
      hasAcceptedLicence: () => gate.hasAcceptedLicence(),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunPortal(
          onComplete: () {},
          licenceGate: gate,
          firstRunStore: first,
          initialState: const FirstRunState(
            licenceAccepted: true,
            entryUnlockDone: false,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text(kFirstRunKeygenStepTitle), findsOneWidget);
    expect(find.text(kContinueTrialButtonLabel), findsOneWidget);
    expect(find.byKey(kFirstRunKeygenContinueKey), findsOneWidget);
    expect(find.byKey(kFirstRunContinueTrialKey), findsOneWidget);
  });
}
