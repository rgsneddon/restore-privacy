/// Ned rpAI: deferred resume setup + stepped wallet/Evolve/VPN how-tos.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_account.dart';
import 'package:restore_privacy_client/suite_ned_guide.dart';
import 'package:restore_privacy_client/suite_rpai_tab.dart';
import 'package:restore_privacy_client/theme.dart';

/// Short narrative so widget tests fit default surface height.
const _kTestNarrative = 'Ned test shell.';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('nedAccountBranch + resume/how-to visibility (pure)', () {
    test('deferred not registered → resume setup', () {
      expect(
        nedAccountBranch(registered: false, deferred: true),
        NedAccountBranch.resumeSetup,
      );
      expect(
        shouldShowNedResumeSetupLink(registered: false, deferred: true),
        isTrue,
      );
      expect(
        shouldShowNedHowToOffer(registered: false),
        isFalse,
      );
    });

    test('registered → how-to offer, no resume register wall', () {
      expect(
        nedAccountBranch(registered: true, deferred: true),
        NedAccountBranch.offerHowTo,
      );
      expect(
        shouldShowNedResumeSetupLink(registered: true, deferred: true),
        isFalse,
      );
      expect(shouldShowNedHowToOffer(registered: true), isTrue);
    });

    test('neither → still offer setup link', () {
      expect(
        nedAccountBranch(registered: false, deferred: false),
        NedAccountBranch.offerSetup,
      );
      expect(
        shouldShowNedResumeSetupLink(registered: false, deferred: false),
        isTrue,
      );
    });

    test('Suite account flags do not gate VPN mayConnect contract', () {
      // Documented invariant: registration is independent of residual Connect.
      // Pure helpers never reference licence/mayConnect; branch only uses flags.
      expect(
        shouldShowNedResumeSetupLink(registered: false, deferred: true),
        isTrue,
      );
      expect(
        shouldShowNedHowToOffer(registered: true),
        isTrue,
      );
      final src = _readSuiteFile('lib/suite_account.dart');
      expect(src.contains('mayConnect'), isTrue);
      expect(
        src.toLowerCase().contains('never') ||
            src.contains('Independent of VPN'),
        isTrue,
      );
    });
  });

  group('how-to step machine (pure)', () {
    test('continue walks wallet+evolve parts then VPN tour offer', () {
      var s = nedGuideInitial(registered: true, deferred: false);
      s = nedGuideStartHowToOfferFromMenu(s);
      expect(s.phase, NedGuidePhase.askHowTo);
      expect(s.lines.last, kNedAskHowTo);

      s = nedGuideStartHowTo(s);
      expect(s.phase, NedGuidePhase.howtoParts);
      expect(s.lines.last, contains(kNedWalletHowToParts.first.title));

      final totalParts = nedWalletEvolveHowToParts().length;
      // First part already shown; advance through remaining.
      for (var i = 1; i < totalParts; i++) {
        expect(nedGuideShowsContinue(s), isTrue, reason: 'part $i');
        s = nedGuideContinue(s);
      }
      // After last how-to part → ask VPN tour
      expect(s.phase, NedGuidePhase.askVpnTour);
      expect(s.lines.last, kNedAskVpnTour);
      expect(nedGuideShowsVpnTourChoices(s), isTrue);
      expect(nedGuideShowsContinue(s), isFalse);
    });

    test('VPN tour opt-in yields full VPN how-to then done', () {
      var s = nedGuideInitial(registered: true, deferred: false);
      s = nedGuideStartHowTo(s);
      // Skip to VPN ask
      while (s.phase == NedGuidePhase.howtoParts) {
        s = nedGuideContinue(s);
      }
      expect(s.phase, NedGuidePhase.askVpnTour);

      s = nedGuideStartVpnTour(s);
      expect(s.phase, NedGuidePhase.vpnTourParts);
      expect(s.lines.last, contains(kNedVpnHowToParts.first.title));

      while (s.phase == NedGuidePhase.vpnTourParts) {
        s = nedGuideContinue(s);
      }
      expect(s.phase, NedGuidePhase.done);
      expect(s.lines.last, kNedDoneLabel);
      // Content covers VPN tour when opted in
      final joined = s.lines.join('\n');
      expect(joined.toLowerCase(), contains('keygen'));
      expect(joined.toLowerCase(), contains('connect'));
      expect(joined, contains(kNedWalletHowToParts.first.title));
      expect(joined, contains(kNedEvolveHowToParts.first.title));
    });

    test('decline VPN tour finishes without vpn part titles', () {
      var s = nedGuideInitial(registered: true, deferred: false);
      s = nedGuideStartHowTo(s);
      while (s.phase == NedGuidePhase.howtoParts) {
        s = nedGuideContinue(s);
      }
      s = nedGuideDeclineVpnTour(s);
      expect(s.phase, NedGuidePhase.done);
      expect(s.lines.join('\n'), isNot(contains(kNedVpnHowToParts[2].title)));
    });

    test('continue-setup yes/no paths', () {
      var s = nedGuideInitial(registered: false, deferred: true);
      s = nedGuideStartContinueSetup(s);
      expect(s.phase, NedGuidePhase.askContinueSetup);
      expect(s.lines.last, kNedAskContinueSetup);
      expect(nedGuideShowsContinueSetupChoices(s), isTrue);

      final no = nedGuideDeclineSetup(s);
      expect(no.phase, NedGuidePhase.done);
      expect(no.lines.join('\n').toLowerCase(), contains('vpn'));

      final yes = nedGuideBeginRegistering(s);
      expect(yes.phase, NedGuidePhase.registering);
      final after = nedGuideAfterRegistered(yes, username: 'alice');
      expect(after.phase, NedGuidePhase.askHowTo);
      expect(after.lines.join('\n'), contains('alice'));
    });
  });

  group('SuiteRpaiTab widget', () {
    testWidgets('deferred shows resume setup and Ned continue question',
        (tester) async {
      await _prepSurface(tester);
      final backend = MemorySettingsBackend();
      final store = SuiteAccountStore(backend);
      await store.markDeferred();

      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(scaffoldBackgroundColor: kChromeBg),
          home: SuiteRpaiTab(
            narrative: _kTestNarrative,
            accountStore: store,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('ned_resume_setup')), findsOneWidget);
      expect(find.byKey(const Key('ned_offer_howto')), findsNothing);

      await _tapKey(tester, 'ned_resume_setup');

      expect(find.text(kNedAskContinueSetup), findsOneWidget);
      expect(find.byKey(const Key('ned_setup_yes')), findsOneWidget);
      expect(find.byKey(const Key('ned_setup_no')), findsOneWidget);
      // Resume control hides once the continue-setup question is active.
      expect(find.byKey(const Key('ned_resume_setup')), findsNothing);
    });

    testWidgets('registered shows how-to offer not resume register',
        (tester) async {
      await _prepSurface(tester);
      final store = SuiteAccountStore(MemorySettingsBackend());
      await store.markRegistered('alice');

      await tester.pumpWidget(
        MaterialApp(
          home: SuiteRpaiTab(
            narrative: _kTestNarrative,
            accountStore: store,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('ned_resume_setup')), findsNothing);
      expect(find.byKey(const Key('ned_offer_howto')), findsOneWidget);

      await _tapKey(tester, 'ned_offer_howto');
      expect(find.text(kNedAskHowTo), findsOneWidget);
      expect(find.byKey(const Key('ned_howto_yes')), findsOneWidget);
    });

    testWidgets('how-to continue steps then VPN tour opt-in', (tester) async {
      await _prepSurface(tester);
      final store = SuiteAccountStore(MemorySettingsBackend());
      await store.markRegistered('bob');

      await tester.pumpWidget(
        MaterialApp(
          home: SuiteRpaiTab(
            narrative: _kTestNarrative,
            accountStore: store,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await _tapKey(tester, 'ned_offer_howto');
      await _tapKey(tester, 'ned_howto_yes');

      expect(find.byKey(const Key('ned_continue')), findsOneWidget);
      final n = nedWalletEvolveHowToParts().length;
      for (var i = 0; i < n; i++) {
        if (find.byKey(const Key('ned_continue')).evaluate().isEmpty) break;
        await _tapKey(tester, 'ned_continue');
      }

      expect(find.text(kNedAskVpnTour), findsOneWidget);
      await _tapKey(tester, 'ned_vpn_tour_yes');
      expect(find.byKey(const Key('ned_continue')), findsOneWidget);
      // First VPN part is licence; KEYGEN appears on the next Continue…
      expect(find.textContaining('licence'), findsWidgets);
      await _tapKey(tester, 'ned_continue');
      expect(find.textContaining('KEYGEN'), findsWidgets);
    });

    testWidgets('setup yes reuses suite account prompt (singular form)',
        (tester) async {
      await _prepSurface(tester);
      // Required so SuiteRpaiTab + showSuiteAccountPrompt do not hang on prefs.
      SharedPreferences.setMockInitialValues({});
      final store = SuiteAccountStore(MemorySettingsBackend());
      await store.markDeferred();
      var applyCalls = 0;

      await tester.pumpWidget(
        MaterialApp(
          home: SuiteRpaiTab(
            narrative: _kTestNarrative,
            accountStore: store,
            applyCredentials: ({
              required String username,
              required String password,
              required bool register,
            }) async {
              applyCalls++;
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      await _tapKey(tester, 'ned_resume_setup');
      await _tapKey(tester, 'ned_setup_yes');
      // Async SharedPreferences + modal bottom sheet.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pumpAndSettle();

      // Unified prompt — one username/password, not dual panels.
      expect(find.byKey(const Key('suite_account_username')), findsOneWidget);
      expect(find.byKey(const Key('suite_account_password')), findsOneWidget);
      expect(find.byKey(const Key('suite_account_defer')), findsOneWidget);

      await tester.enterText(
        find.byKey(const Key('suite_account_username')),
        'neduser',
      );
      await tester.enterText(
        find.byKey(const Key('suite_account_password')),
        'password99',
      );
      await _tapKey(tester, 'suite_account_submit');
      await tester.pumpAndSettle();

      expect(applyCalls, 1);
      expect(await store.isRegistered(), isTrue);
    });
  });

  group('structural wiring', () {
    test('rpAI source mounts resume link and Ned script surface', () {
      final src = _readSuiteFile('lib/suite_rpai_tab.dart');
      expect(src.contains('ned_resume_setup'), isTrue);
      expect(src.contains('ned_setup_yes'), isTrue);
      expect(src.contains('ned_offer_howto'), isTrue);
      expect(src.contains('ned_continue'), isTrue);
      expect(src.contains('ned_vpn_tour_yes'), isTrue);
      expect(src.contains('showSuiteAccountPrompt'), isTrue);
      expect(src.contains('nedGuideContinue'), isTrue);
      expect(src.contains('nedGuideStartContinueSetup'), isTrue);
      expect(src.contains('nedGuideStartVpnTour'), isTrue);
      expect(src.contains('applyCredentials'), isTrue);
      // Single unified Suite prompt reuse — not a second parallel register wall.
      expect(src.contains('showSuiteAccountPrompt'), isTrue);
      expect(src.contains('applySuiteAccountToWalletAndEvolve'), isFalse);
      // Imagine Ned icon chrome tracks guide phase (decorator only).
      expect(src.contains('ned_icon_avatar'), isTrue);
      expect(src.contains('nedIconStimulusFor'), isTrue);
      expect(src.contains('suite_ned_icons.dart'), isTrue);
    });
  });
}

Future<void> _prepSurface(WidgetTester tester) async {
  // Tall surface so ListView Ned controls are hit-testable without scroll flakiness.
  final view = tester.view;
  view.physicalSize = const Size(900, 2400);
  view.devicePixelRatio = 1.0;
  addTearDown(view.resetPhysicalSize);
  addTearDown(view.resetDevicePixelRatio);
}

Future<void> _tapKey(WidgetTester tester, String key) async {
  final finder = find.byKey(Key(key));
  expect(finder, findsOneWidget, reason: 'expected key $key before tap');
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

String _readSuiteFile(String relative) {
  final scriptDir = File(Platform.script.toFilePath()).parent;
  final candidates = <File>[
    File(relative),
    File('client_app/$relative'),
    File('${scriptDir.path}/../$relative'),
    File('${Directory.current.path}/$relative'),
    File('${Directory.current.path}/client_app/$relative'),
    // flutter test often sets cwd to client_app/
    File('${Directory.current.path}/lib/${relative.split('/').last}'),
  ];
  // Prefer paths that match the relative structure.
  for (final f in candidates) {
    if (f.existsSync()) {
      final text = f.readAsStringSync();
      // Guard against accidentally reading a different short file.
      if (relative.endsWith('suite_rpai_tab.dart') &&
          !text.contains('SuiteRpaiTab')) {
        continue;
      }
      return text;
    }
  }
  throw StateError(
    'cannot read $relative cwd=${Directory.current.path} '
    'script=${Platform.script}',
  );
}
