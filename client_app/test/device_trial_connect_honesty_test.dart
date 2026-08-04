/// Trial-expired vs Packet Tunnel fail honesty (shipped helpers).
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/connect_status.dart';
import 'package:restore_privacy_client/licence_gate.dart';

void main() {
  test('trial expired unlock copy is purchase-oriented', () {
    expect(kTrialExpiredUnlockMsg.toLowerCase(), contains('trial'));
    expect(kTrialExpiredUnlockMsg.toLowerCase(), contains('keygen'));
    expect(kTrialExpiredUnlockMsg.contains('Packet Tunnel'), isFalse);
    expect(kTrialExpiredUnlockMsg.contains('sign_macos_residual'), isFalse);
  });

  test('assigned-node tunnel fail is not trial-expired copy', () {
    final map = buildFullTunnelConnectResult(
      packetTunnelActive: false,
      vpnIp: '10.88.0.109',
      hostOnlyHello: true,
      detailMessage:
          'Packet Tunnel did not become Connected (status disconnected/1). '
          'Open System Settings → Network → VPN & Filters.',
    );
    final msg = mapConnectStatusMessage(map);
    expect(msg.toLowerCase().contains('trial has ended'), isFalse);
    expect(msg, isNot(equals(kTrialExpiredUnlockMsg)));
    expect(msg, contains('10.88.0.109'));
    expect(msg, contains('VPN'));
  });

  test('device trial cache expired is pure and local', () {
    expect(
      deviceTrialCacheAllowsConnect(
        status: kDeviceTrialStatusActive,
        endsAt: 100,
        nowSec: 200,
      ),
      isFalse,
    );
    expect(
      deviceTrialCacheAllowsConnect(
        status: kDeviceTrialStatusExpired,
        endsAt: 999999,
        nowSec: 1,
      ),
      isFalse,
    );
    expect(
      deviceTrialCacheAllowsConnect(
        status: kDeviceTrialStatusActive,
        endsAt: 300,
        nowSec: 100,
      ),
      isTrue,
    );
  });
}
