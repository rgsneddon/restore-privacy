import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'prefs_backend.dart';
import 'settings_store.dart';
import 'suite_evolve_tab.dart';
import 'suite_parts.dart';
import 'suite_parts_store.dart';
import 'suite_rpai_tab.dart';
import 'suite_version.dart';
import 'suite_wallet_tab.dart';
import 'theme.dart';

/// Unified Restore Privacy Suite shell: **VPN** · optional **%** · **EVOLVE** · **rpAI**.
///
/// Tab switch keeps the process alive (IndexedStack). VPN is always present;
/// optional parts follow [SuitePartsState] (Settings remove/retain).
class SuiteShell extends StatefulWidget {
  const SuiteShell({
    super.key,
    required this.vpnTab,
    this.initialTabIndex = 0,
    this.walletTab,
    this.evolveTab,
    this.rpaiTab,
    this.partsStore,
    this.initialParts,
    this.onPartsChanged,
  });

  /// Residual VPN home (Connect / licence / settings) — required shipped surface.
  final Widget vpnTab;

  /// Index into **visible** destinations (0 = VPN always).
  final int initialTabIndex;

  /// Injectable wallet tab body (tests); production uses [SuiteWalletTab].
  final Widget? walletTab;

  /// Injectable evolve tab body (tests); production uses [SuiteEvolveTab].
  final Widget? evolveTab;

  /// Injectable Ned / rpAI tab (tests); production uses [SuiteRpaiTab].
  final Widget? rpaiTab;

  /// Durable optional-part install flags.
  final SuitePartsStore? partsStore;

  /// Injectable parts state (tests / sync after Settings).
  final SuitePartsState? initialParts;

  /// Notified when Settings (or shell) changes optional part install flags.
  final ValueChanged<SuitePartsState>? onPartsChanged;

  @override
  State<SuiteShell> createState() => SuiteShellState();
}

/// Public state for tests that select tabs programmatically.
class SuiteShellState extends State<SuiteShell> {
  late int _index;
  late SuitePartsState _parts;
  SuitePartsStore? _store;
  var _loadingParts = true;

  int get currentTabIndex => _index;

  SuitePartsState get partsState => _parts;

  SuitePartsStore? get partsStore => _store;

  void selectTab(int index) {
    final n = visibleSuitePartIds(_parts).length;
    if (index < 0 || index >= n) return;
    if (_index == index) return;
    setState(() => _index = index);
  }

  /// Apply new parts (e.g. after Settings) and clamp tab index.
  void applyParts(SuitePartsState next) {
    if (!mounted) return;
    setState(() {
      _parts = next;
      _index = clampSuiteTabIndex(_index, _parts);
      _loadingParts = false;
    });
    widget.onPartsChanged?.call(next);
  }

  Future<void> setPartInstalled(SuitePartId id, bool installed) async {
    final store = _store;
    SuitePartsState next;
    if (store != null) {
      next = await store.setInstalled(id, installed);
    } else {
      next = applySuitePartInstall(_parts, id: id, installed: installed);
    }
    applyParts(next);
  }

  @override
  void initState() {
    super.initState();
    _parts = widget.initialParts ?? SuitePartsState.allInstalled;
    _index = clampSuiteTabIndex(widget.initialTabIndex, _parts);
    _bootParts();
  }

  @override
  void didUpdateWidget(covariant SuiteShell oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialParts != null &&
        widget.initialParts != oldWidget.initialParts) {
      applyParts(widget.initialParts!);
    }
  }

  Future<void> _bootParts() async {
    final store = widget.partsStore ?? await _defaultPartsStore();
    if (!mounted) return;
    // Explicit initialParts wins over store load (tests + post-Settings sync).
    if (widget.initialParts != null) {
      setState(() {
        _store = store;
        _parts = widget.initialParts!;
        _index = clampSuiteTabIndex(_index, _parts);
        _loadingParts = false;
      });
      return;
    }
    final loaded = await store.load();
    if (!mounted) return;
    setState(() {
      _store = store;
      _parts = loaded;
      _index = clampSuiteTabIndex(_index, _parts);
      _loadingParts = false;
    });
  }

  Future<SuitePartsStore> _defaultPartsStore() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return SuitePartsStore(SharedPreferencesBackend(prefs));
    } catch (_) {
      return SuitePartsStore(MemorySettingsBackend());
    }
  }

  @override
  Widget build(BuildContext context) {
    final wallet = widget.walletTab ?? const SuiteWalletTab();
    final evolve = widget.evolveTab ?? const SuiteEvolveTab();
    final rpai = widget.rpaiTab ?? const SuiteRpaiTab();

    final visible = visibleSuitePartIds(_parts);
    final children = <Widget>[];
    final destinations = <NavigationDestination>[];

    for (final id in visible) {
      switch (id) {
        case SuitePartId.vpn:
          children.add(widget.vpnTab);
          destinations.add(const NavigationDestination(
            icon: Icon(Icons.shield_outlined),
            selectedIcon: Icon(Icons.shield),
            label: kSuiteTabVpn,
          ));
        case SuitePartId.wallet:
          children.add(wallet);
          destinations.add(const NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined),
            selectedIcon: Icon(Icons.account_balance_wallet),
            label: kSuiteTabWallet,
          ));
        case SuitePartId.evolve:
          children.add(evolve);
          destinations.add(const NavigationDestination(
            icon: Icon(Icons.auto_graph_outlined),
            selectedIcon: Icon(Icons.auto_graph),
            label: kSuiteTabEvolve,
          ));
        case SuitePartId.rpai:
          children.add(rpai);
          destinations.add(const NavigationDestination(
            icon: Icon(Icons.smart_toy_outlined),
            selectedIcon: Icon(Icons.smart_toy),
            label: kSuiteTabRpai,
          ));
      }
    }

    // Safety: VPN must always be present even if state is corrupt.
    if (children.isEmpty) {
      children.add(widget.vpnTab);
      destinations.add(const NavigationDestination(
        icon: Icon(Icons.shield_outlined),
        selectedIcon: Icon(Icons.shield),
        label: kSuiteTabVpn,
      ));
    }

    final tabIndex = clampSuiteTabIndex(_index, _parts);
    final chromeLabel = suitePartLabel(visibleSuitePartIds(_parts)[tabIndex]);

    return Scaffold(
      backgroundColor: kChromeBg,
      body: Column(
        children: [
          _SuiteChromeBar(tabLabel: chromeLabel),
          if (_loadingParts)
            const LinearProgressIndicator(minHeight: 2)
          else
            const SizedBox(height: 0),
          Expanded(
            child: IndexedStack(
              index: tabIndex,
              sizing: StackFit.expand,
              children: children,
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: tabIndex,
        onDestinationSelected: selectTab,
        backgroundColor: kPanelBg,
        indicatorColor: kLightAccent,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: destinations,
      ),
    );
  }
}

class _SuiteChromeBar extends StatelessWidget {
  const _SuiteChromeBar({required this.tabLabel});

  final String tabLabel;

  @override
  Widget build(BuildContext context) {
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
                  tabLabel,
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
