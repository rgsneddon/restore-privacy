/// Theme tokens + Settings appearance + suite swipe order (Evolve chrome).
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/settings_screen.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_parts.dart';
import 'package:restore_privacy_client/suite_shell.dart';
import 'package:restore_privacy_client/theme.dart';

void main() {
  group('Evolve suite theme tokens', () {
    test('dark theme uses Evolve purple primary and dark scaffold', () {
      final t = buildSuiteThemeDark();
      expect(t.brightness, Brightness.dark);
      expect(t.scaffoldBackgroundColor, kEvolveBg);
      expect(t.colorScheme.primary, kEvolvePrimary);
      expect(t.colorScheme.secondary, kEvolveSecondary);
      expect(t.colorScheme.surface, kEvolveCard);
      // Not the old Cupertino blue product chrome.
      expect(t.colorScheme.primary, isNot(const Color(0xFF2779AA)));
      expect(t.scaffoldBackgroundColor, isNot(const Color(0xFFF2F5F7)));
    });

    test('light theme is Evolve family light variant', () {
      final t = buildSuiteThemeLight();
      expect(t.brightness, Brightness.light);
      expect(t.scaffoldBackgroundColor, kEvolveLightBg);
      expect(t.colorScheme.primary, kEvolveLightPrimary);
      expect(t.colorScheme.secondary, kEvolveLightSecondary);
      expect(t.colorScheme.primary, isNot(const Color(0xFF2779AA)));
    });

    test('appearance normalizes and maps ThemeMode', () {
      expect(normalizeSuiteAppearance(null), kAppearanceDark);
      expect(normalizeSuiteAppearance(''), kAppearanceDark);
      expect(normalizeSuiteAppearance('DARK'), kAppearanceDark);
      expect(normalizeSuiteAppearance('light'), kAppearanceLight);
      expect(suiteThemeModeFromAppearance('dark'), ThemeMode.dark);
      expect(suiteThemeModeFromAppearance('light'), ThemeMode.light);
      expect(suiteThemeModeFromAppearance(null), ThemeMode.dark);
    });
  });

  group('Settings appearance preference', () {
    test('load/save dark vs light survives backend reload', () async {
      final map = <String, dynamic>{};
      final store = SettingsStore(MemorySettingsBackend(map));
      final loaded0 = await store.load();
      expect(normalizeSuiteAppearance(loaded0.appearance), kAppearanceDark);
      expect(suiteThemeModeFromAppearance(loaded0.appearance), ThemeMode.dark);

      await store.save(loaded0.copyWith(appearance: 'light'));
      final loaded1 = await store.load();
      expect(normalizeSuiteAppearance(loaded1.appearance), kAppearanceLight);
      expect(suiteThemeModeFromAppearance(loaded1.appearance), ThemeMode.light);
      expect(loaded1.isLightAppearance, isTrue);

      // Simulate cold start with same map.
      final store2 = SettingsStore(MemorySettingsBackend(map));
      final loaded2 = await store2.load();
      expect(normalizeSuiteAppearance(loaded2.appearance), kAppearanceLight);
      expect(map[kKeySuiteAppearance], 'light');

      await store2.save(loaded2.copyWith(appearance: 'dark'));
      final loaded3 = await store2.load();
      expect(normalizeSuiteAppearance(loaded3.appearance), kAppearanceDark);
      expect(suiteThemeModeFromAppearance(loaded3.appearance), ThemeMode.dark);
    });

    testWidgets(
      'light appearance paints VPN home and Settings scaffolds light Evolve',
      (tester) async {
        final map = <String, dynamic>{};
        final store = SettingsStore(MemorySettingsBackend(map));
        await store.save(const ProductSettings(appearance: 'light'));

        // Probe: suiteChromeBgOf / suitePanelBgOf honor MaterialApp light theme.
        await tester.pumpWidget(
          MaterialApp(
            theme: buildSuiteThemeLight(),
            darkTheme: buildSuiteThemeDark(),
            themeMode: suiteThemeModeFromAppearance('light'),
            home: Builder(
              builder: (context) {
                return Scaffold(
                  key: const Key('probe_chrome_scaffold'),
                  backgroundColor: suiteChromeBgOf(context),
                  body: ColoredBox(
                    key: const Key('probe_panel'),
                    color: suitePanelBgOf(context),
                    child: Text(
                      'chrome-probe',
                      style: TextStyle(color: suiteTextOf(context)),
                    ),
                  ),
                );
              },
            ),
          ),
        );
        await tester.pump();
        final probe = tester.widget<Scaffold>(
          find.byKey(const Key('probe_chrome_scaffold')),
        );
        expect(probe.backgroundColor, kEvolveLightBg);
        expect(probe.backgroundColor, isNot(kEvolveBg));
        final panel = tester.widget<ColoredBox>(find.byKey(const Key('probe_panel')));
        expect(panel.color, kEvolveLightCard);

        // Production shell scaffold under light themeMode.
        await tester.pumpWidget(
          MaterialApp(
            theme: buildSuiteThemeLight(),
            darkTheme: buildSuiteThemeDark(),
            themeMode: ThemeMode.light,
            home: SuiteShell(
              preferInitialParts: true,
              initialParts: SuitePartsState.allInstalled,
              vpnTab: Scaffold(
                key: const Key('vpn_home_probe'),
                backgroundColor: kEvolveLightBg, // set by TunnelHome via suiteChromeBgOf
                body: Builder(
                  builder: (context) {
                    // Mirror TunnelHome: resolve chrome from theme helpers.
                    return Scaffold(
                      key: const Key('vpn_home_themed'),
                      backgroundColor: suiteChromeBgOf(context),
                      body: const Center(child: Text('VPN_HOME_PROBE')),
                    );
                  },
                ),
              ),
            ),
          ),
        );
        await tester.pump();
        final shell = tester.widget<Scaffold>(
          find.byKey(const Key('suite_shell_scaffold')),
        );
        expect(shell.backgroundColor, kEvolveLightBg);
        expect(shell.backgroundColor, isNot(kEvolveBg));
        final vpnThemed = tester.widget<Scaffold>(
          find.byKey(const Key('vpn_home_themed')),
        );
        expect(vpnThemed.backgroundColor, kEvolveLightBg);
        expect(vpnThemed.backgroundColor, isNot(kChromeBg));
        expect(vpnThemed.backgroundColor, isNot(kEvolveBg));

        // Settings scaffold (real shipped SettingsScreen build).
        await tester.pumpWidget(
          MaterialApp(
            theme: buildSuiteThemeLight(),
            darkTheme: buildSuiteThemeDark(),
            themeMode: ThemeMode.light,
            home: SettingsScreen(
              store: store,
              initial: const ProductSettings(appearance: 'light'),
            ),
          ),
        );
        await tester.pump();
        final settingsScaffold = tester.widget<Scaffold>(find.byType(Scaffold));
        expect(settingsScaffold.backgroundColor, kEvolveLightBg);
        expect(settingsScaffold.backgroundColor, isNot(kEvolveBg));
        expect(settingsScaffold.backgroundColor, isNot(kChromeBg));
        expect(
          find.byKey(const Key('suite_appearance_light_switch')),
          findsOneWidget,
        );

        // Dark mode still resolves dark Evolve chrome (regression guard).
        // Wrap with Theme(data: dark) so the probe does not depend on
        // MaterialApp themeMode + platform brightness interaction in tests.
        await tester.pumpWidget(
          MaterialApp(
            home: Theme(
              data: buildSuiteThemeDark(),
              child: Builder(
                builder: (context) => Scaffold(
                  key: const Key('probe_dark'),
                  backgroundColor: suiteChromeBgOf(context),
                  body: const SizedBox.shrink(),
                ),
              ),
            ),
          ),
        );
        await tester.pump();
        expect(
          tester.widget<Scaffold>(find.byKey(const Key('probe_dark'))).backgroundColor,
          kEvolveBg,
        );
        expect(
          tester.widget<Scaffold>(find.byKey(const Key('probe_dark'))).backgroundColor,
          isNot(kEvolveLightBg),
        );
      },
    );
  });

  group('suite swipe order VPN → % → Evolve → rpAI', () {
    test('order labels match product copy', () {
      final ids = visibleSuitePartIds(SuitePartsState.allInstalled);
      expect(ids.map(suitePartLabel).toList(), ['VPN', '%', 'EVOLVE', 'rpAI']);
      expect(ids.first, SuitePartId.vpn);
      expect(ids.last, SuitePartId.rpai);
    });

    test('next from VPN walks to rpAI; end block at rpAI', () {
      const n = 4;
      expect(suiteSwipeNextIndex(0, n), 1); // %
      expect(suiteSwipeNextIndex(1, n), 2); // Evolve
      expect(suiteSwipeNextIndex(2, n), 3); // rpAI
      expect(suiteSwipeNextIndex(3, n), 3); // end block
      expect(suiteSwipeNextIndex(99, n), 3);
    });

    test('prev from rpAI walks back to VPN; end block at VPN', () {
      const n = 4;
      expect(suiteSwipePrevIndex(3, n), 2);
      expect(suiteSwipePrevIndex(2, n), 1);
      expect(suiteSwipePrevIndex(1, n), 0);
      expect(suiteSwipePrevIndex(0, n), 0); // end block
      expect(suiteSwipePrevIndex(-5, n), 0);
    });

    test('horizontal swipe dx: positive advances, negative retreats', () {
      const n = 4;
      // Left-to-right finger (dx > 0) → next
      expect(
        suiteIndexAfterHorizontalSwipe(current: 0, destinationCount: n, dx: 40),
        1,
      );
      expect(
        suiteIndexAfterHorizontalSwipe(current: 2, destinationCount: n, dx: 12),
        3,
      );
      expect(
        suiteIndexAfterHorizontalSwipe(current: 3, destinationCount: n, dx: 50),
        3,
      );
      // Right-to-left finger (dx < 0) → prev
      expect(
        suiteIndexAfterHorizontalSwipe(current: 3, destinationCount: n, dx: -40),
        2,
      );
      expect(
        suiteIndexAfterHorizontalSwipe(current: 0, destinationCount: n, dx: -40),
        0,
      );
    });

    test('clamp and swipe with fewer destinations still end-blocks', () {
      // e.g. custom count for a future installed-only path
      expect(suiteSwipeNextIndex(0, 2), 1);
      expect(suiteSwipeNextIndex(1, 2), 1);
      expect(suiteSwipePrevIndex(0, 2), 0);
      expect(
        suiteIndexAfterHorizontalSwipe(current: 0, destinationCount: 1, dx: 20),
        0,
      );
    });
  });
}
