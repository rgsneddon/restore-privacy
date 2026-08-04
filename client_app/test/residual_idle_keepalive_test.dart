/// Lean residual idle keep-alive — structural gates on shipped native sources.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Android residual tunnel schedules RPT2 KEEPALIVE independent of cover', () {
    final svc = File(
      'android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client/RptVpnService.kt',
    ).readAsStringSync();
    final eng = File(
      'android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client/RptClientEngine.kt',
    ).readAsStringSync();
    expect(svc.contains('KEEPALIVE_INTERVAL_MS'), isTrue);
    expect(svc.contains('rpt-keepalive'), isTrue);
    expect(svc.contains('sealAndWrapKeepalive'), isTrue);
    expect(eng.contains('fun packKeepalive'), isTrue);
    expect(eng.contains('0x04'), isTrue);
    // Cover remains opt-in; keep-alive is not gated on productCover.
    final kaStart = svc.indexOf('rpt-keepalive');
    expect(kaStart, greaterThanOrEqualTo(0));
    final kaBody = svc.substring(kaStart, kaStart + 800);
    expect(kaBody.contains('productCover'), isFalse);
  });

  test('Apple Packet Tunnel keep-alive under node idle (macOS + iOS)', () {
    for (final path in [
      'macos/NativePrep/PacketTunnelProvider.swift',
      'ios/NativePrep/PacketTunnelProvider.swift',
    ]) {
      final src = File(path).readAsStringSync();
      expect(src.contains('startKeepalive'), isTrue, reason: path);
      expect(src.contains('residualKeepaliveIntervalSec'), isTrue, reason: path);
      expect(src.contains('sendKeepalive'), isTrue, reason: path);
      expect(
        RegExp(r'residualKeepaliveIntervalSec:\s*TimeInterval\s*=\s*25')
            .hasMatch(src),
        isTrue,
        reason: path,
      );
      // Timer only fires while tunnel running
      final fn = src.indexOf('private func startKeepalive');
      expect(fn, greaterThanOrEqualTo(0), reason: path);
      final body = src.substring(fn, fn + 900);
      expect(body.contains('self.running'), isTrue, reason: path);
    }
  });
}
