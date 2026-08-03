/// Dedicated residual VPN product: first-use + chrome locks.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/first_run_gate.dart';
import 'package:restore_privacy_client/suite_nav.dart';
import 'package:restore_privacy_client/suite_parts.dart';

void main() {
  test('first-use steps never include account or seed', () {
    expect(FirstRunStep.values, [
      FirstRunStep.licence,
      FirstRunStep.keygenOrTrial,
      FirstRunStep.complete,
    ]);
  });

  test('shell destinations always VPN only', () {
    expect(
      suiteNavDestinations(SuitePartsState.allInstalled),
      [SuiteNavDest.vpn],
    );
    expect(
      suiteNavDestinations(SuitePartsState.vpnOnly),
      [SuiteNavDest.vpn],
    );
  });

  test('fromJson cannot re-enable Suite family parts', () {
    expect(
      SuitePartsState.fromJson({
        kKeySuitePartWallet: true,
        kKeySuitePartEvolve: true,
        kKeySuitePartRpai: true,
      }),
      SuitePartsState.vpnOnly,
    );
  });

  test('source locks: no first-run username/password UI', () {
    String read(String rel) {
      for (final base in ['', 'client_app/']) {
        final f = File('$base$rel');
        if (f.existsSync()) return f.readAsStringSync();
      }
      throw StateError('missing $rel');
    }

    final portal = read('lib/first_run_portal.dart');
    final gate = read('lib/first_run_gate.dart');
    final entry = read('lib/entry_access.dart');
    final nav = read('lib/suite_nav.dart');

    expect(portal.contains('FirstRunStep.account'), isFalse);
    expect(portal.contains('_buildAccountStep'), isFalse);
    expect(portal.contains('_buildSeedStep'), isFalse);
    expect(portal.contains('kFirstRunKeygenStepTitle'), isTrue);
    expect(portal.contains('TextAlign.justify'), isTrue);
    expect(gate.contains('keygenOrTrial'), isTrue);
    expect(gate.contains('mayEnterVpnShellOnReturn'), isTrue);
    expect(entry.contains('paymentAllowsConnect'), isTrue);
    expect(nav.contains('[SuiteNavDest.vpn]'), isTrue);
  });
}
