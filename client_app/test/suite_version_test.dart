import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/rpt_config.dart';
import 'package:restore_privacy_client/suite_version.dart';

void main() {
  test('RptConfig product monopin matches suite 1.0.1', () {
    expect(RptConfig.productVersion, kSuiteVersion);
    expect(RptConfig.displayProductVersion, '1.0.1');
    expect(kSuiteDisplayVersion.contains(kSuiteVersion), isTrue);
    expect(kSuiteDisplayVersion.startsWith('Restore Privacy Suite'), isTrue);
  });

  test('pubspec and client/VERSION pin suite 1.0.1', () {
    final pubspec = File('pubspec.yaml').readAsStringSync();
    expect(pubspec.contains('version: 1.0.1'), isTrue);
    expect(pubspec.contains('Restore Privacy Suite'), isTrue);

    final versionFile = File('../client/VERSION').readAsStringSync().trim();
    expect(versionFile, '1.0.1');
  });

  test('source declares four suite tab labels exactly including rpAI', () {
    final shell = File('lib/suite_shell.dart').readAsStringSync();
    final version = File('lib/suite_version.dart').readAsStringSync();
    expect(version.contains("kSuiteTabVpn = 'VPN'"), isTrue);
    expect(version.contains("kSuiteTabWallet = '%'"), isTrue);
    expect(version.contains("kSuiteTabEvolve = 'EVOLVE'"), isTrue);
    expect(version.contains("kSuiteTabRpai = 'rpAI'"), isTrue);
    expect(shell.contains('kSuiteTabVpn'), isTrue);
    expect(shell.contains('kSuiteTabWallet'), isTrue);
    expect(shell.contains('kSuiteTabEvolve'), isTrue);
    expect(shell.contains('kSuiteTabRpai'), isTrue);
    // Real tab bodies — not stub-only placeholders.
    expect(shell.contains('SuiteWalletTab'), isTrue);
    expect(shell.contains('SuiteEvolveTab'), isTrue);
    expect(shell.contains('SuiteRpaiTab'), isTrue);
    expect(shell.contains('vpnTab'), isTrue);
  });

  test('wallet and evolve tabs wire shipped package surfaces', () {
    final wallet = File('lib/suite_wallet_tab.dart').readAsStringSync();
    final evolve = File('lib/suite_evolve_tab.dart').readAsStringSync();
    expect(wallet.contains('WalletBootstrapScreen'), isTrue);
    expect(wallet.contains('package:perccent_wallet'), isTrue);
    expect(evolve.contains('AppBootstrapScreen'), isTrue);
    expect(evolve.contains('package:evolve/'), isTrue);
    expect(wallet.toLowerCase().contains('coming soon'), isFalse);
    expect(evolve.toLowerCase().contains('coming soon'), isFalse);
    // Live block explorer iframed into the % wallet tab
    expect(wallet.contains('SuitePercExplorerPanel'), isTrue);
    expect(wallet.contains('suite_wallet_perc_explorer'), isTrue);
    final explorer = File('lib/suite_perc_explorer_panel.dart').readAsStringSync();
    expect(
      explorer.contains('https://evolve-perc-internet.onrender.com'),
      isTrue,
    );
    expect(explorer.contains('WebView'), isTrue);
  });

  test('suite network config source rejects Render as required default', () {
    final net = File('lib/suite_network_config.dart').readAsStringSync();
    expect(net.contains('135.181.152.10'), isTrue);
    expect(net.contains('/perc'), isTrue);
    expect(net.contains('paused to save money'), isTrue);
    final asset = File('assets/config/perc_network.json').readAsStringSync();
    expect(asset.contains('135.181.152.10'), isTrue);
    expect(asset.contains('/perc'), isTrue);
    // Rendezvous asset still must not require the paid Render host.
    expect(asset.contains('evolve-perc-internet.onrender.com'), isFalse);
    expect(asset.toLowerCase(), contains('paused'));
    // Explorer iframe is a separate surface (wallet tab), not the API default.
    final explorer = File('lib/suite_perc_explorer_panel.dart').readAsStringSync();
    expect(explorer.contains('evolve-perc-internet.onrender.com'), isTrue);
  });
}
