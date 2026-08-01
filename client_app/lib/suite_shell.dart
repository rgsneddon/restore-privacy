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
import 'theme.dart';

/// Unified Restore Privacy Suite shell: **VPN** · **%** · **EVOLVE** · **rpAI**.
///
/// Tab switch keeps the process alive (IndexedStack). All four tabs stay in the
/// nav; uninstalled optional parts show a reinstall placeholder body.
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
  ///
  /// Does not re-notify [onPartsChanged] (caller / Settings already owns notify).
  void applyParts(SuitePartsState next, {bool notifyParent = false}) {
    if (!mounted) return;
    if (_parts == next && !_loadingParts) {
      if (notifyParent) widget.onPartsChanged?.call(next);
      return;
    }
    setState(() {
      _parts = next;
      _index = clampSuiteTabIndex(_index, _parts);
      _loadingParts = false;
    });
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
    _bootParts();
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

  @override
  Widget build(BuildContext context) {
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
