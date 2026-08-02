import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'prefs_backend.dart';
import 'settings_store.dart';
import 'suite_evolve_tab.dart';
import 'suite_part_placeholder.dart';
import 'suite_parts.dart';
import 'suite_parts_store.dart';
import 'suite_rpai_tab.dart';
import 'suite_version.dart';
import 'suite_wallet_tab.dart';

/// Unified Restore Privacy Suite shell: **VPN** · **%** · **EVOLVE** · **rpAI**.
///
/// Horizontal [PageView] (reversed) so **left-to-right** swipe advances along
/// the product order VPN → % → Evolve → rpAI; right-to-left walks back. End
/// blocks at VPN and rpAI (no wrap). Bottom nav stays in sync with the pager.
/// Uninstalled optional parts keep a reinstall placeholder body.
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
    this.preferInitialParts = false,
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

  /// Bootstrap / parent-synced parts snapshot. Durable prefs still load on
  /// boot unless [preferInitialParts] is true (tests that force a snapshot).
  final SuitePartsState? initialParts;

  /// When true, skip durable [partsStore] load and keep [initialParts].
  /// Production leaves this false so cold start applies SharedPreferences.
  final bool preferInitialParts;

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
  late final PageController _pageController;

  int get currentTabIndex => _index;

  SuitePartsState get partsState => _parts;

  SuitePartsStore? get partsStore => _store;

  /// Test / chrome access to the horizontal pager (touch swipe path).
  PageController get pageController => _pageController;

  void selectTab(int index) {
    final n = visibleSuitePartIds(_parts).length;
    if (index < 0 || index >= n) return;
    if (_index == index) {
      // Still snap pager if desynced.
      if (_pageController.hasClients &&
          (_pageController.page?.round() ?? _index) != index) {
        _pageController.jumpToPage(index);
      }
      return;
    }
    setState(() => _index = index);
    if (_pageController.hasClients) {
      // jumpToPage keeps tests / programmatic select in sync without waiting
      // for an animation; touch users still get fling physics on the pager.
      _pageController.jumpToPage(index);
    }
  }

  /// Apply new parts (e.g. after Settings) and clamp tab index.
  ///
  /// Does not re-notify [onPartsChanged] (caller / Settings already owns notify).
  void applyParts(SuitePartsState next, {bool notifyParent = false}) {
    if (!mounted) return;
    if (_parts == next && !_loadingParts) {
      if (notifyParent) widget.onPartsChanged?.call(next);
      return;
    }
    final nextIndex = clampSuiteTabIndex(_index, next);
    setState(() {
      _parts = next;
      _index = nextIndex;
      _loadingParts = false;
    });
    if (_pageController.hasClients &&
        (_pageController.page?.round() ?? nextIndex) != nextIndex) {
      _pageController.jumpToPage(nextIndex);
    }
    if (notifyParent) widget.onPartsChanged?.call(next);
  }

  Future<void> setPartInstalled(
    SuitePartId id,
    bool installed, {
    String? confirmPhrase,
  }) async {
    final store = _store;
    SuitePartsState next;
    if (store != null) {
      next = await store.setInstalled(
        id,
        installed,
        confirmPhrase: confirmPhrase,
      );
    } else {
      next = applySuitePartInstall(
        _parts,
        id: id,
        installed: installed,
        confirmPhrase: confirmPhrase,
      );
    }
    applyParts(next, notifyParent: true);
  }

  Future<void> reinstallPart(SuitePartId id) async {
    await setPartInstalled(id, true);
  }

  @override
  void initState() {
    super.initState();
    _parts = widget.initialParts ?? SuitePartsState.allInstalled;
    _index = clampSuiteTabIndex(widget.initialTabIndex, _parts);
    // reverse:true → left-to-right finger motion advances VPN→%→Evolve→rpAI
    _pageController = PageController(initialPage: _index);
    _bootParts();
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant SuiteShell oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.preferInitialParts &&
        widget.initialParts != null &&
        widget.initialParts != oldWidget.initialParts) {
      applyParts(widget.initialParts!);
    } else if (!widget.preferInitialParts &&
        widget.initialParts != null &&
        widget.initialParts != _parts &&
        widget.initialParts != oldWidget.initialParts) {
      // Parent synced from Settings — apply without re-notifying parent.
      applyParts(widget.initialParts!);
    }
  }

  Future<void> _bootParts() async {
    final store = widget.partsStore ?? await _defaultPartsStore();
    if (!mounted) return;
    // Tests may force a snapshot; production always loads durable prefs.
    if (widget.preferInitialParts && widget.initialParts != null) {
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
    // Sync parent (RestorePrivacyApp / TunnelHome) so Settings matches nav.
    widget.onPartsChanged?.call(loaded);
  }

  Future<SuitePartsStore> _defaultPartsStore() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return SuitePartsStore(SharedPreferencesBackend(prefs));
    } catch (_) {
      return SuitePartsStore(MemorySettingsBackend());
    }
  }

  Widget _bodyForPart(SuitePartId id) {
    final full = suitePartShowsFullSurface(_parts, id);
    switch (id) {
      case SuitePartId.vpn:
        return widget.vpnTab;
      case SuitePartId.wallet:
        if (full) return widget.walletTab ?? const SuiteWalletTab();
        return SuitePartReinstallPlaceholder(
          key: const Key('suite_part_placeholder_wallet'),
          partId: id,
          onReinstall: () => reinstallPart(id),
        );
      case SuitePartId.evolve:
        if (full) return widget.evolveTab ?? const SuiteEvolveTab();
        return SuitePartReinstallPlaceholder(
          key: const Key('suite_part_placeholder_evolve'),
          partId: id,
          onReinstall: () => reinstallPart(id),
        );
      case SuitePartId.rpai:
        if (full) return widget.rpaiTab ?? const SuiteRpaiTab();
        return SuitePartReinstallPlaceholder(
          key: const Key('suite_part_placeholder_rpai'),
          partId: id,
          onReinstall: () => reinstallPart(id),
        );
    }
  }

  void _onPageChanged(int page) {
    final next = clampSuiteTabIndex(page, _parts);
    if (next == _index) return;
    setState(() => _index = next);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final visible = visibleSuitePartIds(_parts);
    final children = visible.map(_bodyForPart).toList(growable: false);
    final destinations = <NavigationDestination>[
      for (final id in visible)
        NavigationDestination(
          icon: Icon(_iconFor(id, selected: false)),
          selectedIcon: Icon(_iconFor(id, selected: true)),
          label: suitePartLabel(id),
        ),
    ];

    final tabIndex = clampSuiteTabIndex(_index, _parts);
    final chromeLabel = suitePartLabel(visible[tabIndex]);

    return Scaffold(
      key: const Key('suite_shell_scaffold'),
      backgroundColor: theme.scaffoldBackgroundColor,
      body: Column(
        children: [
          _SuiteChromeBar(tabLabel: chromeLabel),
          if (_loadingParts)
            LinearProgressIndicator(
              minHeight: 2,
              color: scheme.primary,
              backgroundColor: scheme.surface,
            )
          else
            const SizedBox(height: 0),
          Expanded(
            child: PageView(
              key: const Key('suite_shell_page_view'),
              // Product: left-to-right swipe advances VPN→%→Evolve→rpAI.
              reverse: true,
              controller: _pageController,
              onPageChanged: _onPageChanged,
              physics: const BouncingScrollPhysics(
                parent: AlwaysScrollableScrollPhysics(),
              ),
              // Keep each suite surface mounted after first visit (VPN session).
              children: [
                for (final child in children)
                  _SuiteKeepAlivePage(child: child),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: tabIndex,
        onDestinationSelected: selectTab,
        backgroundColor: scheme.surface,
        indicatorColor: scheme.primary.withValues(alpha: 0.28),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: destinations,
      ),
    );
  }

  static IconData _iconFor(SuitePartId id, {required bool selected}) {
    switch (id) {
      case SuitePartId.vpn:
        return selected ? Icons.shield : Icons.shield_outlined;
      case SuitePartId.wallet:
        return selected
            ? Icons.account_balance_wallet
            : Icons.account_balance_wallet_outlined;
      case SuitePartId.evolve:
        return selected ? Icons.auto_graph : Icons.auto_graph_outlined;
      case SuitePartId.rpai:
        return selected ? Icons.smart_toy : Icons.smart_toy_outlined;
    }
  }
}

/// Keeps suite tab bodies alive once visited (residual VPN must not dispose).
class _SuiteKeepAlivePage extends StatefulWidget {
  const _SuiteKeepAlivePage({required this.child});

  final Widget child;

  @override
  State<_SuiteKeepAlivePage> createState() => _SuiteKeepAlivePageState();
}

class _SuiteKeepAlivePageState extends State<_SuiteKeepAlivePage>
    with AutomaticKeepAliveClientMixin {
  @override
  bool get wantKeepAlive => true;

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return widget.child;
  }
}

class _SuiteChromeBar extends StatelessWidget {
  const _SuiteChromeBar({required this.tabLabel});

  final String tabLabel;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.primary,
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
                      style: TextStyle(
                        color: scheme.onPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      kSuiteDisplayVersion,
                      style: TextStyle(
                        color: scheme.onPrimary.withValues(alpha: 0.9),
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
                  color: scheme.onPrimary.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  tabLabel,
                  style: TextStyle(
                    color: scheme.onPrimary,
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
