/// Flat main-bar destinations + reversed swipe + no nested %/Evolve bars.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:evolve/fcg/providers/fcg_voting_provider.dart';
import 'package:evolve/fcg/services/fcg_store_memory.dart';
import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
import 'package:evolve/perc/services/perc_wallet_store_memory.dart';
import 'package:evolve/providers/evolve_provider.dart';
import 'package:evolve/providers/locale_provider.dart' as evolve_locale;
import 'package:evolve/screens/evolve_shell_screen.dart';
import 'package:evolve/services/locale_store_memory.dart';

import 'package:restore_privacy_client/suite_family_host.dart';
import 'package:restore_privacy_client/suite_nav.dart';
import 'package:restore_privacy_client/suite_parts.dart';
import 'package:restore_privacy_client/suite_shell.dart';

/// Deterministic SuiteFamilyHost boot: memory stores, no path_provider, full access.
///
/// Avoids [EvolveProvider.initialize] (Grok proxy timers) and stops inbound
/// polling after register so widget tests do not leave pending Timers.
Future<SuiteFamilyBootReady> suiteFamilyTestBoot() async {
  evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
  evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = false;
  evolve_hub.PercLedgerHub.resetForTest();

  // Defaults only — auto-detect can yield non-standard material locales (en_usa).
  final locale = evolve_locale.LocaleProvider(
    store: LocaleStoreMemory(),
    autoDetectFromDevice: false,
  );
  await locale.initialize();
  // Skip evolve.initialize() — it schedules Grok proxy timers under flutter_test.
  final evolve = EvolveProvider();
  final wallet = evolve_wallet.PercWalletProvider(store: PercWalletStoreMemory());
  final fcg = FcgVotingProvider(store: FcgStoreMemory());

  await wallet.initialize();
  await fcg.initialize();

  // Offline ledger login — full app access without wallet.register network burst
  // (register schedules rendezvous retry timers that outlive widget tests).
  await wallet.setupTreasuryPassword('password12345');
  final ledger = evolve_hub.PercLedgerHub.instance.ledger;
  ledger.register('suite_nav_user', 'password12345');
  ledger.login('suite_nav_user', 'password12345');
  // Full-access maps: Analysis=0, Wallet=1 (entitled evolve shell indices).
  expect(wallet.hasAppAccess, isTrue);

  evolve.setLocale(locale.config);
  return SuiteFamilyBootReady.evolve(
    evolve: evolve,
    evolveWallet: wallet,
    fcg: fcg,
    evolveLocale: locale,
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
    evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = false;
  });

  tearDown(() {
    evolve_wallet.PercWalletProvider.sessionTimeoutEnabled = true;
    evolve_hub.PercLedgerHub.resetForTest();
  });

  group('suiteNavDestinations', () {
    test('suiteNavLabel maps security dest to Backup (not Security)', () {
      expect(suiteNavLabel(SuiteNavDest.security), 'Backup');
      expect(suiteNavLabel(SuiteNavDest.security), isNot('Security'));
    });

    test('product chrome is VPN only regardless of install flags', () {
      for (final parts in [
        SuitePartsState.allInstalled,
        SuitePartsState.vpnAndRpai,
        SuitePartsState.vpnOnly,
      ]) {
        final d = suiteNavDestinations(parts);
        final labels = d.map(suiteNavLabel).toList();
        expect(labels, ['VPN'], reason: '$parts');
        expect(labels, isNot(contains('rpAI')));
        expect(labels, isNot(contains('Wallet')));
        expect(labels, isNot(contains('Analysis')));
        expect(d.where(suiteNavIsPercentEvolveFamily), isEmpty);
      }
    });

    test('wallet install flags cannot expand product bar', () {
      const parts = SuitePartsState(
        walletInstalled: true,
        evolveInstalled: false,
        rpaiInstalled: true,
      );
      final labels = suiteNavDestinations(parts).map(suiteNavLabel).toList();
      expect(labels, ['VPN']);
    });

    test('rpAI flag alone still VPN only', () {
      const parts = SuitePartsState(
        walletInstalled: false,
        evolveInstalled: false,
        rpaiInstalled: true,
      );
      expect(
        suiteNavDestinations(parts).map(suiteNavLabel).toList(),
        ['VPN'],
      );
    });

    test('only VPN: single destination (shell omits NavigationBar)', () {
      const parts = SuitePartsState(
        walletInstalled: false,
        evolveInstalled: false,
        rpaiInstalled: false,
      );
      final d = suiteNavDestinations(parts);
      expect(d, [SuiteNavDest.vpn]);
      expect(d.length, 1);
    });

    test('!hasAppAccess still VPN only (product chrome)', () {
      final d = suiteNavDestinations(
        SuitePartsState.allInstalled,
        hasAppAccess: false,
      );
      final labels = d.map(suiteNavLabel).toList();
      expect(labels, ['VPN']);
      expect(labels, isNot(contains('Analysis')));
      expect(labels, isNot(contains('Voting')));
    });

    test('evolve shell index maps limited vs full access', () {
      expect(
        suiteNavEvolveShellTabIndex(SuiteNavDest.wallet, hasAppAccess: true),
        1,
      );
      expect(
        suiteNavEvolveShellTabIndex(SuiteNavDest.wallet, hasAppAccess: false),
        0,
      );
      expect(
        suiteNavEvolveShellTabIndex(SuiteNavDest.security, hasAppAccess: false),
        1,
      );
      expect(
        suiteNavEvolveShellTabIndex(SuiteNavDest.credit, hasAppAccess: false),
        2,
      );
      expect(
        suiteNavEvolveShellTabIndex(SuiteNavDest.analysis, hasAppAccess: false),
        isNull,
      );
      expect(
        suiteNavEvolveShellTabIndex(SuiteNavDest.voting, hasAppAccess: false),
        isNull,
      );
      expect(
        suiteNavEvolveShellTabIndex(SuiteNavDest.voting, hasAppAccess: true),
        3,
      );
    });
  });

  group('reversed swipe', () {
    test('negative dx advances; positive dx retreats', () {
      const n = 4;
      // Finger right-to-left (dx < 0) → next (natural PageView).
      expect(
        suiteIndexAfterHorizontalSwipe(current: 0, destinationCount: n, dx: -40),
        1,
      );
      expect(
        suiteIndexAfterHorizontalSwipe(current: 2, destinationCount: n, dx: -12),
        3,
      );
      // Finger left-to-right (dx > 0) → prev.
      expect(
        suiteIndexAfterHorizontalSwipe(current: 3, destinationCount: n, dx: 40),
        2,
      );
      expect(
        suiteIndexAfterHorizontalSwipe(current: 0, destinationCount: n, dx: 40),
        0,
      );
    });
  });

  testWidgets('product shell is VPN only; no multi-product main bar',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SuiteShell(
          preferInitialParts: true,
          initialParts: SuitePartsState.allInstalled,
          vpnTab: const Scaffold(body: Text('VPN_SURFACE')),
          walletTab: const Scaffold(
            key: Key('inject_wallet'),
            body: Text('WALLET_INJECT'),
          ),
          evolveTab: const Scaffold(
            key: Key('inject_evolve'),
            body: Text('EVOLVE_INJECT'),
          ),
          rpaiTab: const Scaffold(body: Text('RPAI_SURFACE')),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    // Single VPN destination → no main NavigationBar.
    expect(find.byKey(const Key('suite_shell_main_nav')), findsNothing);
    expect(find.byType(NavigationBar), findsNothing);
    expect(find.text('VPN_SURFACE'), findsOneWidget);
    expect(find.text('Wallet'), findsNothing);
    expect(find.text('Analysis'), findsNothing);
    expect(find.text('rpAI'), findsNothing);
    expect(find.text('EVOLVE'), findsNothing);

    final pv = tester.widget<PageView>(find.byKey(const Key('suite_shell_page_view')));
    expect(pv.reverse, isFalse);

    expect(find.byKey(const Key('suite_family_host')), findsNothing);

    final shell = tester.state<SuiteShellState>(find.byType(SuiteShell));
    expect(shell.destinations, [SuiteNavDest.vpn]);
  });

  testWidgets('only VPN: no NavigationBar assert (single destination)',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SuiteShell(
          preferInitialParts: true,
          initialParts: const SuitePartsState(
            walletInstalled: false,
            evolveInstalled: false,
            rpaiInstalled: false,
          ),
          vpnTab: const Scaffold(body: Text('VPN_ONLY')),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('VPN_ONLY'), findsOneWidget);
    expect(find.byKey(const Key('suite_shell_main_nav')), findsNothing);
    expect(find.byType(NavigationBar), findsNothing);
  });

  test('EvolveShellScreen limited tabIndex 0 is Wallet body mapping', () {
    // Documents package contract: limited stack index 0 = Wallet.
    expect(
      suiteNavEvolveShellTabIndex(SuiteNavDest.wallet, hasAppAccess: false),
      0,
    );
    // Full-access index 0 = Analysis (different body).
    expect(
      suiteNavEvolveShellTabIndex(SuiteNavDest.analysis, hasAppAccess: true),
      0,
    );
    // Real package constructor accepts tabIndex for Suite embed.
    const shell = EvolveShellScreen(
      showBottomBar: false,
      tabIndex: 0,
    );
    expect(shell.showBottomBar, isFalse);
    expect(shell.tabIndex, 0);
  });

  testWidgets(
      'production path: VPN only (family host not mounted for product chrome)',
      (tester) async {
    // Product destinations are VPN only — SuiteFamilyHost is not mounted.
    await tester.pumpWidget(
      MaterialApp(
        home: SuiteShell(
          preferInitialParts: true,
          initialParts: SuitePartsState.allInstalled,
          familyBoot: suiteFamilyTestBoot,
          vpnTab: const Scaffold(
            key: Key('vpn_prod_surface'),
            body: Text('VPN_PROD'),
          ),
          rpaiTab: const Scaffold(body: Text('RPAI_PROD')),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.byKey(const Key('suite_family_host')), findsNothing);
    expect(find.text('VPN_PROD'), findsOneWidget);
    expect(find.byKey(const Key('suite_shell_main_nav')), findsNothing);
    expect(find.byType(NavigationBar), findsNothing);
    expect(find.text('RPAI_PROD'), findsNothing);

    final shell = tester.state<SuiteShellState>(find.byType(SuiteShell));
    expect(shell.destinations, [SuiteNavDest.vpn]);
  });

  test('SuiteFamilyHost source: timeouts, boot seam, Theme only on body', () {
    // Structural proof against shipped suite_family_host.dart (cwd = client_app).
    final text = File('lib/suite_family_host.dart').readAsStringSync();
    expect(text.contains('kSuiteFamilyBootTimeout'), isTrue);
    expect(text.contains('TimeoutException'), isTrue);
    expect(text.contains('SuiteFamilyBootFn'), isTrue);
    expect(text.contains('await wallet.initialize()') ||
        text.contains('wallet.initialize()'), isTrue);
    // Host build (before SuiteFamilyBody) must not Theme-wrap the PageView child.
    final hostBuild = text.split('Widget build(BuildContext context)')[1];
    final hostSection = hostBuild.split('class SuiteFamilyBody')[0];
    expect(hostSection.contains('Theme('), isFalse);
    // Body scopes Theme + embed shells without nested bars.
    final bodySection = text.split('class SuiteFamilyBody')[1];
    expect(bodySection.contains('Theme('), isTrue);
    expect(bodySection.contains('showBottomBar: false'), isTrue);
    expect(bodySection.contains('RegistrationSeedSetupDialogHost'), isTrue);
    expect(bodySection.contains('suite_family_boot_retry'), isTrue);
  });
}

