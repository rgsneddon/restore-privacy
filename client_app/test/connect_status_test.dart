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
      });
      expect(msg, contains('10.88.0.5'));
    });
  });
}
