import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/app_quit.dart';

void main() {
  group('showsMainScreenQuitButton', () {
    test('macOS and iOS show Quit; others do not', () {
      expect(showsMainScreenQuitButton(isMacOS: true, isIOS: false), isTrue);
      expect(showsMainScreenQuitButton(isMacOS: false, isIOS: true), isTrue);
      expect(showsMainScreenQuitButton(isMacOS: false, isIOS: false), isFalse);
    });

    test('target platform helper matches Apple residual shells', () {
      expect(showsMainScreenQuitForTarget(TargetPlatform.macOS), isTrue);
      expect(showsMainScreenQuitForTarget(TargetPlatform.iOS), isTrue);
      expect(showsMainScreenQuitForTarget(TargetPlatform.android), isFalse);
      expect(showsMainScreenQuitForTarget(TargetPlatform.windows), isFalse);
      expect(showsMainScreenQuitForTarget(TargetPlatform.linux), isFalse);
    });
  });

  group('performQuitSequence', () {
    test('stops tunnel before exit (order is disconnect-then-exit)', () async {
      final order = <String>[];
      await performQuitSequence(
        stopTunnel: () async {
          order.add('stop');
        },
        exitApp: () {
          order.add('exit');
        },
      );
      expect(order, ['stop', 'exit']);
    });

    test('awaits async tunnel stop before calling exit', () async {
      var tunnelDone = false;
      var exited = false;
      await performQuitSequence(
        stopTunnel: () async {
          await Future<void>.delayed(const Duration(milliseconds: 20));
          tunnelDone = true;
        },
        exitApp: () {
          expect(tunnelDone, isTrue, reason: 'exit must run after stopTunnel');
          exited = true;
        },
      );
      expect(exited, isTrue);
    });

    test('still exits if stopTunnel completes (even when no-op)', () async {
      var exited = false;
      await performQuitSequence(
        stopTunnel: () async {},
        exitApp: () => exited = true,
      );
      expect(exited, isTrue);
    });
  });

  test('placement and label constants are discrete product markers', () {
    expect(kQuitButtonLabel, 'Quit');
    expect(kQuitButtonPlacement, 'bottomRight');
    expect(kQuitButtonTooltip.toLowerCase(), contains('quit'));
  });
}
