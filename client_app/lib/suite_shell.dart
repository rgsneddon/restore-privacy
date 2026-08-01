import 'package:flutter/material.dart';

import 'suite_evolve_tab.dart';
import 'suite_rpai_tab.dart';
import 'suite_version.dart';
import 'suite_wallet_tab.dart';
import 'theme.dart';

/// Unified Restore Privacy Suite shell: **VPN** · **%** · **EVOLVE** · **rpAI**.
///
/// Tab switch keeps the process alive (IndexedStack). VPN is the residual
/// tunnel home; % embeds Perccent wallet; EVOLVE embeds the full Evolve app;
/// rpAI is Ned, the Restore Privacy Helper.
class SuiteShell extends StatefulWidget {
  const SuiteShell({
    super.key,
    required this.vpnTab,
    this.initialTabIndex = 0,
    this.walletTab,
    this.evolveTab,
    this.rpaiTab,
  });

  /// Residual VPN home (Connect / licence / settings) — required shipped surface.
  final Widget vpnTab;

  /// 0 = VPN, 1 = %, 2 = EVOLVE, 3 = rpAI (Ned).
  final int initialTabIndex;

  /// Injectable wallet tab body (tests); production uses [SuiteWalletTab].
  final Widget? walletTab;

  /// Injectable evolve tab body (tests); production uses [SuiteEvolveTab].
  final Widget? evolveTab;

  /// Injectable Ned / rpAI tab (tests); production uses [SuiteRpaiTab].
  final Widget? rpaiTab;

  @override
  State<SuiteShell> createState() => SuiteShellState();
}

/// Public state for tests that select tabs programmatically.
class SuiteShellState extends State<SuiteShell> {
  late int _index;

  int get currentTabIndex => _index;

  void selectTab(int index) {
    if (index < 0 || index >= kSuiteTabLabels.length) return;
    if (_index == index) return;
    setState(() => _index = index);
  }

  @override
  void initState() {
    super.initState();
    final i = widget.initialTabIndex;
    _index = (i >= 0 && i < kSuiteTabLabels.length) ? i : 0;
  }

  @override
  Widget build(BuildContext context) {
    final wallet = widget.walletTab ?? const SuiteWalletTab();
    final evolve = widget.evolveTab ?? const SuiteEvolveTab();
    final rpai = widget.rpaiTab ?? const SuiteRpaiTab();

    return Scaffold(
      backgroundColor: kChromeBg,
      body: Column(
        children: [
          _SuiteChromeBar(tabIndex: _index),
          Expanded(
            child: IndexedStack(
              index: _index,
              sizing: StackFit.expand,
              children: [
                widget.vpnTab,
                wallet,
                evolve,
                rpai,
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: selectTab,
        backgroundColor: kPanelBg,
        indicatorColor: kLightAccent,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.shield_outlined),
            selectedIcon: Icon(Icons.shield),
            label: kSuiteTabVpn,
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined),
            selectedIcon: Icon(Icons.account_balance_wallet),
            label: kSuiteTabWallet,
          ),
          NavigationDestination(
            icon: Icon(Icons.auto_graph_outlined),
            selectedIcon: Icon(Icons.auto_graph),
            label: kSuiteTabEvolve,
          ),
          NavigationDestination(
            icon: Icon(Icons.smart_toy_outlined),
            selectedIcon: Icon(Icons.smart_toy),
            label: kSuiteTabRpai,
          ),
        ],
      ),
    );
  }
}

class _SuiteChromeBar extends StatelessWidget {
  const _SuiteChromeBar({required this.tabIndex});

  final int tabIndex;

  @override
  Widget build(BuildContext context) {
    final tab = kSuiteTabLabels[tabIndex];
    return Material(
      color: kPrimaryDark,
      elevation: 1,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      kSuiteProductName,
                      style: const TextStyle(
                        color: kWhite,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      kSuiteDisplayVersion,
                      style: TextStyle(
                        color: kWhite.withValues(alpha: 0.9),
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: kWhite.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  tab,
                  style: const TextStyle(
                    color: kWhite,
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
