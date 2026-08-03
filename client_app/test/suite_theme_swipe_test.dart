/// Theme tokens + Settings appearance + suite swipe order (Evolve chrome).
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/settings_screen.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_nav.dart';
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

    testWidgets(
      'idle VPN status title uses suiteTextOf (readable on light panels)',
      (tester) async {
        // Drive shipped [vpnStatusTitleColor] (TunnelHome entry) under light theme.
        await tester.pumpWidget(
          MaterialApp(
            theme: buildSuiteThemeLight(),
            darkTheme: buildSuiteThemeDark(),
            themeMode: ThemeMode.light,
            home: Builder(
              builder: (context) {
                final statusColor = vpnStatusTitleColor(
                  context,
                  connected: false,
                  busyConnecting: false,
                );
                return Scaffold(
                  backgroundColor: suiteChromeBgOf(context),
                  body: Container(
                    color: suitePanelBgOf(context),
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      'Disconnected',
                      key: const Key('vpn_status_card_title'),
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.w700,
                        fontSize: 17,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        );
        await tester.pump();
        final title = tester.widget<Text>(
          find.byKey(const Key('vpn_status_card_title')),
        );
        final color = title.style?.color;
        expect(color, isNotNull);
        // Light onSurface — not dark-only kText / kEvolveText.
        expect(color, kEvolveLightText);
        expect(color, isNot(kText));
        expect(color, isNot(kEvolveText));
        // Contrast against light panel: relative luminance gap must be clear.
        final textLum = color!.computeLuminance();
        final panelLum = kEvolveLightCard.computeLuminance();
        final contrast = (panelLum + 0.05) / (textLum + 0.05);
        expect(contrast, greaterThan(4.5), reason: 'WCAG AA-ish body contrast');

        // Busy / connected branches of the same shipped helper.
        late Color busyColor;
        late Color connectedColor;
        await tester.pumpWidget(
          MaterialApp(
            theme: buildSuiteThemeLight(),
            home: Builder(
              builder: (context) {
                busyColor = vpnStatusTitleColor(
                  context,
                  connected: false,
                  busyConnecting: true,
                );
                connectedColor = vpnStatusTitleColor(
                  context,
                  connected: true,
                  busyConnecting: false,
                );
                return const SizedBox.shrink();
              },
            ),
          ),
        );
        await tester.pump();
        expect(busyColor, kEvolveLightPrimary);
        expect(connectedColor, kEvolveLightSecondary);
      },
    );
  });

  group('static residual VPN shell (no multi-product swipe)', () {
    test('main-bar destinations are VPN only', () {
      final dests = suiteNavDestinations(SuitePartsState.allInstalled);
      expect(dests, [SuiteNavDest.vpn]);
    });

    test('single-destination swipe stays pinned (static main screen)', () {
      const n = 1;
      expect(suiteSwipeNextIndex(0, n), 0);
      expect(suiteSwipePrevIndex(0, n), 0);
      expect(
        suiteIndexAfterHorizontalSwipe(current: 0, destinationCount: 1, dx: -40),
        0,
      );
      expect(
        suiteIndexAfterHorizontalSwipe(current: 0, destinationCount: 1, dx: 40),
        0,
      );
    });
  });
}

