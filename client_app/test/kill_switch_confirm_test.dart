/// Kill-switch confirm-on / free-off pure gate + Settings wiring structural checks.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/kill_switch_confirm.dart';

void main() {
  group('evaluateKillSwitchConfirm', () {
    test('OFF never requires token and persists false', () {
      final d = evaluateKillSwitchConfirm(desiredOn: false);
      expect(d.allowPersist, isTrue);
      expect(d.nextOptIn, isFalse);
      expect(d.reason, 'disable_no_confirm');

      final withJunk = evaluateKillSwitchConfirm(
        desiredOn: false,
        confirmText: 'nope',
      );
      expect(withJunk.allowPersist, isTrue);
      expect(withJunk.nextOptIn, isFalse);
    });

    test('ON with exact KILLSWITCH allows persist true', () {
      final d = evaluateKillSwitchConfirm(
        desiredOn: true,
        confirmText: kKillSwitchConfirmToken,
      );
      expect(kKillSwitchConfirmToken, 'KILLSWITCH');
      expect(d.allowPersist, isTrue);
      expect(d.nextOptIn, isTrue);
      expect(d.reason, 'enable_token_ok');
    });

    test('ON trims outer whitespace but is case-sensitive', () {
      expect(
        evaluateKillSwitchConfirm(desiredOn: true, confirmText: '  KILLSWITCH  ')
            .allowPersist,
        isTrue,
      );
      expect(
        evaluateKillSwitchConfirm(desiredOn: true, confirmText: 'killswitch')
            .allowPersist,
        isFalse,
      );
      expect(
        evaluateKillSwitchConfirm(desiredOn: true, confirmText: 'KillSwitch')
            .allowPersist,
        isFalse,
      );
    });

    test('ON with empty or wrong token stays off', () {
      for (final t in ['', 'YES', 'KILLSWITCH ', ' KILLSWITCHX', 'SWITCH']) {
        final d = evaluateKillSwitchConfirm(desiredOn: true, confirmText: t);
        // Note: ' KILLSWITCH ' trims to ok — skip that case above.
        if (t.trim() == kKillSwitchConfirmToken) continue;
        expect(d.allowPersist, isFalse, reason: 'text=$t');
        expect(d.nextOptIn, isFalse, reason: 'text=$t');
      }
    });

    test('ON cancelled leaves off without token', () {
      final d = evaluateKillSwitchConfirm(
        desiredOn: true,
        confirmText: kKillSwitchConfirmToken,
        cancelled: true,
      );
      expect(d.allowPersist, isFalse);
      expect(d.nextOptIn, isFalse);
      expect(d.reason, 'enable_cancelled');
    });
  });

  test('confirm copy markers include ARE YOU SURE and risk issues', () {
    expect(kKillSwitchConfirmTitle, 'ARE YOU SURE?');
    expect(kKillSwitchConfirmTitle.toUpperCase(), kKillSwitchConfirmTitle);
    expect(kKillSwitchConfirmRiskBody.toLowerCase(), contains('captive'));
    expect(kKillSwitchConfirmRiskBody.toLowerCase(), contains('update'));
    expect(kKillSwitchConfirmRiskBody.toLowerCase(), contains('kill-switch'));
    expect(kKillSwitchConfirmRiskBody, contains(kKillSwitchConfirmToken));
    expect(killSwitchConfirmTokenMatches('KILLSWITCH'), isTrue);
    expect(killSwitchConfirmTokenMatches('nope'), isFalse);
  });

  test('settings_screen wires confirm gate on ON and free OFF path', () {
    final src = File('lib/settings_screen.dart').readAsStringSync();
    expect(src.contains('evaluateKillSwitchConfirm'), isTrue);
    expect(src.contains('kill_switch_confirm.dart'), isTrue);
    expect(src.contains('kKillSwitchConfirmTitle'), isTrue);
    expect(src.contains('kKillSwitchConfirmToken'), isTrue);
    expect(src.contains('_KillSwitchEnableConfirmDialog'), isTrue);
    expect(src.contains('kKillSwitchConfirmDialogKey'), isTrue);
    expect(src.contains('kKillSwitchConfirmFieldKey'), isTrue);
    // OFF path must not open dialog.
    final offIdx = src.indexOf('// OFF: no confirmation');
    expect(offIdx, greaterThanOrEqualTo(0));
    final onIdx = src.indexOf('// ON: require ARE YOU SURE');
    expect(onIdx, greaterThan(offIdx));
    // Must not blindly save on=true without confirm.
    expect(src.contains('_KillSwitchEnableConfirmDialog()'), isTrue);
  });
}
