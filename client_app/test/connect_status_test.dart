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

    test('connecting map is not product success (Android long HELLO)', () {
      expect(
        isConnectSuccess({
          'ok': true,
          'connecting': true,
          'message': 'VPN still connecting…',
          'fullTunnelActive': false,
        }),
        isFalse,
      );
      expect(
        isConnectSuccess({
          'ok': false,
          'connecting': true,
          'message': 'VPN still connecting — waiting for full tunnel…',
        }),
        isFalse,
      );
      expect(
        isConnectingInProgress({
          'connecting': true,
          'message': 'VPN still connecting…',
        }),
        isTrue,
      );
    });

    test('status card title stays Connecting while busy', () {
      expect(
        statusCardTitle(connected: false, busyConnecting: true),
        kConnectingTitle,
      );
      expect(
        statusCardTitle(connected: false, busyConnecting: false),
        'Disconnected',
      );
      expect(
        statusCardTitle(
          connected: true,
          busyConnecting: false,
          vpnIp: '10.88.0.2',
        ),
        contains('10.88.0.2'),
      );
      final msg = connectingStatusMessage(
        host: '82.221.101.241',
        port: 44044,
        elapsedSeconds: 12,
      );
      expect(msg, contains('Connecting'));
      expect(msg, contains('12s'));
      expect(msg, contains('full tunnel'));
    });

    test('does not invent Connected on failure', () {
      final msg = mapConnectStatusMessage({
        'ok': false,
        'message': kMissingSecretsMessage,
      });
      expect(msg, contains('node_elgamal.pub'));
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
      expect(map['ipv6Protected'], isFalse);
      expect(isConnectSuccess(map), isTrue);
      final msg = mapConnectStatusMessage(map);
      expect(msg, contains('10.88.0.19'));
      // Apple residual honesty: IPv4 via VPN; no IPv6 kill-switch claim
      expect(msg, contains('IPv6 not protected'));
      expect(msg.toLowerCase(), isNot(contains('ipv6 isp path blocked')));
      // macOS hide-to-tray only after product full-tunnel success
      expect(shouldHideToTrayAfterConnect(map), isTrue);
      expect(shouldHideToTrayAfterConnectSuccess(true), isTrue);
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
      // Must NOT hide to tray on failed Packet Tunnel
      expect(shouldHideToTrayAfterConnect(map), isFalse);
      expect(shouldHideToTrayAfterConnectSuccess(false), isFalse);
    });

    test('host-only HELLO does not hide to tray', () {
      final map = buildFullTunnelConnectResult(
        packetTunnelActive: false,
        vpnIp: '10.88.0.18',
        hostOnlyHello: true,
      );
      expect(isConnectSuccess(map), isFalse);
      expect(shouldHideToTrayAfterConnect(map), isFalse);
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

    test('disconnect map is not product connect success', () {
      final map = {
        'ok': true,
        'message': kDisconnectedResidualIpMessage,
        'fullTunnelActive': false,
        'hostOnlySession': false,
      };
      expect(isConnectSuccess(map), isFalse);
      expect(mapConnectStatusMessage(map).toLowerCase(), contains('residual public ip'));
    });
  });

  group('app lifecycle must not auto-stop tunnel', () {
    test('close/background/detach never auto-disconnect (user uses Disconnect button)', () {
      // Product roll-back: tunnel stays up until explicit Disconnect.
      expect(shouldStopTunnelOnAppLifecycle('detached'), isFalse);
      expect(shouldStopTunnelOnAppLifecycle('AppLifecycleState.detached'), isFalse);
      expect(shouldStopTunnelOnAppLifecycle('paused'), isFalse);
      expect(shouldStopTunnelOnAppLifecycle('AppLifecycleState.paused'), isFalse);
      expect(shouldStopTunnelOnAppLifecycle('inactive'), isFalse);
      expect(shouldStopTunnelOnAppLifecycle('resumed'), isFalse);
    });

    test('disconnectResultMap contract is not product success (shipped helper)', () {
      // Mirrors native RptFullTunnelResult.disconnectResultMap fields.
      final map = {
        'ok': true,
        'message': kDisconnectedResidualIpMessage,
        'fullTunnelActive': false,
        'hostOnlySession': false,
      };
      expect(isConnectSuccess(map), isFalse);
      expect(mapConnectStatusMessage(map), kDisconnectedResidualIpMessage);
    });
  });
}
