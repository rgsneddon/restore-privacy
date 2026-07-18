import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/connect_status.dart';

void main() {
  group('connect status mapping (shipped helper)', () {
    test('success only when ok is true', () {
      expect(isConnectSuccess({'ok': true, 'message': 'Connected'}), isTrue);
      expect(isConnectSuccess({'ok': false, 'message': 'fail'}), isFalse);
      expect(isConnectSuccess(null), isFalse);
      expect(isConnectSuccess('x'), isFalse);
    });

    test('does not invent Connected on failure', () {
      final msg = mapConnectStatusMessage({
        'ok': false,
        'message': kMissingSecretsMessage,
      });
      expect(msg, contains('Missing admission secrets'));
      expect(msg.toLowerCase(), isNot(equals('connected')));
    });

    test('permission denial message preserved', () {
      final msg = mapConnectStatusMessage({
        'ok': false,
        'message': kVpnPermissionDeniedMessage,
      });
      expect(msg, contains('VPN permission denied'));
    });

    test('success includes VPN IP when provided', () {
      final msg = mapConnectStatusMessage({
        'ok': true,
        'message': 'Connected — RPT full tunnel up',
        'vpnIp': '10.88.0.5',
        'fullTunnelActive': true,
      });
      expect(msg, contains('10.88.0.5'));
    });
  });

  group('full-tunnel honesty (residual public IP)', () {
    test('(a) host-only HELLO with vpnIp is not product success', () {
      final map = buildFullTunnelConnectResult(
        packetTunnelActive: false,
        vpnIp: '10.88.0.18',
        hostOnlyHello: true,
      );
      expect(map['ok'], isFalse);
      expect(map['fullTunnelActive'], isFalse);
      expect(map['hostOnlySession'], isTrue);
      expect(map['vpnIp'], '10.88.0.18');
      expect(isConnectSuccess(map), isFalse);
      final msg = mapConnectStatusMessage(map);
      expect(msg.toLowerCase(), contains('residual public ip'));
      expect(msg, isNot(startsWith('Connected')));
      expect(msg, contains('10.88.0.18'));
    });

    test('(b) Packet Tunnel active + vpnIp is product success', () {
      final map = buildFullTunnelConnectResult(
        packetTunnelActive: true,
        vpnIp: '10.88.0.19',
      );
      expect(map['ok'], isTrue);
      expect(map['fullTunnelActive'], isTrue);
      expect(map['hostOnlySession'], isFalse);
      expect(isConnectSuccess(map), isTrue);
      expect(mapConnectStatusMessage(map), contains('10.88.0.19'));
    });

    test('(c) NE start failed is ok:false with residual-IP honest message', () {
      final map = buildFullTunnelConnectResult(
        packetTunnelActive: false,
        detailMessage: 'Packet Tunnel start pending or failed (status 3).',
      );
      expect(map['ok'], isFalse);
      expect(map['fullTunnelActive'], isFalse);
      expect(isConnectSuccess(map), isFalse);
      final msg = mapConnectStatusMessage(map);
      expect(msg, contains('System VPN (Packet Tunnel) did not become active'));
      expect(msg.toLowerCase(), contains('residual public ip'));
      expect(msg, contains('status 3'));
    });

    test('legacy hostOnlySession flag rejects ok:true maps', () {
      expect(
        isConnectSuccess({
          'ok': true,
          'message': 'Connected — tunnel IP 10.88.0.1',
          'vpnIp': '10.88.0.1',
          'hostOnlySession': true,
        }),
        isFalse,
      );
    });

    test('fullTunnelActive false rejects ok:true maps', () {
      expect(
        isConnectSuccess({
          'ok': true,
          'message': 'Connected — tunnel IP 10.88.0.1',
          'vpnIp': '10.88.0.1',
          'fullTunnelActive': false,
        }),
        isFalse,
      );
    });
  });
}
