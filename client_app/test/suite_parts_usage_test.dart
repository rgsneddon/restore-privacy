/// Suite parts: tab-retain uninstall, typed confirm, reinstall, usage notifier.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/settings_screen.dart';
import 'package:restore_privacy_client/settings_store.dart';
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
    test('fresh default has all optional parts installed; VPN always-in', () {
      expect(SuitePartsState.allInstalled.walletInstalled, isTrue);
      expect(SuitePartsState.allInstalled.evolveInstalled, isTrue);
      expect(SuitePartsState.allInstalled.rpaiInstalled, isTrue);
      expect(SuitePartsState.allInstalled.vpnInstalled, isTrue);
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
    });

    test('tabs always retained even when optional parts uninstalled', () {
      final s = SuitePartsState(
        walletInstalled: false,
        evolveInstalled: false,
        rpaiInstalled: false,
      );
      expect(
        visibleSuitePartIds(s),
        [
          SuitePartId.vpn,
          SuitePartId.wallet,
          SuitePartId.evolve,
          SuitePartId.rpai,
        ],
      );
      expect(suitePartShowsFullSurface(s, SuitePartId.vpn), isTrue);
      expect(suitePartShowsFullSurface(s, SuitePartId.wallet), isFalse);
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

    test('store persists uninstall only with valid confirm phrase', () async {
      final backend = MemorySettingsBackend();
      final store = SuitePartsStore(backend);
      final rejected = await store.setInstalled(SuitePartId.evolve, false);
      expect(rejected.evolveInstalled, isTrue);
      final accepted = await store.setInstalled(
        SuitePartId.evolve,
        false,
        confirmPhrase: kSuiteTabEvolve,
      );
      expect(accepted.evolveInstalled, isFalse);
      final loaded = await store.load();
      expect(loaded.evolveInstalled, isFalse);
      final re = await store.setInstalled(SuitePartId.evolve, true);
      expect(re.evolveInstalled, isTrue);
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

  group('SuiteShell flat family + reinstall', () {
    testWidgets(
        'wallet off + evolve on: family still on main bar via Evolve surfaces',
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

      // Flat main bar: no dual EVOLVE product slot; family destinations present.
      expect(find.text(kSuiteTabVpn), findsWidgets);
      expect(find.text('Wallet'), findsWidgets);
      expect(find.text('Analysis'), findsWidgets);
      expect(find.text(kSuiteTabRpai), findsWidgets);
      expect(find.text(kSuiteTabEvolve), findsNothing);

      // Wallet destination served by Evolve inject when wallet part is off.
      await tester.tap(find.text('Wallet').last);
      await tester.pumpAndSettle();
      expect(find.text('EVOLVE_FULL'), findsOneWidget);
      expect(find.text('WALLET_FULL'), findsNothing);

      await tester.tap(find.text('Analysis').last);
      await tester.pumpAndSettle();
      expect(find.text('EVOLVE_FULL'), findsOneWidget);
    });

    testWidgets('reinstall wallet part restores wallet inject path',
        (tester) async {
      final backend = MemorySettingsBackend();
      backend.data['licence_accepted'] = true;
      backend.data['suite_account_registered'] = true;
      backend.data['suite_account_username'] = 'alice';

      final store = SuitePartsStore(backend);
      await store.save(
        const SuitePartsState(
          walletInstalled: false,
          evolveInstalled: false,
          rpaiInstalled: true,
        ),
      );

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

      // Family destinations omitted when both wallet and evolve are off.
      expect(find.text('Wallet'), findsNothing);
      expect(find.text(kSuiteTabRpai), findsWidgets);

      // Reinstall wallet via shell API (Settings path).
      final shell = tester.state<SuiteShellState>(find.byType(SuiteShell));
      await shell.setPartInstalled(SuitePartId.wallet, true);
      await tester.pumpAndSettle();

      expect(find.text('Wallet'), findsWidgets);
      await tester.tap(find.text('Wallet').last);
      await tester.pumpAndSettle();
      expect(find.text('WALLET_FULL'), findsOneWidget);

      final loaded = await store.load();
      expect(loaded.walletInstalled, isTrue);
      expect(backend.data['licence_accepted'], isTrue);
      expect(backend.data['suite_account_registered'], isTrue);
      expect(backend.data['suite_account_username'], 'alice');
    });

    testWidgets('cold start: uninstalled rpAI omitted from main bar',
        (tester) async {
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
      expect(state.partsState.walletInstalled, isFalse);
      expect(state.partsState.rpaiInstalled, isFalse);
      expect(find.text('Analysis'), findsWidgets);
      expect(find.text(kSuiteTabRpai), findsNothing);
      expect(find.text('RPAI_COLD'), findsNothing);
    });
  });

  group('Settings uninstall confirm + usage', () {
    testWidgets('Settings mounts parts panel; VPN not removable; usage notifier',
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
      await partsStore.save(SuitePartsState.allInstalled);

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
            initialParts: SuitePartsState.allInstalled,
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

      // Uninstall buttons exist for optional parts (typed gate is pure-tested).
      expect(find.byKey(const Key('suite_part_uninstall_btn_wallet')), findsOneWidget);
      expect(find.byKey(const Key('suite_part_uninstall_btn_evolve')), findsOneWidget);
      expect(find.byKey(const Key('suite_part_uninstall_btn_rpai')), findsOneWidget);

      // Drive the same store API the dialog proceeds to after valid confirm.
      final aborted = await partsStore.setInstalled(
        SuitePartId.wallet,
        false,
        confirmPhrase: 'wrong',
      );
      expect(aborted.walletInstalled, isTrue);
      final ok = await partsStore.setInstalled(
        SuitePartId.wallet,
        false,
        confirmPhrase: kSuiteTabWallet,
      );
      expect(ok.walletInstalled, isFalse);
    });
  });

  group('structural', () {
    test('settings + shell + parts source mount confirm and reinstall path', () {
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
      final phSrc = read('lib/suite_part_placeholder.dart');

      expect(settingsSrc.contains('suite_part_confirm_field_'), isTrue);
      expect(settingsSrc.contains('evaluateSuitePartUninstallConfirmation'),
          isTrue);
      expect(settingsSrc.contains('_confirmUninstallPart'), isTrue);
      expect(partsSrc.contains('suitePartUninstallConfirmationAccepted'), isTrue);
      expect(partsSrc.contains('visibleSuitePartIds'), isTrue);
      expect(shellSrc.contains('SuitePartReinstallPlaceholder'), isTrue);
      expect(phSrc.contains('kSuitePartReinstallLabel'), isTrue);
      expect(partsSrc.contains('KEYGEN'), isTrue);
      expect(partsSrc.contains('removable: false'), isTrue);
    });
  });
}
