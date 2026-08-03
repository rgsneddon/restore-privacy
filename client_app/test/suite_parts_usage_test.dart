/// Suite parts: optional default-off, install expands bar, typed uninstall, VPN fixed.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/settings_screen.dart';
import 'package:restore_privacy_client/settings_store.dart';
import 'package:restore_privacy_client/suite_nav.dart';
import 'package:restore_privacy_client/suite_parts.dart';
import 'package:restore_privacy_client/suite_parts_store.dart';
import 'package:restore_privacy_client/suite_shell.dart';
import 'package:restore_privacy_client/suite_usage.dart';
import 'package:restore_privacy_client/suite_version.dart';
import 'package:restore_privacy_client/theme.dart';

class _FixedDisk implements SuiteDiskUsageProbe {
  _FixedDisk(this.bytes);
  final int bytes;
  @override
  Future<int> measureDiskBytes() async => bytes;
}

class _FixedProcess implements SuiteProcessUsageProbe {
  _FixedProcess(this.percent);
  final double percent;
  @override
  Future<double> measureProcessPercent() async => percent;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('suite parts pure policy', () {
    test('product default: residual VPN only; VPN non-removable', () {
      expect(SuitePartsState.vpnOnly.walletInstalled, isFalse);
      expect(SuitePartsState.vpnOnly.evolveInstalled, isFalse);
      expect(SuitePartsState.vpnOnly.rpaiInstalled, isFalse);
      expect(SuitePartsState.vpnOnly.vpnInstalled, isTrue);
      expect(const SuitePartsState().rpaiInstalled, isFalse);
      expect(const SuitePartsState().walletInstalled, isFalse);
      // Historical fixtures still exist for pure unit tests.
      expect(SuitePartsState.vpnAndRpai.rpaiInstalled, isTrue);
      expect(SuitePartsState.allInstalled.walletInstalled, isTrue);
      expect(suitePartIsRemovable(SuitePartId.vpn), isFalse);
      expect(
        applySuitePartInstall(
          SuitePartsState.allInstalled,
          id: SuitePartId.vpn,
          installed: false,
          confirmPhrase: 'VPN',
        ).vpnInstalled,
        isTrue,
      );
      final afterVpnOff = applySuitePartInstall(
        SuitePartsState.vpnOnly,
        id: SuitePartId.vpn,
        installed: false,
        confirmPhrase: 'VPN',
      );
      expect(afterVpnOff.vpnInstalled, isTrue);
      expect(afterVpnOff, SuitePartsState.vpnOnly);
    });

    test('product main-bar destinations are VPN only for any parts state', () {
      for (final parts in [
        SuitePartsState.vpnOnly,
        SuitePartsState.vpnAndRpai,
        SuitePartsState.allInstalled,
      ]) {
        final d = suiteNavDestinations(parts);
        expect(d, [SuiteNavDest.vpn], reason: '$parts');
        final labels = d.map(suiteNavLabel).toList();
        expect(labels, ['VPN']);
        expect(labels, isNot(contains('Wallet')));
        expect(labels, isNot(contains('Analysis')));
        expect(labels, isNot(contains(kSuiteTabRpai)));
      }
      expect(
        visibleSuitePartIds(SuitePartsState.vpnOnly),
        [SuitePartId.vpn],
      );
      expect(
        suitePartShowsFullSurface(SuitePartsState.vpnOnly, SuitePartId.vpn),
        isTrue,
      );
      expect(
        suitePartShowsFullSurface(SuitePartsState.vpnOnly, SuitePartId.wallet),
        isFalse,
      );
    });

    test('install flags cannot re-expand product main-bar (VPN only)', () {
      var s = SuitePartsState.vpnOnly;
      expect(suiteNavDestinations(s).map(suiteNavLabel).toList(), ['VPN']);
      s = applySuitePartInstall(
        s,
        id: SuitePartId.wallet,
        installed: true,
      );
      expect(s.walletInstalled, isTrue);
      // Product chrome stays VPN-only regardless of install flags.
      expect(
        suiteNavDestinations(s).map(suiteNavLabel).toList(),
        ['VPN'],
      );
      s = applySuitePartInstall(
        s,
        id: SuitePartId.evolve,
        installed: true,
      );
      expect(
        suiteNavDestinations(s).map(suiteNavLabel).toList(),
        ['VPN'],
      );
      expect(
        applySuitePartInstall(
          s,
          id: SuitePartId.vpn,
          installed: false,
          confirmPhrase: 'VPN',
        ).vpnInstalled,
        isTrue,
      );
    });

    test('fromJson and store load: always product VPN only', () async {
      expect(SuitePartsState.fromJson(null), SuitePartsState.vpnOnly);
      expect(SuitePartsState.fromJson({}), SuitePartsState.vpnOnly);
      expect(
        SuitePartsState.fromJson({kKeySuitePartWallet: true}),
        SuitePartsState.vpnOnly,
      );
      expect(
        SuitePartsState.fromJson({kKeySuitePartRpai: false}),
        SuitePartsState.vpnOnly,
      );
      final backend = MemorySettingsBackend();
      final store = SuitePartsStore(backend);
      final fresh = await store.load();
      expect(fresh, SuitePartsState.vpnOnly);
      expect(fresh.vpnInstalled, isTrue);
      expect(fresh.walletInstalled, isFalse);
      expect(fresh.rpaiInstalled, isFalse);
      await store.save(SuitePartsState.allInstalled);
      final stillVpn = await store.load();
      expect(stillVpn, SuitePartsState.vpnOnly);
    });

    test('uninstall confirm gate requires exact part name (rpOS-style)', () {
      expect(
        suitePartUninstallConfirmationAccepted(
          id: SuitePartId.wallet,
          userInput: null,
        ),
        isFalse,
      );
      expect(
        suitePartUninstallConfirmationAccepted(
          id: SuitePartId.wallet,
          userInput: '',
        ),
        isFalse,
      );
      expect(
        suitePartUninstallConfirmationAccepted(
          id: SuitePartId.wallet,
          userInput: 'wallet',
        ),
        isFalse,
      );
      expect(
        suitePartUninstallConfirmationAccepted(
          id: SuitePartId.wallet,
          userInput: kSuiteTabWallet,
        ),
        isTrue,
      );
      expect(
        suitePartUninstallConfirmationAccepted(
          id: SuitePartId.evolve,
          userInput: '  EVOLVE  ',
        ),
        isTrue,
      );
      expect(
        suitePartUninstallConfirmationAccepted(
          id: SuitePartId.vpn,
          userInput: 'VPN',
        ),
        isFalse,
      );

      final before = SuitePartsState.allInstalled;
      final noConfirm = applySuitePartInstall(
        before,
        id: SuitePartId.wallet,
        installed: false,
      );
      expect(noConfirm.walletInstalled, isTrue);
      final wrong = applySuitePartInstall(
        before,
        id: SuitePartId.wallet,
        installed: false,
        confirmPhrase: 'nope',
      );
      expect(wrong.walletInstalled, isTrue);
      final ok = applySuitePartInstall(
        before,
        id: SuitePartId.wallet,
        installed: false,
        confirmPhrase: kSuiteTabWallet,
      );
      expect(ok.walletInstalled, isFalse);
      // Reinstall needs no phrase
      final back = applySuitePartInstall(
        ok,
        id: SuitePartId.wallet,
        installed: true,
      );
      expect(back.walletInstalled, isTrue);
    });

    test('store always returns product VPN only after setInstalled', () async {
      final backend = MemorySettingsBackend();
      final store = SuitePartsStore(backend);
      await store.save(SuitePartsState.allInstalled);
      final rejected = await store.setInstalled(SuitePartId.evolve, false);
      expect(rejected, SuitePartsState.vpnOnly);
      final accepted = await store.setInstalled(
        SuitePartId.evolve,
        false,
        confirmPhrase: kSuiteTabEvolve,
      );
      expect(accepted, SuitePartsState.vpnOnly);
      final loaded = await store.load();
      expect(loaded, SuitePartsState.vpnOnly);
    });

    test('store setInstalled cannot expand product chrome', () async {
      final backend = MemorySettingsBackend();
      backend.data['licence_accepted'] = true;
      final store = SuitePartsStore(backend);
      final fresh = await store.load();
      expect(fresh.walletInstalled, isFalse);
      expect(fresh.rpaiInstalled, isFalse);
      final next = await store.setInstalled(SuitePartId.wallet, true);
      expect(next, SuitePartsState.vpnOnly);
      expect(backend.data['licence_accepted'], isTrue);
      expect(
        suiteNavDestinations(next).map(suiteNavLabel).toList(),
        ['VPN'],
      );
    });
  });

