import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/rpt_config.dart';
import 'package:restore_privacy_client/theme.dart';
import 'package:restore_privacy_client/vpn_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('restore_privacy/vpn');
  var statusConnected = false;

  setUp(() {
    // Pre-accept licence + active payment so Connect is not blocked by gates.
    SharedPreferences.setMockInitialValues({
      'licence_accepted': true,
      'licence_id': 'FULL-COPYRIGHT-2026',
      'licence_accepted_at': '1',
      'payment_entitlement_status': 'active',
      'payment_entitlement_session_id': 'cs_test_widget',
      'payment_entitlement_keygen': 'RPT-KEY-TEST-TEST-TEST',
    });
    statusConnected = false;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      // Settings → App Group sync (load / Connect / Settings switches).
      if (call.method == 'setResidualStack' || call.method == 'setPrivacyScale') {
        return {'ok': true};
      }
      if (call.method == 'connect') {
        statusConnected = true;
        return {
          'ok': true,
          'message': 'Connected — VPN active; IPv6 ISP path blocked (10.88.0.2)',
          'vpnIp': '10.88.0.2',
          'fullTunnelActive': true,
          'connected': true,
          'hostOnlySession': false,
          'ipv6Protected': true,
          'ipv4Residual': true,
        };
      }
      if (call.method == 'disconnect') {
        statusConnected = false;
        return {
          'ok': true,
          'message': 'Disconnected — system VPN stopped; residual public IP restored',
          'connected': false,
          'fullTunnelActive': false,
        };
      }
      if (call.method == 'status') {
        return {
          'ok': statusConnected,
          'connected': statusConnected,
          'fullTunnelActive': statusConnected,
          'vpnIp': statusConnected ? '10.88.0.2' : '',
          'message': statusConnected
              ? 'Connected — VPN active; IPv6 ISP path blocked (10.88.0.2)'
              : 'Disconnected',
          if (statusConnected) 'ipv6Protected': true,
          if (statusConnected) 'ipv4Residual': true,
        };
      }
      // prepareVpn / openVpnSettings / other optional methods
      if (call.method == 'prepareVpn' ||
          call.method == 'preparePacketTunnel' ||
          call.method == 'registerVpnConfiguration') {
        return {
          'ok': true,
          'prepared': true,
          'tunnelType': 'packet-tunnel',
        };
      }
      return {'ok': true};
    });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  testWidgets('UI has title, logo chrome, status card, Connect, and settings cog', (tester) async {
    await tester.pumpWidget(const RestorePrivacyApp());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text(kAppTitle), findsWidgets);
    expect(find.text(kBannerTitle), findsOneWidget);
    expect(kBannerTitle.contains('Virtual Private Network'), isTrue);
    expect(kBannerTitle.toLowerCase().contains('uk vpn'), isFalse);
    expect(find.text(connectButtonLabel(false)), findsOneWidget);
    expect(find.textContaining('lightweight vpn to restore your privacy'), findsWidgets);
    expect(find.byIcon(Icons.settings), findsOneWidget);
    final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
    expect(scaffold.backgroundColor, kChromeBg);
  });

  testWidgets('Connect then Disconnect invoke channel methods', (tester) async {
    await tester.pumpWidget(const RestorePrivacyApp());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pumpAndSettle();

    // If sheet still open, accept with the real button label.
    final acceptBtn = find.text('Accept licence');
    if (acceptBtn.evaluate().isNotEmpty) {
      await tester.tap(acceptBtn);
      await tester.pumpAndSettle();
    }

    expect(find.text(connectButtonLabel(false)), findsOneWidget);
    await tester.ensureVisible(find.text(connectButtonLabel(false)));
    await tester.tap(find.text(connectButtonLabel(false)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    expect(find.text(connectButtonLabel(true)), findsOneWidget);

    await tester.tap(find.text(connectButtonLabel(true)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pumpAndSettle();

    expect(find.text(connectButtonLabel(false)), findsOneWidget);
  });

  test('connectButtonLabel toggles', () {
    expect(connectButtonLabel(false), 'Connect');
    expect(connectButtonLabel(true), 'Disconnect');
  });

  test('product policy: no auto-connect on launch', () {
    expect(RptConfig.autoConnectOnLaunch, isFalse);
    expect(VpnController.autoConnectOnLaunchEnabled, isFalse);
  });
}
