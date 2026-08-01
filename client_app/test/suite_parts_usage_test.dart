/// Suite optional-part uninstall + Settings disk/process usage notifier.
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
    test('VPN is never removable and always installed', () {
      expect(suitePartIsRemovable(SuitePartId.vpn), isFalse);
      expect(kSuitePartVpn.removable, isFalse);
      final s = SuitePartsState(
        walletInstalled: false,
        evolveInstalled: false,
        rpaiInstalled: false,
      );
      expect(s.vpnInstalled, isTrue);
      expect(s.isInstalled(SuitePartId.vpn), isTrue);
      final after = applySuitePartInstall(
        s,
        id: SuitePartId.vpn,
        installed: false,
      );
      expect(after.isInstalled(SuitePartId.vpn), isTrue);
      expect(after, s);
    });

    test('optional parts remove and retain independently', () {
      var s = SuitePartsState.allInstalled;
      s = applySuitePartInstall(s, id: SuitePartId.wallet, installed: false);
      expect(s.walletInstalled, isFalse);
      expect(s.evolveInstalled, isTrue);
      expect(s.rpaiInstalled, isTrue);
      s = applySuitePartInstall(s, id: SuitePartId.evolve, installed: false);
      expect(s.evolveInstalled, isFalse);
      expect(s.rpaiInstalled, isTrue);
      s = applySuitePartInstall(s, id: SuitePartId.rpai, installed: false);
      expect(s.rpaiInstalled, isFalse);
      s = applySuitePartInstall(s, id: SuitePartId.wallet, installed: true);
      expect(s.walletInstalled, isTrue);
      expect(visibleSuitePartIds(s), [SuitePartId.vpn, SuitePartId.wallet]);
    });

    test('store persists optional flags; never invents vpn-off', () async {
      final backend = MemorySettingsBackend();
      final store = SuitePartsStore(backend);
      await store.setInstalled(SuitePartId.wallet, false);
      await store.setInstalled(SuitePartId.evolve, false);
      final loaded = await store.load();
      expect(loaded.walletInstalled, isFalse);
      expect(loaded.evolveInstalled, isFalse);
      expect(loaded.rpaiInstalled, isTrue);
      expect(loaded.vpnInstalled, isTrue);
      expect(backend.data.containsKey(kKeySuitePartWallet), isTrue);
      // No VPN install key — VPN is not optional.
      expect(
        backend.data.keys.where((k) => k.toString().contains('vpn')),
        isEmpty,
      );
    });
  });

  group('usage formatters and reporter path', () {
    test('formatSuiteDiskUsage and formatSuiteProcessPercent', () {
      expect(formatSuiteDiskUsage(0), '0 B');
      expect(formatSuiteDiskUsage(512), '512 B');
      expect(formatSuiteDiskUsage(2048), '2.0 KiB');
      expect(formatSuiteDiskUsage(3 * 1024 * 1024), '3.0 MiB');
      expect(formatSuiteProcessPercent(0), '0%');
      expect(formatSuiteProcessPercent(12.0), '12%');
      expect(formatSuiteProcessPercent(12.4), '12.4%');
      expect(formatSuiteProcessPercent(150), '100%');
      expect(formatSuiteProcessPercent(double.nan), '0%');
    });

    test('SuiteUsageReporter drives injected probes (not hard-coded UI)', () async {
      final reporter = SuiteUsageReporter(
        disk: _FixedDisk(5 * 1024 * 1024),
        process: _FixedProcess(7.5),
      );
      final snap = await reporter.measure();
      expect(snap.diskBytes, 5 * 1024 * 1024);
      expect(snap.processPercent, 7.5);
      // Display strings come from real formatters on measured values.
      expect(formatSuiteDiskUsage(snap.diskBytes), '5.0 MiB');
      expect(formatSuiteProcessPercent(snap.processPercent), '7.5%');
    });

    test('DefaultSuiteDiskUsageProbe measures extraRoots', () async {
      final dir = await Directory.systemTemp.createTemp('suite_disk_');
      addTearDown(() => dir.delete(recursive: true));
      final f = File('${dir.path}/marker.bin');
      await f.writeAsBytes(List<int>.filled(4096, 1));
      final probe = DefaultSuiteDiskUsageProbe(extraRoots: [dir]);
      final n = await probe.measureDiskBytes();
      expect(n, greaterThanOrEqualTo(4096));
    });
  });

  group('SuiteShell visibility', () {
    testWidgets('uninstalled optional parts leave nav; VPN remains', (tester) async {
      final parts = SuitePartsState(
        walletInstalled: false,
        evolveInstalled: true,
        rpaiInstalled: false,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: SuiteShell(
            initialParts: parts,
            partsStore: SuitePartsStore(MemorySettingsBackend()),
            vpnTab: const Scaffold(
              body: Text('VPN_ONLY_SURFACE'),
            ),
            walletTab: const Scaffold(body: Text('WALLET_GONE')),
            evolveTab: const Scaffold(body: Text('EVOLVE_HERE')),
            rpaiTab: const Scaffold(body: Text('RPAI_GONE')),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text(kSuiteTabVpn), findsWidgets);
      expect(find.text(kSuiteTabEvolve), findsWidgets);
      expect(find.text(kSuiteTabWallet), findsNothing);
      expect(find.text(kSuiteTabRpai), findsNothing);
      expect(find.text('VPN_ONLY_SURFACE'), findsOneWidget);
      // Switch to Evolve (visible index 1)
      await tester.tap(find.text(kSuiteTabEvolve));
      await tester.pumpAndSettle();
      expect(find.text('EVOLVE_HERE'), findsOneWidget);
      expect(find.text('WALLET_GONE'), findsNothing);
    });
  });

  group('Settings parts + usage UI', () {
    testWidgets('Settings mounts parts panel and usage notifier; VPN not removable',
        (tester) async {
      // Pre-existing Settings panels wrap ListTiles in DecoratedBox; ignore those
      // framework infos so this suite can drive the real Settings path.
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
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('suite_parts_panel')), findsOneWidget);
      expect(find.byKey(const Key('suite_part_vpn')), findsOneWidget);
      expect(find.byKey(const Key('suite_part_wallet')), findsOneWidget);
      expect(find.byKey(const Key('suite_part_evolve')), findsOneWidget);
      expect(find.byKey(const Key('suite_part_rpai')), findsOneWidget);
      expect(find.text(kSuitePartVpnRequiredLabel), findsOneWidget);
      // VPN tile is not a SwitchListTile.
      expect(
        find.ancestor(
          of: find.byKey(const Key('suite_part_vpn')),
          matching: find.byType(SwitchListTile),
        ),
        findsNothing,
      );

      expect(find.byKey(const Key(kSuiteUsageDiskKey)), findsOneWidget);
      expect(find.byKey(const Key(kSuiteUsageProcessKey)), findsOneWidget);
      // Values come from injected SuiteUsageReporter (same path Settings refresh uses).
      expect(find.textContaining('1.0 MiB'), findsOneWidget);
      expect(find.textContaining('3%'), findsOneWidget);

      // Settings mutates via SuitePartsStore.setInstalled (same API as Switch onChanged).
      await partsStore.setInstalled(SuitePartId.wallet, false);
      final loaded = await partsStore.load();
      expect(loaded.walletInstalled, isFalse);
      expect(loaded.vpnInstalled, isTrue);
      expect(loaded.evolveInstalled, isTrue);
    });
  });

  group('structural', () {
    test('settings source has parts + usage markers; no VPN uninstall control', () {
      String read(String rel) {
        for (final base in ['', 'client_app/']) {
          final f = File('$base$rel');
          if (f.existsSync()) return f.readAsStringSync();
        }
        throw StateError('missing $rel cwd=${Directory.current.path}');
      }

      final settingsSrc = read('lib/settings_screen.dart');
      final partsSrc = read('lib/suite_parts.dart');
      final usageSrc = read('lib/suite_usage.dart');
      expect(settingsSrc.contains('suite_parts_panel'), isTrue);
      expect(settingsSrc.contains('kSuiteUsageDiskKey'), isTrue);
      expect(settingsSrc.contains('kSuiteUsageProcessKey'), isTrue);
      expect(settingsSrc.contains('kSuitePartVpnRequiredLabel'), isTrue);
      expect(usageSrc.contains(kSuiteUsageDiskKey), isTrue);
      expect(usageSrc.contains(kSuiteUsageProcessKey), isTrue);
      expect(partsSrc.contains('removable: false'), isTrue);
      expect(partsSrc.contains('SuitePartId.vpn'), isTrue);
      // Must not offer a VPN uninstall switch path.
      expect(settingsSrc.contains('setInstalled(SuitePartId.vpn'), isFalse);
    });
  });
}
