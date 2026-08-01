/// Ned icon stimuli: pure phase→asset mapping + rpAI chrome presence.
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

const _kTestNarrative = 'Ned icon test shell.';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('asset tree (shipped paths)', () {
    test('all four Imagine motifs exist on disk + in path constants', () {
      final root = _clientAppRoot();
      for (final rel in kNedIconAssetPaths) {
        final f = File('${root.path}/$rel');
        expect(f.existsSync(), isTrue, reason: 'missing $rel under ${root.path}');
        expect(f.lengthSync(), greaterThan(1000), reason: '$rel too small');
      }
      expect(kNedIconAssetPaths, contains(kNedIconAssetPackage));
      expect(kNedIconAssetPaths, contains(kNedIconAssetChip));
      expect(kNedIconAssetPaths, contains(kNedIconAssetSatellite));
      expect(kNedIconAssetPaths, contains(kNedIconAssetGear));
      // Distinct assets — no accidental alias of all stimuli to one file.
      final basenames = kNedIconAssetPaths.map((p) => p.split('/').last).toSet();
      expect(basenames.length, 4);
    });

    test('pubspec declares Ned icon assets for packaging', () {
      final pubspec = File('${_clientAppRoot().path}/pubspec.yaml').readAsStringSync();
      for (final rel in kNedIconAssetPaths) {
        expect(pubspec, contains(rel), reason: 'pubspec must declare $rel');
      }
    });
  });

  group('nedIconStimulusFor (pure, real phases)', () {
    test('menu → idle package; done → ready package', () {
      expect(
        nedIconStimulusFor(phase: NedGuidePhase.menu),
        NedIconStimulus.idle,
      );
      expect(
        nedIconAssetForStimulus(NedIconStimulus.idle),
        kNedIconAssetPackage,
      );
      expect(
        nedIconStimulusFor(phase: NedGuidePhase.done),
        NedIconStimulus.ready,
      );
      expect(
        nedIconAssetForStimulus(NedIconStimulus.ready),
        kNedIconAssetPackage,
      );
    });

    test('ask* phases → satellite asking', () {
      for (final phase in [
        NedGuidePhase.askContinueSetup,
        NedGuidePhase.askHowTo,
        NedGuidePhase.askVpnTour,
      ]) {
        final s = nedIconStimulusFor(phase: phase);
        expect(s, NedIconStimulus.asking, reason: '$phase');
        expect(nedIconAssetForStimulus(s), kNedIconAssetSatellite);
      }
    });

    test('registering and busy → chip processing', () {
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
        kNedIconAssetChip,
      );
    });

    test('howtoParts and vpnTourParts → gear explaining', () {
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
        kNedIconAssetGear,
      );
    });

    test('real nedGuide* transitions advance the stimulus', () {
      var s = nedGuideInitial(registered: false, deferred: true);
      expect(s.phase, NedGuidePhase.menu);
      expect(nedIconStimulusForState(s), NedIconStimulus.idle);

      s = nedGuideStartContinueSetup(s);
      expect(s.phase, NedGuidePhase.askContinueSetup);
      expect(nedIconStimulusForState(s), NedIconStimulus.asking);

      s = nedGuideBeginRegistering(s);
      expect(s.phase, NedGuidePhase.registering);
      expect(nedIconStimulusForState(s), NedIconStimulus.processing);

      s = nedGuideAfterRegistered(s, username: 'neduser');
      expect(s.phase, NedGuidePhase.askHowTo);
      expect(nedIconStimulusForState(s), NedIconStimulus.asking);

      s = nedGuideStartHowTo(s);
      expect(s.phase, NedGuidePhase.howtoParts);
      expect(nedIconStimulusForState(s), NedIconStimulus.explaining);

      // Drive Continue… until VPN offer (real transition chain).
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
      expect(nedIconAssetForState(s), kNedIconAssetPackage);
    });

    test('decline paths land on ready stimulus without inventing phases', () {
      var s = nedGuideInitial(registered: true, deferred: false);
      s = nedGuideStartHowToOfferFromMenu(s);
      expect(nedIconStimulusForState(s), NedIconStimulus.asking);
      s = nedGuideDeclineHowTo(s);
      expect(s.phase, NedGuidePhase.done);
      expect(nedIconStimulusForState(s), NedIconStimulus.ready);
    });
  });

  group('SuiteRpaiTab icon chrome', () {
    testWidgets('avatar + package idle on deferred menu', (tester) async {
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
      // Letter-N placeholder replaced by Imagine package chrome.
      expect(find.byKey(const Key('ned_icon_asset_idle')), findsOneWidget);
      // Existing controls still present.
      expect(find.byKey(const Key('ned_resume_setup')), findsOneWidget);
    });

    testWidgets('resume → asking satellite stimulus', (tester) async {
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
      expect(find.byKey(const Key('ned_setup_yes')), findsOneWidget);
      expect(find.byKey(const Key('ned_setup_no')), findsOneWidget);
    });

    testWidgets('how-to yes → explaining gear; continue keeps gear', (tester) async {
      await _prepSurface(tester);
      final store = SuiteAccountStore(MemorySettingsBackend());
      await store.markRegistered('iconuser');

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
      expect(find.byKey(const Key('ned_icon_stimulus_explaining')), findsOneWidget);
      expect(find.byKey(const Key('ned_continue')), findsOneWidget);
      await _tapKey(tester, 'ned_continue');
      expect(find.byKey(const Key('ned_icon_stimulus_explaining')), findsOneWidget);
    });

    testWidgets('decline how-to → ready package stimulus', (tester) async {
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
    });
  });

  group('structural wiring', () {
    test('rpAI tab imports mapper and does not gate Connect', () {
      final src = File('${_clientAppRoot().path}/lib/suite_rpai_tab.dart')
          .readAsStringSync();
      expect(src.contains('suite_ned_icons.dart'), isTrue);
      expect(src.contains('nedIconStimulusFor'), isTrue);
      expect(src.contains('ned_icon_avatar'), isTrue);
      expect(src.contains('ned_resume_setup'), isTrue);
      // Still a decorator — no mayConnect gate from icons.
      expect(src.contains('mayConnect'), isFalse);
      final mapper = File('${_clientAppRoot().path}/lib/suite_ned_icons.dart')
          .readAsStringSync();
      expect(mapper.contains('NedGuidePhase'), isTrue);
      expect(mapper.contains('nedIconStimulusFor'), isTrue);
    });
  });
}

Directory _clientAppRoot() {
  final cwd = Directory.current;
  // flutter test cwd is usually client_app/
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
