import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'prefs_backend.dart';
import 'settings_store.dart';
import 'suite_family_host.dart';
import 'suite_nav.dart';
import 'suite_part_placeholder.dart';
import 'suite_parts.dart';
import 'suite_parts_store.dart';
import 'suite_rpai_tab.dart';
import 'suite_version.dart';

/// Unified Restore Privacy Suite shell: flat main bottom bar.
///
/// Destinations: **VPN** · promoted **%/Evolve** surfaces (Analysis / Wallet /
/// Backup / Voting / Credit as installed + entitled) · **rpAI**. Nested
/// wallet/evolve bottom bars are off on the Suite embed path. Family pages share
/// one [SuiteFamilyHost] bootstrap (not one provider tree per tab).
///
/// Horizontal [PageView] uses natural orientation ([reverse] false). End blocks
/// at first and last destination (no wrap). When only one destination is
/// visible, the bottom [NavigationBar] is omitted (Material requires ≥2).
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
    this.familyBoot,
  });

  final Widget vpnTab;
  final int initialTabIndex;
  final Widget? walletTab;
  final Widget? evolveTab;
  final Widget? rpaiTab;
  final SuitePartsStore? partsStore;
  final SuitePartsState? initialParts;
  final bool preferInitialParts;
  final ValueChanged<SuitePartsState>? onPartsChanged;

  /// Test seam: inject ready %/Evolve providers (skips live path_provider boot).
  final SuiteFamilyBootFn? familyBoot;

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

  /// Evolve wallet app-access (drives Analysis/Voting visibility).
  bool _hasAppAccess = true;

  int get currentTabIndex => _index;

  SuitePartsState get partsState => _parts;

  SuitePartsStore? get partsStore => _store;

  bool get hasAppAccess => _hasAppAccess;

  /// Visible main-bar destinations for the current install + access flags.
  List<SuiteNavDest> get destinations =>
      suiteNavDestinations(_parts, hasAppAccess: _hasAppAccess);

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

  void applyParts(SuitePartsState next, {bool notifyParent = false}) {
    if (!mounted) return;
    if (_parts == next && !_loadingParts) {
      if (notifyParent) widget.onPartsChanged?.call(next);
      return;
    }
    final nextIndex = clampSuiteNavIndex(
      _index,
      next,
      hasAppAccess: _hasAppAccess,
    );
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
    // Fresh default is VPN + rpAI until store load or explicit initialParts.
    _parts = widget.initialParts ?? SuitePartsState.vpnAndRpai;
    _index = clampSuiteNavIndex(
      widget.initialTabIndex,
      _parts,
      hasAppAccess: _hasAppAccess,
    );
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
        _index = clampSuiteNavIndex(
          _index,
          _parts,
          hasAppAccess: _hasAppAccess,
        );
        _loadingParts = false;
      });
      return;
    }
    final loaded = await store.load();
    if (!mounted) return;
    setState(() {
      _store = store;
      _parts = loaded;
      _index = clampSuiteNavIndex(
        _index,
        _parts,
        hasAppAccess: _hasAppAccess,
      );
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

  void _onHasAppAccessChanged(bool next) {
    if (!mounted || next == _hasAppAccess) return;
    // When access becomes true after rehydrate, expand Analysis/Voting.
    // When false after a true flash, still apply (honest cold install) — family
    // host is responsible for rehydrating Suite-registered sessions first so
    // this false path is not a false negative right after account create.
    final nextIndex = clampSuiteNavIndex(
      _index,
      _parts,
      hasAppAccess: next,
    );
    setState(() {
      _hasAppAccess = next;
      _index = nextIndex;
    });
    if (_pageController.hasClients &&
        (_pageController.page?.round() ?? nextIndex) != nextIndex) {
      _pageController.jumpToPage(nextIndex);
    }
  }

  bool get _hasFamilyInstall =>
      suitePartShowsFullSurface(_parts, SuitePartId.wallet) ||
      suitePartShowsFullSurface(_parts, SuitePartId.evolve);

  /// Production family path (no test inject overrides).
  bool get _useSharedFamilyHost {
    if (widget.walletTab != null || widget.evolveTab != null) {
      return false;
    }
    return _hasFamilyInstall;
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
      case SuiteNavDest.wallet:
      case SuiteNavDest.security:
      case SuiteNavDest.credit:
        // Test injects: one stub widget per dest (no multi-bootstrap).
        if (widget.evolveTab != null &&
            suitePartShowsFullSurface(_parts, SuitePartId.evolve) &&
            (dest == SuiteNavDest.analysis ||
                dest == SuiteNavDest.voting ||
                !suitePartShowsFullSurface(_parts, SuitePartId.wallet))) {
          return widget.evolveTab!;
        }
        if (widget.walletTab != null &&
            suitePartShowsFullSurface(_parts, SuitePartId.wallet) &&
            (dest == SuiteNavDest.wallet ||
                dest == SuiteNavDest.security ||
                dest == SuiteNavDest.credit)) {
          return widget.walletTab!;
        }
        if (widget.evolveTab != null &&
            suitePartShowsFullSurface(_parts, SuitePartId.evolve)) {
          return widget.evolveTab!;
        }
        // Production: shared host provides providers; body only.
        if (_useSharedFamilyHost) {
          return SuiteFamilyBody(
            key: ValueKey('family_body_${dest.name}'),
            dest: dest,
            parts: _parts,
            hasAppAccess: _hasAppAccess,
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
    final next = clampSuiteNavIndex(
      page,
      _parts,
      hasAppAccess: _hasAppAccess,
    );
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

    final tabIndex = clampSuiteNavIndex(
      _index,
      _parts,
      hasAppAccess: _hasAppAccess,
    );
    final chromeLabel =
        dests.isEmpty ? kSuiteTabVpn : suiteNavLabel(dests[tabIndex]);

    Widget pageView = PageView(
      key: const Key('suite_shell_page_view'),
      reverse: false,
      controller: _pageController,
      onPageChanged: _onPageChanged,
      physics: const BouncingScrollPhysics(
        parent: AlwaysScrollableScrollPhysics(),
      ),
      children: [
        for (final child in children) _SuiteKeepAlivePage(child: child),
      ],
    );

    // One family bootstrap for all promoted %/Evolve pages.
    if (_useSharedFamilyHost) {
      pageView = SuiteFamilyHost(
        key: const Key('suite_family_host'),
        parts: _parts,
        onHasAppAccessChanged: _onHasAppAccessChanged,
        boot: widget.familyBoot,
        child: pageView,
      );
    }

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
          Expanded(child: pageView),
        ],
      ),
      // Material NavigationBar requires ≥2 destinations.
      bottomNavigationBar: navDestinations.length >= 2
          ? NavigationBar(
              key: const Key('suite_shell_main_nav'),
              selectedIndex: tabIndex.clamp(0, navDestinations.length - 1),
              onDestinationSelected: selectTab,
              backgroundColor: scheme.surface,
              indicatorColor: scheme.primary.withValues(alpha: 0.28),
              labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
              destinations: navDestinations,
            )
          : null,
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
        // Backup/restore surface — not shield/security chrome.
        return selected
            ? Icons.settings_backup_restore
            : Icons.backup_outlined;
      case SuiteNavDest.voting:
        return selected ? Icons.how_to_vote : Icons.how_to_vote_outlined;
      case SuiteNavDest.credit:
        return selected ? Icons.info : Icons.info_outline;
      case SuiteNavDest.rpai:
        return selected ? Icons.smart_toy : Icons.smart_toy_outlined;
    }
  }
}

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
