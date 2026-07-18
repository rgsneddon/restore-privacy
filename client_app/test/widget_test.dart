import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/theme.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('restore_privacy/vpn');

  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'connect') {
        return {
          'ok': true,
          'message': 'Connected — test harness',
          'vpnIp': '10.88.0.2',
          'fullTunnelActive': true,
        };
      }
      if (call.method == 'disconnect') {
        return {'ok': true, 'message': 'Disconnected'};
      }
      return null;
    });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  testWidgets('UI has title, logo chrome, log, and Connect button', (tester) async {
    await tester.pumpWidget(const RestorePrivacyApp());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text(kAppTitle), findsWidgets); // title + log line
    expect(find.text(kBannerTitle), findsOneWidget);
    expect(find.text(connectButtonLabel(false)), findsOneWidget);
    expect(find.textContaining('lightweight vpn to restore your privacy'), findsWidgets);
    // Dark blue chrome background
    final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
    expect(scaffold.backgroundColor, kChromeBg);
  });

  testWidgets('Connect button invokes channel connect', (tester) async {
    await tester.pumpWidget(const RestorePrivacyApp());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    await tester.tap(find.text(connectButtonLabel(false)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // After successful connect, label flips to Disconnect
    expect(find.text(connectButtonLabel(true)), findsOneWidget);
  });

  test('connectButtonLabel toggles', () {
    expect(connectButtonLabel(false), 'Connect');
    expect(connectButtonLabel(true), 'Disconnect');
  });
}
