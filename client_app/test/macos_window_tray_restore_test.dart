import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/macos_window.dart';

void main() {
  group('macWindowRestorePlan (shipped pure helper)', () {
    test('miniaturized window requires deminiaturize and never disconnects', () {
      final plan = macWindowRestorePlan(
        isMiniaturized: true,
        isAppHidden: false,
      );
      expect(plan.deminiaturize, isTrue);
      expect(plan.orderFront, isTrue);
      expect(plan.activateApp, isTrue);
      expect(plan.disconnectTunnel, isFalse);
    });

    test('hide-to-tray (app hidden) unhides without disconnect', () {
      final plan = macWindowRestorePlan(
        isMiniaturized: false,
        isAppHidden: true,
      );
      expect(plan.unhideApp, isTrue);
      expect(plan.deminiaturize, isFalse);
      expect(plan.orderFront, isTrue);
      expect(plan.disconnectTunnel, isFalse);
    });

    test('dock reopen when tray mode or no visible windows', () {
      expect(
        shouldHandleDockReopenToShowWindow(
          trayMode: true,
          hasVisibleWindows: true,
        ),
        isTrue,
      );
      expect(
        shouldHandleDockReopenToShowWindow(
          trayMode: false,
          hasVisibleWindows: false,
        ),
        isTrue,
      );
      expect(
        shouldHandleDockReopenToShowWindow(
          trayMode: false,
          hasVisibleWindows: true,
        ),
        isFalse,
      );
    });
  });

  group('native show-from-tray path (structural, shipped sources)', () {
    late final String traySwift;
    late final String appDelegateSwift;

    setUpAll(() {
      // flutter test cwd is client_app/; also try relative to this file.
      File resolve(String rel) {
        final fromCwd = File(rel);
        if (fromCwd.existsSync()) return fromCwd;
        final here = File.fromUri(Platform.script).parent; // …/test or kernel blob
        final candidate = File('${here.path}/../$rel');
        if (candidate.existsSync()) return candidate;
        // Walk up for client_app/macos
        var dir = Directory.current;
        for (var i = 0; i < 6; i++) {
          final f = File('${dir.path}/$rel');
          if (f.existsSync()) return f;
          final f2 = File('${dir.path}/client_app/$rel');
          if (f2.existsSync()) return f2;
          dir = dir.parent;
        }
        return fromCwd;
      }

      traySwift = resolve('macos/Runner/RptTrayController.swift').readAsStringSync();
      appDelegateSwift =
          resolve('macos/Runner/AppDelegate.swift').readAsStringSync();
    });

    test('showMainWindow deminiaturizes and orders front', () {
      expect(traySwift, contains('static func showMainWindow'));
      expect(traySwift, contains('deminiaturize'));
      expect(traySwift, contains('makeKeyAndOrderFront'));
      expect(traySwift, contains('orderFrontRegardless'));
      // Body of showMainWindow only (not disconnect menu handler later in file).
      final start = traySwift.indexOf('static func showMainWindow');
      expect(start, greaterThanOrEqualTo(0));
      final body = traySwift.substring(start, start + 900);
      expect(body, contains('deminiaturize'));
      expect(body.toLowerCase(), isNot(contains('requestflutterdisconnect')));
      expect(body, isNot(contains('terminate')));
    });

    test('tray Show / status item invokes showMainWindow not a no-op', () {
      expect(traySwift, contains('func showWindow'));
      expect(traySwift, contains('showMainWindow()'));
      expect(traySwift, contains('requestFlutterShow()'));
      expect(traySwift, contains('case "showFromTray"'));
      // Left-click path
      expect(traySwift, contains('statusItemClicked'));
    });

    test('dock reopen restores window when tray mode or no visible windows', () {
      expect(appDelegateSwift, contains('applicationShouldHandleReopen'));
      expect(appDelegateSwift, contains('showMainWindow'));
      expect(appDelegateSwift, contains('isTrayMode'));
    });

    test('Flutter channel name matches native', () {
      expect(traySwift, contains(kMacWindowChannelName));
    });
  });
}
