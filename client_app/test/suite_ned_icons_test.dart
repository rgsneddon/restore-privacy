/// Ned face stimuli: pure phase→face mapping + rpAI chrome presence.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_account.dart';
import 'package:restore_privacy_client/suite_ned_guide.dart';
import 'package:restore_privacy_client/suite_ned_icons.dart';
import 'package:restore_privacy_client/suite_rpai_tab.dart';
import 'package:restore_privacy_client/theme.dart';

const _kTestNarrative = 'Ned face test shell.';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('face asset tree (shipped paths)', () {
    test('all five Imagine faces exist on disk + in path constants', () {
      final root = _clientAppRoot();
      for (final rel in kNedFaceAssetPaths) {
        final f = File('${root.path}/$rel');
        expect(f.existsSync(), isTrue, reason: 'missing $rel under ${root.path}');
        expect(f.lengthSync(), greaterThan(1000), reason: '$rel too small');
      }
      expect(kNedFaceAssetPaths, contains(kNedFaceAssetDefault));
      expect(kNedFaceAssetPaths, contains(kNedFaceAssetError));
      expect(kNedFaceAssetPaths, contains(kNedFaceAssetExcited));
      expect(kNedFaceAssetPaths, contains(kNedFaceAssetConfused));
      expect(kNedFaceAssetPaths, contains(kNedFaceAssetSleep));
      // Distinct assets — no accidental alias of all faces to one file.
      final basenames = kNedFaceAssetPaths.map((p) => p.split('/').last).toSet();
      expect(basenames.length, 5);
      // Primary chrome list is the face set.
      expect(kNedIconAssetPaths, kNedFaceAssetPaths);
    });

    test('pubspec declares Ned face assets for packaging', () {
      final pubspec =
          File('${_clientAppRoot().path}/pubspec.yaml').readAsStringSync();
      for (final rel in kNedFaceAssetPaths) {
        expect(pubspec, contains(rel), reason: 'pubspec must declare $rel');
      }
    });
  });

  group('nedIconStimulusFor (pure, real phases → faces)', () {
    test('menu → idle default; done → ready excited', () {
      expect(
        nedIconStimulusFor(phase: NedGuidePhase.menu),
        NedIconStimulus.idle,
      );
      expect(
        nedIconAssetForStimulus(NedIconStimulus.idle),
        kNedFaceAssetDefault,
      );
      expect(
        nedIconStimulusFor(phase: NedGuidePhase.done),
        NedIconStimulus.ready,
      );
      expect(
        nedIconAssetForStimulus(NedIconStimulus.ready),
        kNedFaceAssetExcited,
      );
      expect(nedFaceStatusLabel(NedIconStimulus.idle), 'DEFAULT');
      expect(nedFaceStatusLabel(NedIconStimulus.ready), 'EXCITED');
    });

    test('ask* phases → confused face', () {
      for (final phase in [
        NedGuidePhase.askContinueSetup,
        NedGuidePhase.askHowTo,
        NedGuidePhase.askVpnTour,
      ]) {
        final s = nedIconStimulusFor(phase: phase);
        expect(s, NedIconStimulus.asking, reason: '$phase');
        expect(nedIconAssetForStimulus(s), kNedFaceAssetConfused);
        expect(nedFaceStatusLabel(s), 'CONFUSED');
      }
    });

    test('registering and busy → sleep face', () {
      expect(
        nedIconStimulusFor(phase: NedGuidePhase.registering),
        NedIconStimulus.processing,
      );
      expect(
        nedIconStimulusFor(phase: NedGuidePhase.menu, busy: true),
        NedIconStimulus.processing,
      );
      expect(
        nedIconStimulusFor(phase: NedGuidePhase.howtoParts, busy: true),
        NedIconStimulus.processing,
      );
      expect(
        nedIconAssetForStimulus(NedIconStimulus.processing),
        kNedFaceAssetSleep,
      );
      expect(nedFaceStatusLabel(NedIconStimulus.processing), 'SLEEP');
    });

    test('howtoParts and vpnTourParts → excited face', () {
      expect(
        nedIconStimulusFor(phase: NedGuidePhase.howtoParts),
        NedIconStimulus.explaining,
      );
      expect(
        nedIconStimulusFor(phase: NedGuidePhase.vpnTourParts),
        NedIconStimulus.explaining,
      );
      expect(
        nedIconAssetForStimulus(NedIconStimulus.explaining),
        kNedFaceAssetExcited,
      );
      expect(nedFaceStatusLabel(NedIconStimulus.explaining), 'EXCITED');
    });

    test('error flag → ERROR face only (not a normal decline path)', () {
      final s = nedIconStimulusFor(phase: NedGuidePhase.menu, error: true);
      expect(s, NedIconStimulus.error);
      expect(nedIconAssetForStimulus(s), kNedFaceAssetError);
      expect(nedFaceStatusLabel(s), 'ERROR');
      // Decline to done is ready/excited — not a fake error.
      var g = nedGuideInitial(registered: true, deferred: false);
      g = nedGuideStartHowToOfferFromMenu(g);
      g = nedGuideDeclineHowTo(g);
      expect(g.phase, NedGuidePhase.done);
      expect(nedIconStimulusForState(g), NedIconStimulus.ready);
      expect(nedIconStimulusForState(g), isNot(NedIconStimulus.error));
    });

    test('real nedGuide* transitions advance the face stimulus', () {
      var s = nedGuideInitial(registered: false, deferred: true);
      expect(s.phase, NedGuidePhase.menu);
      expect(nedIconStimulusForState(s), NedIconStimulus.idle);
      expect(nedIconAssetForState(s), kNedFaceAssetDefault);

      s = nedGuideStartContinueSetup(s);
      expect(s.phase, NedGuidePhase.askContinueSetup);
      expect(nedIconStimulusForState(s), NedIconStimulus.asking);
      expect(nedIconAssetForState(s), kNedFaceAssetConfused);

      s = nedGuideBeginRegistering(s);
      expect(s.phase, NedGuidePhase.registering);
      expect(nedIconStimulusForState(s), NedIconStimulus.processing);
      expect(nedIconAssetForState(s), kNedFaceAssetSleep);

      s = nedGuideAfterRegistered(s, username: 'neduser');
      expect(s.phase, NedGuidePhase.askHowTo);
      expect(nedIconStimulusForState(s), NedIconStimulus.asking);

      s = nedGuideStartHowTo(s);
      expect(s.phase, NedGuidePhase.howtoParts);
      expect(nedIconStimulusForState(s), NedIconStimulus.explaining);
      expect(nedIconAssetForState(s), kNedFaceAssetExcited);

      var guard = 0;
      while (s.phase == NedGuidePhase.howtoParts && guard < 20) {
        s = nedGuideContinue(s);
        guard++;
      }
      expect(s.phase, NedGuidePhase.askVpnTour);
      expect(nedIconStimulusForState(s), NedIconStimulus.asking);

      s = nedGuideStartVpnTour(s);
      expect(s.phase, NedGuidePhase.vpnTourParts);
      expect(nedIconStimulusForState(s), NedIconStimulus.explaining);

      guard = 0;
      while (s.phase == NedGuidePhase.vpnTourParts && guard < 20) {
        s = nedGuideContinue(s);
        guard++;
      }
      expect(s.phase, NedGuidePhase.done);
      expect(nedIconStimulusForState(s), NedIconStimulus.ready);
      expect(nedIconAssetForState(s), kNedFaceAssetExcited);
    });
  });

  group('SuiteRpaiTab face chrome', () {
    testWidgets('avatar + default face on deferred menu', (tester) async {
      await _prepSurface(tester);
      final store = SuiteAccountStore(MemorySettingsBackend());
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

      expect(find.byKey(const Key('ned_icon_avatar')), findsOneWidget);
      expect(find.byKey(const Key('ned_icon_stimulus_idle')), findsOneWidget);
      expect(find.byKey(const Key('ned_icon_stimulus_label')), findsOneWidget);
      expect(find.byKey(const Key('ned_icon_asset_idle')), findsOneWidget);
      expect(find.textContaining('DEFAULT'), findsWidgets);
      expect(find.byKey(const Key('ned_resume_setup')), findsOneWidget);
    });

    testWidgets('resume → confused face stimulus', (tester) async {
      await _prepSurface(tester);
      final store = SuiteAccountStore(MemorySettingsBackend());
      await store.markDeferred();

      await tester.pumpWidget(
        MaterialApp(
          home: SuiteRpaiTab(
            narrative: _kTestNarrative,
            accountStore: store,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('ned_icon_stimulus_idle')), findsOneWidget);
      await _tapKey(tester, 'ned_resume_setup');
      expect(find.byKey(const Key('ned_icon_stimulus_asking')), findsOneWidget);
      expect(find.textContaining('CONFUSED'), findsWidgets);
      expect(find.byKey(const Key('ned_setup_yes')), findsOneWidget);
      expect(find.byKey(const Key('ned_setup_no')), findsOneWidget);
    });

    testWidgets('how-to yes → excited face; continue keeps excited',
        (tester) async {
      await _prepSurface(tester);
      final store = SuiteAccountStore(MemorySettingsBackend());
      await store.markRegistered('faceuser');

      await tester.pumpWidget(
        MaterialApp(
          home: SuiteRpaiTab(
            narrative: _kTestNarrative,
            accountStore: store,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('ned_icon_stimulus_idle')), findsOneWidget);
      await _tapKey(tester, 'ned_offer_howto');
      expect(find.byKey(const Key('ned_icon_stimulus_asking')), findsOneWidget);
      await _tapKey(tester, 'ned_howto_yes');
      expect(
        find.byKey(const Key('ned_icon_stimulus_explaining')),
        findsOneWidget,
      );
      expect(find.textContaining('EXCITED'), findsWidgets);
      expect(find.byKey(const Key('ned_continue')), findsOneWidget);
      await _tapKey(tester, 'ned_continue');
      expect(
        find.byKey(const Key('ned_icon_stimulus_explaining')),
        findsOneWidget,
      );
    });

    testWidgets('decline how-to → ready/excited face (not ERROR)', (tester) async {
      await _prepSurface(tester);
      final store = SuiteAccountStore(MemorySettingsBackend());
      await store.markRegistered('doneuser');

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
      await _tapKey(tester, 'ned_howto_no');
      expect(find.byKey(const Key('ned_icon_stimulus_ready')), findsOneWidget);
      expect(find.byKey(const Key('ned_icon_stimulus_error')), findsNothing);
    });
  });

  group('structural wiring', () {
    test('rpAI tab imports face mapper and does not gate Connect', () {
      final src = File('${_clientAppRoot().path}/lib/suite_rpai_tab.dart')
          .readAsStringSync();
      expect(src.contains('suite_ned_icons.dart'), isTrue);
      expect(src.contains('nedIconStimulusFor'), isTrue);
      expect(src.contains('ned_icon_avatar'), isTrue);
      expect(src.contains('ned_resume_setup'), isTrue);
      expect(src.contains('mayConnect'), isFalse);
      final mapper = File('${_clientAppRoot().path}/lib/suite_ned_icons.dart')
          .readAsStringSync();
      expect(mapper.contains('NedGuidePhase'), isTrue);
      expect(mapper.contains('nedIconStimulusFor'), isTrue);
      expect(mapper.contains('kNedFaceAssetDefault'), isTrue);
      expect(mapper.contains('kNedFaceAssetConfused'), isTrue);
      expect(mapper.contains('kNedFaceAssetSleep'), isTrue);
      expect(mapper.contains('kNedFaceAssetExcited'), isTrue);
      expect(mapper.contains('kNedFaceAssetError'), isTrue);
    });
  });
}

Directory _clientAppRoot() {
  final cwd = Directory.current;
  if (File('${cwd.path}/pubspec.yaml').existsSync() &&
      File('${cwd.path}/lib/suite_ned_icons.dart').existsSync()) {
    return cwd;
  }
  final nested = Directory('${cwd.path}/client_app');
  if (File('${nested.path}/lib/suite_ned_icons.dart').existsSync()) {
    return nested;
  }
  throw StateError('cannot locate client_app root from ${cwd.path}');
}

Future<void> _prepSurface(WidgetTester tester) async {
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
