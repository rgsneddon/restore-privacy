/// Flat main-bar destinations + reversed swipe + no nested %/Evolve bars.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:restore_privacy_client/suite_nav.dart';
import 'package:restore_privacy_client/suite_parts.dart';
import 'package:restore_privacy_client/suite_shell.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('suiteNavDestinations', () {
    test('all installed: VPN + family (no dual EVOLVE top-level) + rpAI', () {
      final d = suiteNavDestinations(SuitePartsState.allInstalled);
      final labels = d.map(suiteNavLabel).toList();
      expect(labels.first, 'VPN');
      expect(labels.last, 'rpAI');
      // Unified %/Evolve family — Wallet once, no separate EVOLVE product slot.
      expect(labels.where((l) => l == 'EVOLVE'), isEmpty);
      expect(labels.where((l) => l == '%'), isEmpty);
      expect(labels, containsAll(['Analysis', 'Wallet', 'Security', 'Voting', 'Credit']));
      // % and Evolve share family — Analysis/Voting from evolve, Wallet shared.
      expect(d.where(suiteNavIsPercentEvolveFamily).length, greaterThanOrEqualTo(3));
    });

    test('wallet only: no Analysis/Voting', () {
      const parts = SuitePartsState(
        walletInstalled: true,
        evolveInstalled: false,
        rpaiInstalled: true,
      );
      final labels = suiteNavDestinations(parts).map(suiteNavLabel).toList();
      expect(labels, ['VPN', 'Wallet', 'Security', 'Credit', 'rpAI']);
      expect(labels, isNot(contains('Analysis')));
      expect(labels, isNot(contains('Voting')));
    });

    test('neither wallet nor evolve: VPN + rpAI only', () {
      const parts = SuitePartsState(
        walletInstalled: false,
        evolveInstalled: false,
        rpaiInstalled: true,
      );
      expect(
        suiteNavDestinations(parts).map(suiteNavLabel).toList(),
        ['VPN', 'rpAI'],
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

  testWidgets('main bar lists promoted tabs; no nested wallet/evolve bars',
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

    // Main bar destinations (promoted family).
    expect(find.byKey(const Key('suite_shell_main_nav')), findsOneWidget);
    expect(find.text('VPN'), findsWidgets);
    expect(find.text('Wallet'), findsWidgets);
    expect(find.text('Analysis'), findsWidgets);
    expect(find.text('Security'), findsWidgets);
    expect(find.text('Voting'), findsWidgets);
    expect(find.text('Credit'), findsWidgets);
    expect(find.text('rpAI'), findsWidgets);
    // No dual top-level EVOLVE product label on main bar.
    expect(find.text('EVOLVE'), findsNothing);

    // PageView is not reverse (swipes natural).
    final pv = tester.widget<PageView>(find.byKey(const Key('suite_shell_page_view')));
    expect(pv.reverse, isFalse);

    // Nested package bars must not appear on Suite embed path.
    expect(find.byKey(const Key('wallet_shell_embed_no_bottom_bar')), findsNothing);
    expect(find.byKey(const Key('evolve_shell_embed_no_bottom_bar')), findsNothing);
    // Only one NavigationBar — the Suite main bar.
    expect(find.byType(NavigationBar), findsOneWidget);

    final shell = tester.state<SuiteShellState>(find.byType(SuiteShell));
    final dests = shell.destinations;
    expect(dests.first, SuiteNavDest.vpn);
    expect(dests, contains(SuiteNavDest.wallet));
    expect(dests, contains(SuiteNavDest.analysis));
    expect(dests.where((d) => d == SuiteNavDest.vpn).length, 1);

    // Select Analysis (index 1 with all installed).
    final analysisIdx = dests.indexOf(SuiteNavDest.analysis);
    shell.selectTab(analysisIdx);
    await tester.pump();
    expect(find.text('EVOLVE_INJECT'), findsOneWidget);

    // Select Wallet — inject wallet when provided for shared surface.
    final walletIdx = dests.indexOf(SuiteNavDest.wallet);
    shell.selectTab(walletIdx);
    await tester.pump();
    expect(find.text('WALLET_INJECT'), findsOneWidget);
  });
}
