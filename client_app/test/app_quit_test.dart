import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/app_quit.dart';

void main() {
  group('showsMainScreenQuitButton', () {
    test('all residual platforms show Quit (including Windows/Linux)', () {
      expect(
        showsMainScreenQuitButton(
          isMacOS: true,
          isIOS: false,
          isAndroid: false,
          isWindows: false,
          isLinux: false,
        ),
        isTrue,
      );
      expect(
        showsMainScreenQuitButton(
          isMacOS: false,
          isIOS: true,
          isAndroid: false,
          isWindows: false,
          isLinux: false,
        ),
        isTrue,
      );
      expect(
        showsMainScreenQuitButton(
          isMacOS: false,
          isIOS: false,
          isAndroid: true,
          isWindows: false,
          isLinux: false,
        ),
        isTrue,
      );
      expect(
        showsMainScreenQuitButton(
          isMacOS: false,
          isIOS: false,
          isAndroid: false,
          isWindows: true,
          isLinux: false,
        ),
        isTrue,
      );
      expect(
        showsMainScreenQuitButton(
          isMacOS: false,
          isIOS: false,
          isAndroid: false,
          isWindows: false,
          isLinux: true,
        ),
        isTrue,
      );
    });

    test('target platform matrix includes desktop', () {
      expect(showsMainScreenQuitForTarget(TargetPlatform.macOS), isTrue);
      expect(showsMainScreenQuitForTarget(TargetPlatform.iOS), isTrue);
      expect(showsMainScreenQuitForTarget(TargetPlatform.android), isTrue);
      expect(showsMainScreenQuitForTarget(TargetPlatform.windows), isTrue);
      expect(showsMainScreenQuitForTarget(TargetPlatform.linux), isTrue);
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

    test('awaits stop before calling exit even if stop is slow', () async {
      final order = <String>[];
      await performQuitSequence(
        stopTunnel: () async {
          await Future<void>.delayed(const Duration(milliseconds: 5));
          order.add('stop');
        },
        exitApp: () {
          order.add('exit');
        },
      );
      expect(order, ['stop', 'exit']);
    });

    test('still exits when stopTunnel completes (no rethrow path)', () async {
      var exited = false;
      await performQuitSequence(
        stopTunnel: () async {},
        exitApp: () {
          exited = true;
        },
      );
      expect(exited, isTrue);
    });
  });

  test('Quit placement is lower-left with disconnect-then-exit copy', () {
    expect(kQuitButtonLabel, 'Quit');
    expect(kQuitButtonPlacement, 'bottomLeft');
    expect(kQuitButtonTooltip.toLowerCase(), contains('quit'));
    expect(kQuitButtonTooltip.toLowerCase(), contains('stop residual'));
  });
}
