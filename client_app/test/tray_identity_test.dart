import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/tray_identity.dart';

void main() {
  test('tray display name is durable Privacy, Restored', () {
    expect(kTrayDisplayName, 'Privacy, Restored');
    expect(kTrayStatusItemTitle, 'Privacy, Restored');
    expect(kTrayDisplayName.contains(','), isTrue);
  });

  test('tooltip helpers embed Privacy, Restored only', () {
    expect(trayTooltipConnected(), startsWith('Privacy, Restored'));
    expect(trayTooltipDisconnected(), startsWith('Privacy, Restored'));
    expect(trayTooltipSessionOnly(), startsWith('Privacy, Restored'));
    expect(
      trayTooltipForState(connected: true, residual: true),
      trayTooltipConnected(),
    );
    expect(
      trayTooltipForState(connected: false),
      trayTooltipDisconnected(),
    );
  });

  test('platform tray sources pin Privacy, Restored (not rpT0)', () {
    String read(String rel) {
      for (final base in ['', 'client_app/', '../']) {
        final f = File('$base$rel');
        if (f.existsSync()) return f.readAsStringSync();
      }
      final f = File('../$rel');
      if (f.existsSync()) return f.readAsStringSync();
      throw StateError('missing $rel');
    }

    final winTray = read('client/windows/tray_win.py');
    expect(
      RegExp(r'TRAY_DISPLAY_NAME\s*=\s*"Privacy, Restored"').hasMatch(winTray),
      isTrue,
    );
    expect(RegExp(r'TRAY_DISPLAY_NAME\s*=\s*"rpT0"').hasMatch(winTray), isFalse);

    final macTray = read('client_app/macos/Runner/RptTrayController.swift');
    expect(macTray.contains('trayDisplayName = "Privacy, Restored"'), isTrue);
    expect(macTray.contains('trayDisplayName = "rpT0"'), isFalse);

    final dart = read('client_app/lib/tray_identity.dart');
    expect(dart.contains("kTrayDisplayName = 'Privacy, Restored'"), isTrue);
    expect(dart.contains("kTrayDisplayName = 'rpT0'"), isFalse);
  });
}
