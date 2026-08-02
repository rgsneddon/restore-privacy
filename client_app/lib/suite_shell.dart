import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'prefs_backend.dart';
import 'settings_store.dart';
import 'suite_evolve_tab.dart';
import 'suite_nav.dart';
import 'suite_part_placeholder.dart';
import 'suite_parts.dart';
import 'suite_parts_store.dart';
import 'suite_rpai_tab.dart';
import 'suite_version.dart';
import 'suite_wallet_tab.dart';

/// Unified Restore Privacy Suite shell: flat main bottom bar.
///
/// Destinations: **VPN** · promoted **%/Evolve** surfaces (Analysis / Wallet /
/// Security / Voting / Credit as installed) · **rpAI**. Nested wallet/evolve
/// bottom bars are off on the Suite embed path.
///
/// Horizontal [PageView] uses natural orientation ([reverse] false): swipe
/// toward higher indices with the usual right-to-left finger motion. End
/// blocks at first and last destination (no wrap).
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

  /// Index into **visible** main destinations (0 = VPN always).
  final int initialTabIndex;

  /// Injectable wallet body (tests); production uses [SuiteWalletTab].
  final Widget? walletTab;

  /// Injectable evolve body (tests); production uses [SuiteEvolveTab].
  final Widget? evolveTab;

  /// Injectable Ned / rpAI tab (tests); production uses [SuiteRpaiTab].
  final Widget? rpaiTab;

  /// Durable optional-part install flags.
  final SuitePartsStore? partsStore;

  /// Bootstrap / parent-synced parts snapshot. Durable prefs still load on
  /// boot unless [preferInitialParts] is true (tests that force a snapshot).
  final SuitePartsState? initialParts;

  /// When true, skip durable [partsStore] load and keep [initialParts].
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

  /// Visible main-bar destinations for the current install flags.
  List<SuiteNavDest> get destinations => suiteNavDestinations(_parts);

  /// Test / chrome access to the horizontal pager (touch swipe path).
  PageController get pageController => _pageController;

  void selectTab(int index) {
    final n = destinations.length;
    if (index < 0 || index >= n) return;
    if (_index == index) {
      if (_pageController.hasClients &&
          (_pageController.page?.round() ?? _index) != index) {
        _pageController.jumpToPage(index);
      }
      return;
    }
    setState(() => _index = index);
    if (_pageController.hasClients) {
      _pageController.jumpToPage(index);
    }
  }

  /// Apply new parts (e.g. after Settings) and clamp tab index.
  void applyParts(SuitePartsState next, {bool notifyParent = false}) {
    if (!mounted) return;
    if (_parts == next && !_loadingParts) {
      if (notifyParent) widget.onPartsChanged?.call(next);
      return;
    }
    final nextIndex = clampSuiteNavIndex(_index, next);
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
    _index = clampSuiteNavIndex(widget.initialTabIndex, _parts);
    // Natural PageView (reverse:false) — swipe inverted from prior product.
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
      applyParts(widget.initialParts!);
    }
  }

  Future<void> _bootParts() async {
    final store = widget.partsStore ?? await _defaultPartsStore();
    if (!mounted) return;
    if (widget.preferInitialParts && widget.initialParts != null) {
      setState(() {
        _store = store;
        _parts = widget.initialParts!;
        _index = clampSuiteNavIndex(_index, _parts);
        _loadingParts = false;
      });
      return;
    }
    final loaded = await store.load();
    if (!mounted) return;
    setState(() {
      _store = store;
      _parts = loaded;
      _index = clampSuiteNavIndex(_index, _parts);
      _loadingParts = false;
    });
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

  Widget _bodyForDest(SuiteNavDest dest) {
    switch (dest) {
      case SuiteNavDest.vpn:
        return widget.vpnTab;
      case SuiteNavDest.rpai:
        if (suitePartShowsFullSurface(_parts, SuitePartId.rpai)) {
          return widget.rpaiTab ?? const SuiteRpaiTab();
        }
        return SuitePartReinstallPlaceholder(
          key: const Key('suite_part_placeholder_rpai'),
          partId: SuitePartId.rpai,
          onReinstall: () => reinstallPart(SuitePartId.rpai),
        );
      case SuiteNavDest.analysis:
      case SuiteNavDest.voting:
        // Evolve-only surfaces — Suite main bar; no nested bottom bar.
        if (widget.evolveTab != null) return widget.evolveTab!;
        if (!suitePartShowsFullSurface(_parts, SuitePartId.evolve)) {
          return SuitePartReinstallPlaceholder(
            key: const Key('suite_part_placeholder_evolve'),
            partId: SuitePartId.evolve,
            onReinstall: () => reinstallPart(SuitePartId.evolve),
          );
        }
        return SuiteEvolveTab(
          key: ValueKey('suite_evolve_${dest.name}'),
          showShellBottomBar: false,
          shellTabIndex: suiteNavEvolveShellTabIndex(dest),
        );
      case SuiteNavDest.wallet:
      case SuiteNavDest.security:
      case SuiteNavDest.credit:
        // Shared % / Evolve family (one product link). Prefer wallet inject only
        // when the wallet part is installed; else Evolve when installed.
        if (widget.walletTab != null &&
            suitePartShowsFullSurface(_parts, SuitePartId.wallet)) {
          return widget.walletTab!;
        }
        if (widget.evolveTab != null &&
            suitePartShowsFullSurface(_parts, SuitePartId.evolve)) {
          return widget.evolveTab!;
        }
        if (suitePartShowsFullSurface(_parts, SuitePartId.evolve)) {
          return SuiteEvolveTab(
            key: ValueKey('suite_family_${dest.name}'),
            showShellBottomBar: false,
            shellTabIndex: suiteNavEvolveShellTabIndex(dest),
          );
        }
        if (suitePartShowsFullSurface(_parts, SuitePartId.wallet)) {
          return SuiteWalletTab(
            key: ValueKey('suite_wallet_${dest.name}'),
            showShellBottomBar: false,
            shellTabIndex: suiteNavWalletShellTabIndex(dest),
          );
        }
        return SuitePartReinstallPlaceholder(
          key: const Key('suite_part_placeholder_wallet'),
          partId: SuitePartId.wallet,
          onReinstall: () => reinstallPart(SuitePartId.wallet),
        );
    }
  }

  void _onPageChanged(int page) {
    final next = clampSuiteNavIndex(page, _parts);
    if (next == _index) return;
    setState(() => _index = next);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final dests = destinations;
    final children = dests.map(_bodyForDest).toList(growable: false);
    final navDestinations = <NavigationDestination>[
      for (final d in dests)
        NavigationDestination(
          icon: Icon(_iconFor(d, selected: false)),
          selectedIcon: Icon(_iconFor(d, selected: true)),
          label: suiteNavLabel(d),
        ),
    ];

    final tabIndex = clampSuiteNavIndex(_index, _parts);
    final chromeLabel =
        dests.isEmpty ? kSuiteTabVpn : suiteNavLabel(dests[tabIndex]);

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
              // Reversed product swipe: natural pager (reverse:false).
              reverse: false,
              controller: _pageController,
              onPageChanged: _onPageChanged,
              physics: const BouncingScrollPhysics(
                parent: AlwaysScrollableScrollPhysics(),
              ),
              children: [
                for (final child in children)
                  _SuiteKeepAlivePage(child: child),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        key: const Key('suite_shell_main_nav'),
        selectedIndex: tabIndex.clamp(0, navDestinations.length - 1),
        onDestinationSelected: selectTab,
        backgroundColor: scheme.surface,
        indicatorColor: scheme.primary.withValues(alpha: 0.28),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: navDestinations,
      ),
    );
  }

  static IconData _iconFor(SuiteNavDest dest, {required bool selected}) {
    switch (dest) {
      case SuiteNavDest.vpn:
        return selected ? Icons.shield : Icons.shield_outlined;
      case SuiteNavDest.analysis:
        return selected ? Icons.analytics : Icons.analytics_outlined;
      case SuiteNavDest.wallet:
        return selected
            ? Icons.account_balance_wallet
            : Icons.account_balance_wallet_outlined;
      case SuiteNavDest.security:
        return selected ? Icons.security : Icons.security_outlined;
      case SuiteNavDest.voting:
        return selected ? Icons.how_to_vote : Icons.how_to_vote_outlined;
      case SuiteNavDest.credit:
        return selected ? Icons.info : Icons.info_outline;
      case SuiteNavDest.rpai:
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
