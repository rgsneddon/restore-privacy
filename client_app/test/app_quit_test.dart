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
    test('exit planner requires stop service, remove tasks, deferred kill', () {
      final steps = androidFullExitSteps();
      expect(steps, contains('await_fullExit_channel'));
      expect(steps, contains('force_stop_vpn_service'));
      expect(steps, contains('remove_all_app_tasks'));
      expect(steps, contains('finishAffinity'));
      expect(steps, contains('finishAndRemoveTask'));
      expect(steps, contains('deferred_process_kill'));
      expect(
        steps.indexOf('force_stop_vpn_service'),
        lessThan(steps.indexOf('finishAndRemoveTask')),
      );
      expect(
        steps.indexOf('finishAndRemoveTask'),
        lessThan(steps.indexOf('deferred_process_kill')),
      );
      expect(
        kAndroidFullExitBackupDelay.inMilliseconds,
        greaterThan(androidFullExitKillDelayMs),
      );
    });

    test('exitAppProcess awaits fullExit then short backup exit', () async {
      final order = <String>[];
      final messenger =
          TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
      const channel = MethodChannel('restore_privacy/vpn_test_quit');
      messenger.setMockMethodCallHandler(channel, (call) async {
        expect(call.method, kAndroidFullExitMethod);
        order.add('native_fullExit');
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
        delay: (d) async {
          order.add('grace_${d.inMilliseconds}');
        },
        exitFn: (code) {
          order.add('dart_exit_$code');
        },
      );

      expect(
        order,
        [
          'native_fullExit',
          'native_done',
          'grace_${kAndroidFullExitBackupDelay.inMilliseconds}',
          'dart_exit_0',
        ],
        reason: 'native fullExit completes before dart backup exit',
      );
    });

    test('app_quit.dart Android path awaits invokeMethod and backup delay', () {
      final src = File('lib/app_quit.dart').readAsStringSync();
      expect(src.contains('kAndroidFullExitMethod'), isTrue);
      expect(src.contains("'fullExit'"), isTrue);
      expect(src.contains('await ch.invokeMethod'), isTrue);
      expect(src.contains('kAndroidFullExitBackupDelay'), isTrue);
      expect(src.contains('await wait(kAndroidFullExitBackupDelay)'), isTrue);
      expect(
        src.contains('Fire-and-forget'),
        isFalse,
        reason: 'fire-and-forget path was the idle-process bug',
      );
      expect(src.contains('await exitApp()'), isTrue);
      expect(src.contains('Future<void> Function() exitApp'), isTrue);
    });

    test('main.dart wires async exitAppProcess (not sync void only)', () {
      final src = File('lib/main.dart').readAsStringSync();
      expect(src.contains('await exitAppProcess()'), isTrue);
      expect(src.contains('exitApp: () async'), isTrue);
      expect(src.contains('Minimize / background does **not** stop'), isTrue);
    });

    test('MainActivity fullExit: stop without FGS, remove tasks, deferred kill',
        () {
      final kt = File(
        'android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client/MainActivity.kt',
      ).readAsStringSync();
      expect(kt.contains('"fullExit"'), isTrue);
      expect(kt.contains('fullProcessExit'), isTrue);
      expect(kt.contains('forceStopVpnService'), isTrue);
      expect(kt.contains('removeAllAppTasks'), isTrue);
      expect(kt.contains('appTasks'), isTrue);
      expect(kt.contains('finishAffinity'), isTrue);
      expect(kt.contains('finishAndRemoveTask'), isTrue);
      expect(kt.contains('killProcess'), isTrue);
      expect(kt.contains('System.exit'), isTrue);
      expect(kt.contains('Runtime.getRuntime().halt'), isTrue);
      expect(kt.contains('stopService'), isTrue);
      expect(kt.contains('FULL_EXIT_KILL_DELAY_MS'), isTrue);
      // CONNECT may still startForegroundService; DISCONNECT must never do so.
      expect(
        kt.contains('ACTION_CONNECT'),
        isTrue,
        reason: 'connect path must remain present for FGS baseline',
      );

      final forceIdx = kt.indexOf('private fun forceStopVpnService');
      expect(forceIdx, greaterThanOrEqualTo(0));
      final forceBody =
          kt.substring(forceIdx, (forceIdx + 900).clamp(0, kt.length));
      expect(forceBody.contains('ACTION_DISCONNECT'), isTrue);
      expect(forceBody.contains('startService'), isTrue);
      expect(forceBody.contains('stopService'), isTrue);
      expect(
        forceBody.contains('startForegroundService'),
        isFalse,
        reason: 'forceStopVpnService must not start FGS for DISCONNECT',
      );
      // stopService after DISCONNECT startService in forceStop
      expect(
        forceBody.indexOf('startService'),
        lessThan(forceBody.indexOf('stopService')),
      );

      final fnIdx = kt.indexOf('private fun fullProcessExit');
      expect(fnIdx, greaterThanOrEqualTo(0));
      final fnBody = kt.substring(fnIdx, (fnIdx + 1600).clamp(0, kt.length));
      // Kill must be postDelayed after finishAndRemoveTask (AMS + DISCONNECT window).
      expect(fnBody.contains('postDelayed'), isTrue);
      expect(
        fnBody.indexOf('finishAndRemoveTask'),
        lessThan(fnBody.indexOf('postDelayed')),
      );
      expect(
        fnBody.indexOf('forceStopVpnService'),
        lessThan(fnBody.indexOf('postDelayed')),
      );
      expect(fnBody.contains('FULL_EXIT_KILL_DELAY_MS'), isTrue);
      expect(fnBody.contains('hardKillProcess'), isTrue);

      final fullExitIdx = kt.indexOf('"fullExit"');
      final block = kt.substring(
        fullExitIdx,
        (fullExitIdx + 800).clamp(0, kt.length),
      );
      expect(block.contains('result.success'), isTrue);
      expect(block.contains('fullProcessExit()'), isTrue);
      expect(
        block.indexOf('result.success'),
        lessThan(block.indexOf('fullProcessExit()')),
      );

      final sendIdx = kt.indexOf('private fun sendDisconnect');
      expect(sendIdx, greaterThanOrEqualTo(0));
      final sendBody =
          kt.substring(sendIdx, (sendIdx + 700).clamp(0, kt.length));
      expect(
        sendBody.contains('startForegroundService'),
        isFalse,
        reason: 'sendDisconnect must use plain startService only',
      );
      expect(sendBody.contains('startService'), isTrue);
      expect(sendBody.contains('ACTION_DISCONNECT'), isTrue);
    });
  });
}