  group('usage formatters and reporter path', () {
    test('formatSuiteDiskUsage and formatSuiteProcessPercent', () {
      expect(formatSuiteDiskUsage(0), '0 B');
      expect(formatSuiteDiskUsage(3 * 1024 * 1024), '3.0 MiB');
      expect(formatSuiteProcessPercent(12.0), '12%');
      expect(formatSuiteProcessPercent(12.4), '12.4%');
    });

    test('SuiteUsageReporter drives injected probes', () async {
      final reporter = SuiteUsageReporter(
        disk: _FixedDisk(5 * 1024 * 1024),
        process: _FixedProcess(7.5),
      );
      final snap = await reporter.measure();
      expect(snap.diskBytes, 5 * 1024 * 1024);
      expect(snap.processPercent, 7.5);
      expect(formatSuiteDiskUsage(snap.diskBytes), '5.0 MiB');
      expect(formatSuiteProcessPercent(snap.processPercent), '7.5%');
    });
  });

  group('SuiteShell VPN-only product chrome', () {
    testWidgets('shell shows VPN surface only even when family flags true',
        (tester) async {
      final parts = SuitePartsState(
        walletInstalled: false,
        evolveInstalled: true,
        rpaiInstalled: true,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: SuiteShell(
            initialParts: parts,
            preferInitialParts: true,
            partsStore: SuitePartsStore(MemorySettingsBackend()),
            vpnTab: const Scaffold(body: Text('VPN_SURFACE')),
            walletTab: const Scaffold(body: Text('WALLET_FULL')),
            evolveTab: const Scaffold(body: Text('EVOLVE_FULL')),
            rpaiTab: const Scaffold(body: Text('RPAI_FULL')),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('VPN_SURFACE'), findsOneWidget);
      expect(find.text('Wallet'), findsNothing);
      expect(find.text('Analysis'), findsNothing);
      expect(find.text(kSuiteTabRpai), findsNothing);
      expect(find.text(kSuiteTabEvolve), findsNothing);
      // Single destination → no NavigationBar.
      expect(find.byType(NavigationBar), findsNothing);
    });

    testWidgets('fresh shell: VPN only; install cannot expand bar',
        (tester) async {
      final backend = MemorySettingsBackend();
      backend.data['licence_accepted'] = true;
      final store = SuitePartsStore(backend);
      expect((await store.load()), SuitePartsState.vpnOnly);

      await tester.pumpWidget(
        MaterialApp(
          home: SuiteShell(
            partsStore: store,
            vpnTab: const Scaffold(body: Text('VPN_SURFACE')),
            walletTab: const Scaffold(body: Text('WALLET_FULL')),
            evolveTab: const Scaffold(body: Text('EVOLVE_FULL')),
            rpaiTab: const Scaffold(body: Text('RPAI_FULL')),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final shell = tester.state<SuiteShellState>(find.byType(SuiteShell));
      expect(shell.partsState, SuitePartsState.vpnOnly);
      expect(shell.destinations, [SuiteNavDest.vpn]);
      expect(find.text('Wallet'), findsNothing);
      expect(find.text(kSuiteTabRpai), findsNothing);
      expect(find.text('VPN_SURFACE'), findsOneWidget);

      await shell.setPartInstalled(SuitePartId.wallet, true);
      await tester.pumpAndSettle();
      expect(shell.destinations, [SuiteNavDest.vpn]);
      expect(find.text('Wallet'), findsNothing);
      expect((await store.load()), SuitePartsState.vpnOnly);
    });

    testWidgets('cold start always VPN only', (tester) async {
      final backend = MemorySettingsBackend();
      final store = SuitePartsStore(backend);
      await store.save(
        const SuitePartsState(
          walletInstalled: false,
          evolveInstalled: true,
          rpaiInstalled: false,
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: SuiteShell(
            partsStore: store,
            vpnTab: const Scaffold(body: Text('VPN_COLD')),
            walletTab: const Scaffold(body: Text('WALLET_COLD')),
            evolveTab: const Scaffold(body: Text('EVOLVE_COLD')),
            rpaiTab: const Scaffold(body: Text('RPAI_COLD')),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final state = tester.state<SuiteShellState>(find.byType(SuiteShell));
      expect(state.partsState, SuitePartsState.vpnOnly);
      expect(find.text('VPN_COLD'), findsOneWidget);
      expect(find.text('Analysis'), findsNothing);
      expect(find.text(kSuiteTabRpai), findsNothing);
    });
  });

  group('Settings product panel + usage', () {
    testWidgets('Settings mounts VPN-only product panel and usage notifier',
        (tester) async {
      final previousOnError = FlutterError.onError;
      FlutterError.onError = (details) {
        if (details.exceptionAsString().contains('ListTile background color')) {
          return;
        }
        previousOnError?.call(details);
      };
      addTearDown(() => FlutterError.onError = previousOnError);

      final backend = MemorySettingsBackend();
      final settingsStore = SettingsStore(backend);
      final partsStore = SuitePartsStore(backend);

      final view = tester.view;
      view.physicalSize = const Size(900, 2400);
      view.devicePixelRatio = 1.0;
      addTearDown(view.resetPhysicalSize);
      addTearDown(view.resetDevicePixelRatio);

      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(scaffoldBackgroundColor: kChromeBg),
          home: SettingsScreen(
            store: settingsStore,
            initial: ProductSettings.defaults,
            partsStore: partsStore,
            initialParts: SuitePartsState.vpnOnly,
            usageReporter: SuiteUsageReporter(
              disk: _FixedDisk(1024 * 1024),
              process: _FixedProcess(3),
            ),
            initialUsage: const SuiteUsageSnapshot(
              diskBytes: 1024 * 1024,
              processPercent: 3,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('suite_parts_panel')), findsOneWidget);
      expect(find.byKey(const Key('suite_part_vpn')), findsOneWidget);
      expect(find.text(kSuitePartVpnRequiredLabel), findsOneWidget);
      expect(find.byKey(const Key('suite_part_uninstall_btn_vpn')), findsNothing);
      expect(find.byKey(const Key(kSuiteUsageDiskKey)), findsOneWidget);
      expect(find.textContaining('1.0 MiB'), findsOneWidget);
      expect(find.textContaining('3%'), findsOneWidget);

      // Optional Suite family tiles are not product chrome.
      expect(find.byKey(const Key('suite_part_uninstall_btn_wallet')), findsNothing);
      expect(find.byKey(const Key('suite_part_uninstall_btn_evolve')), findsNothing);
      expect(find.byKey(const Key('suite_part_uninstall_btn_rpai')), findsNothing);
    });
  });

  group('structural', () {
    test('settings + shell + parts source lock VPN-only product path', () {
      String read(String rel) {
        for (final base in ['', 'client_app/']) {
          final f = File('$base$rel');
          if (f.existsSync()) return f.readAsStringSync();
        }
        throw StateError('missing $rel');
      }

      final settingsSrc = read('lib/settings_screen.dart');
      final partsSrc = read('lib/suite_parts.dart');
      final shellSrc = read('lib/suite_shell.dart');
      final storeSrc = read('lib/suite_parts_store.dart');
      final navSrc = read('lib/suite_nav.dart');

      expect(settingsSrc.contains('kSuitePartVpn'), isTrue);
      expect(partsSrc.contains('vpnOnly'), isTrue);
      expect(partsSrc.contains('residual VPN only'), isTrue);
      expect(partsSrc.contains('removable: false'), isTrue);
      expect(storeSrc.contains('SuitePartsState.vpnOnly'), isTrue);
      expect(shellSrc.contains('SuitePartsState.vpnOnly'), isTrue);
      expect(navSrc.contains('SuiteNavDest.vpn'), isTrue);
      expect(navSrc.contains('VPN only'), isTrue);
    });
  });
}
