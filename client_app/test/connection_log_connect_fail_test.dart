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

    test('UDP timeout export prefers keygen/entitlement primary when residual-capable',
        () {
      // Residual-team PT boilerplate mentions sign_macos_residual_team as a tip
      // only — must NOT strip Node diagnostic / keygen.
      const status =
          'System VPN (Packet Tunnel) did not become active — residual public IP will not change. '
          'Allow VPN for Restore Privacy in System Settings → Network → VPN & Filters '
          '(and Login Items & Extensions if prompted). Settings opens when possible — then '
          'press Connect again. Residual Packet Tunnel needs a Team-signed host + appex with '
          'Network Extension (developers: scripts/sign_macos_residual_team.py). '
          'Node diagnostic: Connect failed to 5.161.242.85:44044: UDP receive timeout — residual HELLO got no reply. '
          'Product residual nodes refuse HELLO until this device is bound to an active paid entitlement. '
          'If you just paid: enter the keygen';
      final msg = connectionLogConnectFailureMessage(status);
      expect(msg.toLowerCase(), contains('udp receive timeout'));
      expect(msg.toLowerCase(), contains('keygen'));
      expect(msg.toLowerCase(), contains('entitlement'));
      expect(msg.toLowerCase(), contains('node diagnostic:'));
      // Not collapsed to bare PT tip-only line
      expect(
        msg.toLowerCase().startsWith('system vpn (packet tunnel) did not become active'),
        isFalse,
        reason: 'residual-capable export must not drop Node diagnostic for PT tips',
      );
      expect(msg.toLowerCase(), isNot(equals('connect failed')));
    });

    test('PT tip boilerplate alone is not treated as missing host NE export', () {
      // kPacketTunnelNotActiveMessage body (residual-capable tip)
      const tipOnly =
          'System VPN (Packet Tunnel) did not become active — residual public IP will not change. '
          'Residual Packet Tunnel needs a Team-signed host + appex with Network Extension '
          '(developers: scripts/sign_macos_residual_team.py).';
      final msg = connectionLogConnectFailureMessage(tipOnly);
      expect(msg, tipOnly);
      expect(
        collapseConnectFailurePrimaryForExport(tipOnly),
        tipOnly,
      );
    });

    test('multi-fault public DevID export collapses to host NE primary', () {
      const multi =
          'System VPN (Packet Tunnel) did not become active — residual public IP will not change. '
          'Allow VPN for Restore Privacy in System Settings → Network → VPN & Filters. '
          'This app build cannot register or activate Packet Tunnel in Network settings: '
          'the host is missing the packet-tunnel-provider Network Extension entitlement. '
          'Public Developer ID downloads intentionally omit host NE so the app opens for all users. '
          'On a developer Mac, re-sign for residual with: '
          'python3 scripts/sign_macos_residual_team.py --app path/to/restore_privacy_client.app '
          'then relaunch and press Connect. '
          'Node diagnostic: Connect failed to 5.161.242.85:44044: UDP receive timeout';
      final msg = connectionLogConnectFailureMessage(multi);
      expect(msg.toLowerCase(), contains('packet-tunnel-provider'));
      expect(msg.toLowerCase(), contains('sign_macos_residual_team'));
      expect(msg.toLowerCase(), isNot(contains('udp receive timeout')));
      expect(msg.toLowerCase(), isNot(equals('connect failed')));
      expect(
        msg.startsWith('This app build cannot register'),
        isTrue,
        reason: 'primary root cause is missing host NE, not Settings wall',
      );
    });
  });
}
