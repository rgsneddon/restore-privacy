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

  test('sanitizeStatusForPrint preserves ASCII compound hyphens and URLs', () {
    // Skeptic bar: bare compound and hyphenated host must be unchanged.
    expect(sanitizeStatusForPrint('end-user'), 'end-user');
    expect(
      sanitizeStatusForPrint('https://a-b.example/path-name'),
      'https://a-b.example/path-name',
    );

    // Real path: autoconnect append mentions end-user licence.
    const compound =
        'Settings: autoconnect skipped - accept the end-user licence first.';
    expect(sanitizeStatusForPrint(compound), compound);
    expect(sanitizeStatusForPrint(compound), contains('end-user'));
    expect(sanitizeStatusForPrint(compound), isNot(contains('end - user')));

    const url =
        'Could not open browser. Visit: https://restoreprivacy.online/pay?product=suite';
    expect(sanitizeStatusForPrint(url), url);
    expect(
      sanitizeStatusForPrint(url),
      contains('https://restoreprivacy.online/pay'),
    );
    expect(
      sanitizeStatusForPrint(url),
      isNot(contains('restoreprivacy.online/pay - ')),
    );

    // Em dash still becomes spaced ASCII separator; ASCII hyphens nearby stay put.
    final mixed = sanitizeStatusForPrint(
      'end-user licence \u2014 then visit https://a-b.example/path-name',
    );
    expect(mixed, contains('end-user'));
    expect(mixed, isNot(contains('end - user')));
    expect(mixed, contains('https://a-b.example/path-name'));
    expect(mixed, contains(' - ')); // only from the em dash
    expect(mixed, isNot(contains('\u2014')));
  });

  test('sanitizeStatusForPrint source has no global ASCII-hyphen re-space', () {
    final f = File('lib/connect_status.dart');
    final src = f.readAsStringSync();
    final start = src.indexOf('String sanitizeStatusForPrint');
    expect(start, greaterThanOrEqualTo(0));
    final end = src.indexOf('\n}\n', start);
    final body = src.substring(start, end > start ? end : src.length);
    // Forbidden: rewrite every hyphen with surrounding whitespace.
    expect(body.contains(r'[ \t]*-[ \t]*'), isFalse);
    // Must still target em dash / mojibake forms (not plain ASCII '-').
    expect(body.contains(r'\u2014'), isTrue);
    expect(body.contains(r'\u2013'), isTrue);
    // Doc above the function states the end-user / URL preservation rule.
    final docStart = src.lastIndexOf('/// Normalize punctuation', start);
    expect(docStart, greaterThanOrEqualTo(0));
    final doc = src.substring(docStart, start);
    expect(doc.contains('end-user'), isTrue);
    expect(doc.toLowerCase(), contains('does not'));
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
