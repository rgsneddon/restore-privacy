import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/connection_log.dart';
import 'package:restore_privacy_client/rpt_config.dart';

void main() {
  group('connection log connect failure detail (shipped helpers)', () {
    test('prefers residual-honest UI status over bare Connect failed', () {
      const native =
          'Packet Tunnel did not become Connected (status disconnected/1). '
          'Allow VPN for Restore Privacy in System Settings.';
      expect(
        connectionLogConnectFailureMessage(native),
        native,
      );
      expect(
        connectionLogConnectFailureMessage(native).toLowerCase(),
        isNot(equals('connect failed')),
      );
    });

    test('empty status falls back to Connect failed', () {
      expect(connectionLogConnectFailureMessage(null), 'Connect failed');
      expect(connectionLogConnectFailureMessage('  '), 'Connect failed');
    });

    test('connecting status is annotated as incomplete tunnel', () {
      final msg = connectionLogConnectFailureMessage(
        'Connecting… full tunnel in progress (12s)',
      );
      expect(msg.toLowerCase(), contains('connect failed'));
      expect(msg.toLowerCase(), contains('did not complete'));
      expect(msg, contains('12s'));
    });

    test('export header embeds product version when ConnectionLog is configured',
        () async {
      final log = ConnectionLog(
        MemoryConnectionLogBackend(),
        clientVersion: RptConfig.displayProductVersion,
        platformLabel: 'macos',
      );
      await log.appendEvent(
        kLogKindError,
        connectionLogConnectFailureMessage(
          'System VPN (Packet Tunnel) did not become active',
        ),
      );
      final body = await log.formatExport();
      expect(body, contains('client_version=${RptConfig.displayProductVersion}'));
      expect(body, isNot(contains('client_version=unknown')));
      expect(body, contains('platform=macos'));
      expect(body, contains('Packet Tunnel'));
      expect(body, isNot(contains('error: Connect failed\n')));
    });
  });
}
