/// Print/status window: disconnect lines must be ASCII-safe (no em-dash mojibake).
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/app_quit.dart';
import 'package:restore_privacy_client/connect_status.dart';

void main() {
  test('kDisconnectedResidualIpMessage is ASCII hyphen, not em dash', () {
    expect(kDisconnectedResidualIpMessage, contains('Disconnected - system'));
    expect(kDisconnectedResidualIpMessage, isNot(contains('\u2014')));
    expect(kDisconnectedResidualIpMessage, isNot(contains('â€"')));
    expect(kDisconnectedResidualIpMessage, isNot(contains('å')));
    expect(kDisconnectedResidualIpMessage, isNot(contains('€')));
  });

  test('sanitizeStatusForPrint strips em dash and common mojibake', () {
    final fromEm = sanitizeStatusForPrint(
      'Disconnected \u2014 system VPN stopped; residual public IP restored',
    );
    expect(
      fromEm,
      'Disconnected - system VPN stopped; residual public IP restored',
    );
    expect(fromEm, isNot(contains('\u2014')));

    final fromMojibake = sanitizeStatusForPrint(
      'Disconnected â€” system VPN stopped; residual public IP restored',
    );
    expect(fromMojibake.contains('Disconnected'), isTrue);
    expect(fromMojibake.contains('system VPN stopped'), isTrue);
    expect(fromMojibake, isNot(contains('â')));
    expect(fromMojibake, isNot(contains('\u2014')));

    final ellipsis = sanitizeStatusForPrint('Please wait\u2026');
    expect(ellipsis, 'Please wait...');
  });

  test('Quit shows on every residual TargetPlatform including Android', () {
    for (final p in [
      TargetPlatform.android,
      TargetPlatform.iOS,
      TargetPlatform.macOS,
      TargetPlatform.windows,
      TargetPlatform.linux,
    ]) {
      expect(
        showsMainScreenQuitForTarget(p),
        isTrue,
        reason: 'Quit missing for $p',
      );
    }
    expect(
      showsMainScreenQuitButton(
        isAndroid: true,
        isMacOS: false,
        isIOS: false,
        isWindows: false,
        isLinux: false,
      ),
      isTrue,
    );
    expect(kQuitButtonLabel, 'Quit');
    expect(kQuitButtonPlacement, 'bottomLeft');
  });

  test('shipped main.dart wires Quit button and disconnect ASCII print lines',
      () {
    // client_app/test -> client_app/lib/main.dart
    final mainFile = File(
      '${Directory.current.path}/lib/main.dart',
    );
    // flutter test cwd is client_app/
    final alt = File('lib/main.dart');
    final src = (mainFile.existsSync() ? mainFile : alt).readAsTextSync();
    expect(src.contains("key: const Key('main_quit_button')"), isTrue);
    expect(src.contains('showsMainScreenQuitOnThisDevice()'), isTrue);
    expect(src.contains('kQuitButtonLabel'), isTrue);
    expect(src.contains('performQuitSequence'), isTrue);
    // Disconnect print path must not embed bare em dash in user-facing lines
    expect(
      src.contains(
        "Disconnected - system VPN stopped. Press Connect when you want protection.",
      ),
      isTrue,
    );
    expect(
      src.contains("Disconnected - system Network VPN off."),
      isTrue,
    );
    expect(src.contains('sanitizeStatusForPrint'), isTrue);
  });

  test('Android MainActivity disconnect message is ASCII hyphen', () {
    final f = File(
      'android/app/src/main/kotlin/com/restoreprivacy/'
      'restore_privacy_client/MainActivity.kt',
    );
    expect(f.existsSync(), isTrue);
    final t = f.readAsStringSync();
    expect(
      t.contains(
        'Disconnected - system VPN stopped; residual public IP restored',
      ),
      isTrue,
    );
    expect(t.contains('\u2014'), isFalse);
    expect(t.contains('â€"'), isFalse);
    expect(t.contains('â€"'), isFalse);
  });
}

extension on File {
  String readAsTextSync() => readAsStringSync();
}
