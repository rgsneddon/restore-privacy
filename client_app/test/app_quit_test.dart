import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/app_quit.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

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
        exitApp: () async {
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
        exitApp: () async {
          order.add('exit');
        },
      );
      expect(order, ['stop', 'exit']);
    });

    test('awaits async exitApp (Android fullExit must complete before backup)',
        () async {
      final order = <String>[];
      await performQuitSequence(
        stopTunnel: () async {
          order.add('stop');
        },
        exitApp: () async {
          await Future<void>.delayed(const Duration(milliseconds: 5));
          order.add('exit');
        },
      );
      expect(order, ['stop', 'exit']);
    });

    test('still exits when stopTunnel completes (no rethrow path)', () async {
      var exited = false;
      await performQuitSequence(
        stopTunnel: () async {},
        exitApp: () async {
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

  group('Android full process exit', () {
    test('exit planner requires await channel then finishAndRemoveTask', () {
      final steps = androidFullExitSteps();
      expect(steps, contains('await_fullExit_channel'));
      expect(steps, contains('finishAndRemoveTask'));
      expect(steps, contains('process_killProcess'));
      expect(
        steps.indexOf('await_fullExit_channel'),
        lessThan(steps.indexOf('finishAndRemoveTask')),
      );
    });

    test('exitAppProcess awaits fullExit channel before dart exit', () async {
      final order = <String>[];
      final messenger =
          TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
      const channel = MethodChannel('restore_privacy/vpn_test_quit');
      messenger.setMockMethodCallHandler(channel, (call) async {
        expect(call.method, kAndroidFullExitMethod);
        order.add('native_fullExit');
        // Simulate slow native path — must complete before exitFn.
        await Future<void>.delayed(const Duration(milliseconds: 10));
        order.add('native_done');
        return {'ok': true};
      });
      addTearDown(() {
        messenger.setMockMethodCallHandler(channel, null);
      });

      await exitAppProcess(
        channel: channel,
        isAndroid: true,
        exitFn: (code) {
          order.add('dart_exit_$code');
        },
      );

      expect(
        order,
        ['native_fullExit', 'native_done', 'dart_exit_0'],
        reason: 'native fullExit must finish before dart:io exit backup',
      );
    });

    test('app_quit.dart Android path awaits invokeMethod not fire-and-forget',
        () {
      final src = File('lib/app_quit.dart').readAsStringSync();
      expect(src.contains('kAndroidFullExitMethod'), isTrue);
      expect(src.contains("'fullExit'"), isTrue);
      // Critical: must await channel before any exit backup.
      expect(src.contains('await ch.invokeMethod'), isTrue);
      expect(
        src.contains('Fire-and-forget'),
        isFalse,
        reason: 'fire-and-forget path was the idle-process bug',
      );
      // performQuitSequence must await exitApp
      expect(src.contains('await exitApp()'), isTrue);
      expect(src.contains('Future<void> Function() exitApp'), isTrue);
    });

    test('main.dart wires async exitAppProcess (not sync void only)', () {
      final src = File('lib/main.dart').readAsStringSync();
      expect(src.contains('await exitAppProcess()'), isTrue);
      expect(src.contains('exitApp: () async'), isTrue);
    });

    test('MainActivity implements fullExit with finishAndRemoveTask + killProcess',
        () {
      final kt = File(
        'android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client/MainActivity.kt',
      ).readAsStringSync();
      expect(kt.contains('"fullExit"'), isTrue);
      expect(kt.contains('fullProcessExit'), isTrue);
      expect(kt.contains('finishAndRemoveTask'), isTrue);
      expect(kt.contains('killProcess'), isTrue);
      expect(kt.contains('System.exit'), isTrue);
      // Reply success before kill so awaiting Dart can complete invokeMethod.
      final fullExitIdx = kt.indexOf('"fullExit"');
      expect(fullExitIdx, greaterThanOrEqualTo(0));
      final block = kt.substring(
        fullExitIdx,
        (fullExitIdx + 600).clamp(0, kt.length),
      );
      expect(block.contains('result.success'), isTrue);
      expect(block.contains('fullProcessExit()'), isTrue);
      expect(
        block.indexOf('result.success'),
        lessThan(block.indexOf('fullProcessExit()')),
      );
    });
  });
}
