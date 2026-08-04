import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('FirstRunPortal shows Step 1 licence and Step 2 KEYGEN headlines', () {
    final src = File('lib/first_run_portal.dart').readAsStringSync();
    expect(src.contains('Step 1 of 2 — Accept the end-user licence'), isTrue);
    expect(src.contains('Step 2 of 2 — KEYGEN or free trial'), isTrue);
    expect(src.contains('first_run_step_label_'), isTrue);
    expect(src.contains('_stepHeadline'), isTrue);
  });

  test('RptVpnChannel recreates NETunnelProviderProtocol for monopin upgrade', () {
    final src =
        File('macos/NativePrep/RptVpnChannel.swift').readAsStringSync();
    expect(src.contains('fresh'), isTrue);
    expect(src.contains('NETunnelProviderProtocol()'), isTrue);
    // Stale designated requirement from residual-team is the documented failure mode
    expect(src.toLowerCase().contains('designated requirement'), isTrue);
  });
}
