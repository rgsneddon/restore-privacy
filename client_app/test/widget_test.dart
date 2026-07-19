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
    SharedPreferences.setMockInitialValues({});
    statusConnected = false;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'connect') {
        statusConnected = true;
        return {
          'ok': true,
          'message': 'Connected — test harness',
          'vpnIp': '10.88.0.2',
          'fullTunnelActive': true,
          'connected': true,
        };
      }
      if (call.method == 'disconnect') {
        statusConnected = false;
        return {
          'ok': true,
          'message': 'Disconnected — system VPN stopped; residual public IP restored',
          'connected': false,
        };
      }
      if (call.method == 'status') {
        return {
          'ok': statusConnected,
          'connected': statusConnected,
          'fullTunnelActive': statusConnected,
          'vpnIp': statusConnected ? '10.88.0.2' : '',
          'message': statusConnected ? 'Connected — protected' : 'Disconnected',
        };
      }
      return null;
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
    expect(find.text(connectButtonLabel(false)), findsOneWidget);
    expect(find.textContaining('lightweight vpn to restore your privacy'), findsWidgets);
    expect(find.byIcon(Icons.settings), findsOneWidget);
    final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
    expect(scaffold.backgroundColor, kChromeBg);
  });

  testWidgets('Connect then Disconnect invoke channel methods', (tester) async {
    await tester.pumpWidget(const RestorePrivacyApp());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    await tester.tap(find.text(connectButtonLabel(false)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text(connectButtonLabel(true)), findsOneWidget);

    await tester.tap(find.text(connectButtonLabel(true)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

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
