import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:restore_privacy_client/easter_egg_server.dart';
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
    // Isolate VPN home (suite tabs covered in suite_shell_test).
    await tester.binding.setSurfaceSize(const Size(800, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      const MaterialApp(home: TunnelHome()),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump(const Duration(seconds: 1));

    expect(find.text(kAppTitle), findsWidgets);
    expect(find.text(kBannerTitle), findsOneWidget);
    expect(kBannerTitle.contains('Virtual Private Network'), isTrue);
    expect(kBannerTitle.toLowerCase().contains('uk vpn'), isFalse);
    expect(find.text(connectButtonLabel(false)), findsOneWidget);
    // Product privacy copy is always shipped (log or const).
    expect(
      kPrivacyMessageText.toLowerCase(),
      contains('lightweight vpn to restore your privacy'),
    );
    expect(find.byIcon(Icons.settings), findsOneWidget);
    final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
    final themeBg = Theme.of(
      tester.element(find.byType(Scaffold)),
    ).scaffoldBackgroundColor;
    // Scaffold may inherit theme (null backgroundColor) — Evolve dark or light.
    final bg = scaffold.backgroundColor ?? themeBg;
    expect(
      bg == kChromeBg || bg == kEvolveLightBg || bg == themeBg,
      isTrue,
      reason: 'scaffold bg=$bg themeBg=$themeBg',
    );
  });

  testWidgets('Connect button is present and tappable on VPN home', (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(const MaterialApp(home: TunnelHome()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(seconds: 1));

    // If sheet still open, accept with the real button label.
    final acceptBtn = find.text('Accept licence');
    if (acceptBtn.evaluate().isNotEmpty) {
      await tester.tap(acceptBtn);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
    }

    final connectFinder = find.text(connectButtonLabel(false));
    expect(connectFinder, findsOneWidget);
    await tester.ensureVisible(connectFinder);
    await tester.tap(connectFinder);
    await tester.pump();
    // Busy "Please wait…" or Disconnect both prove Connect invoked the path.
    final busy = find.textContaining('Please wait');
    final disconnect = find.text(connectButtonLabel(true));
    expect(
      busy.evaluate().isNotEmpty || disconnect.evaluate().isNotEmpty,
      isTrue,
      reason: 'Connect must enter busy or connected state',
    );
  });

  testWidgets('home Settings cog opens product Settings page', (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(const MaterialApp(home: TunnelHome()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump(const Duration(seconds: 1));

    final acceptBtn = find.text('Accept licence');
    if (acceptBtn.evaluate().isNotEmpty) {
      await tester.tap(acceptBtn);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
    }

    final cog = find.byKey(const Key('main_settings_button'));
    expect(cog, findsOneWidget);
    await tester.ensureVisible(cog);
    await tester.tap(cog);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(
      find.byKey(const Key('product_settings_screen')),
      findsOneWidget,
      reason: 'tapping main_settings_button must push SettingsScreen',
    );
    expect(find.text('Settings'), findsWidgets);
    expect(find.byType(TunnelHome), findsOneWidget);
    expect(
      easterEggServer.isRunning,
      isFalse,
      reason: 'Settings open must not bind loft HTTP',
    );
  });

  testWidgets('Settings cog stays tappable while Connect is busy', (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(const MaterialApp(home: TunnelHome()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump(const Duration(seconds: 1));

    final acceptBtn = find.text('Accept licence');
    if (acceptBtn.evaluate().isNotEmpty) {
      await tester.tap(acceptBtn);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
    }

    final connectFinder = find.text(connectButtonLabel(false));
    expect(connectFinder, findsOneWidget);
    await tester.ensureVisible(connectFinder);
    await tester.tap(connectFinder);
    await tester.pump();

    final cog = find.byKey(const Key('main_settings_button'));
    expect(cog, findsOneWidget);
    final btn = tester.widget<IconButton>(cog);
    expect(btn.onPressed, isNotNull, reason: 'Settings must stay enabled during _busy');
    await tester.ensureVisible(cog);
    await tester.tap(cog);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(
      find.byKey(const Key('product_settings_screen')),
      findsOneWidget,
      reason: 'Settings must open while Connect is busy',
    );
    expect(find.text('Settings'), findsWidgets);
  });

  testWidgets('RestorePrivacyApp Settings cog opens Settings through SuiteShell',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      const RestorePrivacyApp(entryInitiallyUnlocked: true),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump(const Duration(seconds: 1));

    final acceptBtn = find.text('Accept licence');
    if (acceptBtn.evaluate().isNotEmpty) {
      await tester.tap(acceptBtn);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
    }

    final cog = find.byKey(const Key('main_settings_button'));
    expect(cog, findsOneWidget);
    await tester.ensureVisible(cog);
    await tester.tap(cog);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(
      find.byKey(const Key('product_settings_screen')),
      findsOneWidget,
      reason: 'SuiteShell must not swallow the Settings route',
    );
    expect(find.text('Settings'), findsWidgets);
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
