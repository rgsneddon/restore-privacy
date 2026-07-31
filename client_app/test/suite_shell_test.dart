import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/suite_network_config.dart';
import 'package:restore_privacy_client/suite_shell.dart';
import 'package:restore_privacy_client/suite_version.dart';
import 'package:restore_privacy_client/theme.dart';

/// Primary surface markers for each suite tab (not stubs).
class _VpnSurface extends StatelessWidget {
  const _VpnSurface();
  @override
  Widget build(BuildContext context) => const Scaffold(
        body: Center(child: Text('VPN_SURFACE_CONNECT')),
      );
}

class _WalletSurface extends StatelessWidget {
  const _WalletSurface();
  @override
  Widget build(BuildContext context) => const Scaffold(
        body: Center(child: Text('WALLET_SURFACE_BOOTSTRAP')),
      );
}

class _EvolveSurface extends StatelessWidget {
  const _EvolveSurface();
  @override
  Widget build(BuildContext context) => const Scaffold(
        body: Center(child: Text('EVOLVE_SURFACE_HOME')),
      );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('restore_privacy/vpn');

  setUp(() {
    SharedPreferences.setMockInitialValues({
      'licence_accepted': true,
      'licence_id': 'FULL-COPYRIGHT-2026',
      'licence_accepted_at': '1',
      'payment_entitlement_status': 'active',
      'payment_entitlement_session_id': 'cs_test_suite',
      'payment_entitlement_keygen': 'RPT-KEY-TEST-TEST-TEST',
    });
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'status') {
        return {
          'ok': false,
          'connected': false,
          'fullTunnelActive': false,
          'message': 'Disconnected',
        };
      }
      return {'ok': true};
    });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  test('suite version monopin is 1.0.0 Restore Privacy Suite', () {
    expect(kSuiteVersion, '1.0.0');
    expect(kSuiteProductName, 'Restore Privacy Suite');
    expect(kSuiteDisplayVersion, 'Restore Privacy Suite v 1.0.0');
    expect(kSuiteTabLabels, ['VPN', '%', 'EVOLVE']);
    expect(kSuiteTabVpn, 'VPN');
    expect(kSuiteTabWallet, '%');
    expect(kSuiteTabEvolve, 'EVOLVE');
  });

  test('suite network defaults to Helsinki, not paused Render', () {
    final url = resolveSuiteRendezvousUrl();
    expect(url, contains('135.181.152.10'));
    expect(url, contains('/perc'));
    expect(url.startsWith('https://'), isTrue);
    expect(isPausedRenderPercInternet(url), isFalse);
    expect(isPausedRenderPercInternet(kPausedRenderPercInternet), isTrue);
    expect(kPercInternetPausedNote.toLowerCase(), contains('paused'));
    final json = suitePercNetworkJson();
    expect(json['rendezvousUrl'], url);
    expect(
      (json['rendezvousUrl'] as String).contains('onrender.com'),
      isFalse,
    );
  });

  test('env override for rendezvous is honored', () {
    final u = resolveSuiteRendezvousUrl(override: 'http://example.test:9/');
    expect(u, 'http://example.test:9');
  });

  testWidgets('shell declares VPN, %, EVOLVE tabs and switches surfaces',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SuiteShell(
          vpnTab: const _VpnSurface(),
          walletTab: const _WalletSurface(),
          evolveTab: const _EvolveSurface(),
        ),
      ),
    );
    await tester.pump();

    // Chrome branding.
    expect(find.text(kSuiteProductName), findsOneWidget);
    expect(find.text(kSuiteDisplayVersion), findsOneWidget);

    // Navigation destinations with exact labels.
    expect(find.text('VPN'), findsWidgets);
    expect(find.text('%'), findsWidgets);
    expect(find.text('EVOLVE'), findsWidgets);

    // Default tab = VPN primary surface.
    expect(find.text('VPN_SURFACE_CONNECT'), findsOneWidget);
    expect(find.text('WALLET_SURFACE_BOOTSTRAP'), findsNothing);
    expect(find.text('EVOLVE_SURFACE_HOME'), findsNothing);

    // Select % tab.
    final shell = tester.state<SuiteShellState>(find.byType(SuiteShell));
    shell.selectTab(1);
    await tester.pump();
    expect(shell.currentTabIndex, 1);
    expect(find.text('WALLET_SURFACE_BOOTSTRAP'), findsOneWidget);
    expect(find.text('VPN_SURFACE_CONNECT'), findsNothing);

    // Select EVOLVE tab.
    shell.selectTab(2);
    await tester.pump();
    expect(shell.currentTabIndex, 2);
    expect(find.text('EVOLVE_SURFACE_HOME'), findsOneWidget);
    expect(find.text('WALLET_SURFACE_BOOTSTRAP'), findsNothing);

    // Back to VPN without process restart.
    shell.selectTab(0);
    await tester.pump();
    expect(find.text('VPN_SURFACE_CONNECT'), findsOneWidget);
  });

  testWidgets('NavigationBar taps switch tabs', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SuiteShell(
          vpnTab: const _VpnSurface(),
          walletTab: const _WalletSurface(),
          evolveTab: const _EvolveSurface(),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('%').last);
    await tester.pump();
    expect(find.text('WALLET_SURFACE_BOOTSTRAP'), findsOneWidget);

    await tester.tap(find.text('EVOLVE').last);
    await tester.pump();
    expect(find.text('EVOLVE_SURFACE_HOME'), findsOneWidget);
  });

  testWidgets('RestorePrivacyApp hosts suite shell with real VPN home',
      (tester) async {
    await tester.pumpWidget(
      RestorePrivacyApp(
        walletTab: const _WalletSurface(),
        evolveTab: const _EvolveSurface(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.byType(SuiteShell), findsOneWidget);
    expect(find.text(kSuiteDisplayVersion), findsWidgets);
    // VPN residual chrome still present on default tab.
    expect(find.text(kBannerTitle), findsOneWidget);
    expect(find.text(connectButtonLabel(false)), findsOneWidget);
  });
}
