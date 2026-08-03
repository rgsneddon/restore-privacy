import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/rpt_config.dart';
import 'package:restore_privacy_client/suite_version.dart';

void main() {
  test('RptConfig product monopin matches residual catalog pin', () {
    expect(RptConfig.productVersion, kSuiteVersion);
    expect(kSuiteVersion, '1.1.7');
    expect(kSuiteDisplayVersion.contains(kSuiteVersion), isTrue);
    expect(kSuiteDisplayVersion.toLowerCase(), contains('privacy'));
    // Residual VPN product — not multi-product Suite chrome.
    expect(kSuiteDisplayVersion.toLowerCase().contains('suite'), isFalse);
  });

  test('pubspec and client/VERSION pin monopin 1.1.7', () {
    final pubspec = File('pubspec.yaml').readAsStringSync();
    expect(pubspec.contains('version: 1.1.7'), isTrue);

    final versionFile = File('../client/VERSION').readAsStringSync().trim();
    expect(versionFile, '1.1.7');
    expect(versionFile, kSuiteVersion);
  });

  test('suite_version still declares legacy tab constants for companions', () {
    final version = File('lib/suite_version.dart').readAsStringSync();
    expect(version.contains("kSuiteTabVpn = 'VPN'"), isTrue);
    expect(version.contains("kSuiteTabWallet = '%'"), isTrue);
    expect(version.contains("kSuiteTabEvolve = 'EVOLVE'"), isTrue);
    expect(version.contains("kSuiteTabRpai = 'rpAI'"), isTrue);
    // Live shell is VPN-only residual; constants may remain for tests/companions.
    final shell = File('lib/suite_shell.dart').readAsStringSync();
    expect(shell.contains('vpnTab') || shell.contains('VPN'), isTrue);
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
    // Block explorer is not embedded in the % wallet tab
    expect(wallet.contains('SuitePercExplorerPanel'), isFalse);
    expect(wallet.contains('suite_wallet_perc_explorer'), isFalse);
    expect(wallet.contains('WebView'), isFalse);
    expect(wallet.contains('evolve-perc-internet.onrender.com'), isFalse);
    expect(
      File('lib/suite_perc_explorer_panel.dart').existsSync(),
      isFalse,
      reason: 'explorer embed panel file must be removed',
    );
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
  });
}
