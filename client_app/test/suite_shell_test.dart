import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/suite_network_config.dart';
import 'package:restore_privacy_client/suite_parts.dart';
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

class _RpaiSurface extends StatelessWidget {
  const _RpaiSurface();
  @override
  Widget build(BuildContext context) => const Scaffold(
        body: Center(child: Text('RPAI_SURFACE_NED')),
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

  test('suite version monopin labels for Restore Privacy Suite', () {
    // Monopin string is owned by suite_version.dart / catalog pin.
    expect(kSuiteVersion, isNotEmpty);
    expect(kSuiteProductName, 'Restore Privacy Suite');
    expect(kSuiteDisplayVersion, contains('Restore Privacy Suite v '));
    expect(kSuiteDisplayVersion, contains(kSuiteVersion));
    expect(kSuiteTabLabels, ['VPN', '%', 'EVOLVE', 'rpAI']);
    expect(kSuiteTabVpn, 'VPN');
    expect(kSuiteTabWallet, '%');
    expect(kSuiteTabEvolve, 'EVOLVE');
    expect(kSuiteTabRpai, 'rpAI');
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

  testWidgets('shell main bar promotes %/Evolve family tabs and switches',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SuiteShell(
          preferInitialParts: true,
          initialParts: SuitePartsState.allInstalled,
          vpnTab: const _VpnSurface(),
          walletTab: const _WalletSurface(),
          evolveTab: const _EvolveSurface(),
          rpaiTab: const _RpaiSurface(),
        ),
      ),
    );
    await tester.pump();

    // Chrome branding.
    expect(find.text(kSuiteProductName), findsOneWidget);
    expect(find.text(kSuiteDisplayVersion), findsOneWidget);

    // Main bar: VPN, promoted family, rpAI — no dual EVOLVE product slot.
    expect(find.text('VPN'), findsWidgets);
    expect(find.text('Wallet'), findsWidgets);
    expect(find.text('Analysis'), findsWidgets);
    expect(find.text('Backup'), findsWidgets);
    expect(find.text('Voting'), findsWidgets);
    expect(find.text('Credit'), findsWidgets);
    expect(find.text('rpAI'), findsWidgets);
    expect(find.text('EVOLVE'), findsNothing);

    // Backup destination uses backup/restore icons (not shield/security).
    final backupDest = tester
        .widgetList<NavigationDestination>(find.byType(NavigationDestination))
        .firstWhere((d) => d.label == 'Backup');
    expect((backupDest.icon as Icon).icon, Icons.backup_outlined);
    expect(
      (backupDest.selectedIcon as Icon).icon,
      Icons.settings_backup_restore,
    );
    expect((backupDest.icon as Icon).icon, isNot(Icons.security));
    expect((backupDest.icon as Icon).icon, isNot(Icons.security_outlined));

    // Default tab = VPN primary surface.
    expect(find.text('VPN_SURFACE_CONNECT'), findsOneWidget);

    final shell = tester.state<SuiteShellState>(find.byType(SuiteShell));
    final dests = shell.destinations;
    expect(dests.first.name, 'vpn');

    // Select Wallet (shared % surface).
    final walletIdx = dests.indexWhere((d) => d.name == 'wallet');
    shell.selectTab(walletIdx);
    await tester.pump();
    expect(find.text('WALLET_SURFACE_BOOTSTRAP'), findsOneWidget);

    // Select Analysis (Evolve-only surface).
    final analysisIdx = dests.indexWhere((d) => d.name == 'analysis');
    shell.selectTab(analysisIdx);
    await tester.pump();
    expect(find.text('EVOLVE_SURFACE_HOME'), findsOneWidget);

    // Select rpAI.
    final rpaiIdx = dests.indexWhere((d) => d.name == 'rpai');
    shell.selectTab(rpaiIdx);
    await tester.pump();
    expect(find.text('RPAI_SURFACE_NED'), findsOneWidget);

    // Back to VPN without process restart.
    shell.selectTab(0);
    await tester.pump();
    expect(find.text('VPN_SURFACE_CONNECT'), findsOneWidget);

    // Only the Suite main NavigationBar.
    expect(find.byType(NavigationBar), findsOneWidget);
  });

  testWidgets('NavigationBar taps switch flat destinations', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SuiteShell(
          preferInitialParts: true,
          initialParts: SuitePartsState.allInstalled,
          vpnTab: const _VpnSurface(),
          walletTab: const _WalletSurface(),
          evolveTab: const _EvolveSurface(),
          rpaiTab: const _RpaiSurface(),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Wallet').last);
    await tester.pump();
    expect(find.text('WALLET_SURFACE_BOOTSTRAP'), findsOneWidget);

    await tester.tap(find.text('Analysis').last);
    await tester.pump();
    expect(find.text('EVOLVE_SURFACE_HOME'), findsOneWidget);

    await tester.tap(find.text('rpAI').last);
    await tester.pump();
    expect(find.text('RPAI_SURFACE_NED'), findsOneWidget);
  });

  testWidgets('RestorePrivacyApp hosts suite shell with real VPN home',
      (tester) async {
    await tester.pumpWidget(
      RestorePrivacyApp(
        entryInitiallyUnlocked: true,
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
