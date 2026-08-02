/// Single shared % / Evolve provider boot for all promoted family destinations.
///
/// Wraps the Suite [PageView] with providers only (no [Theme]) so VPN / rpAI
/// keep suite chrome. [SuiteFamilyBody] applies Evolve/wallet theme locally.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'package:evolve/data/outcome_registry.dart';
import 'package:evolve/fcg/providers/fcg_voting_provider.dart';
import 'package:evolve/l10n/app_localizations.dart' as evolve_l10n;
import 'package:evolve/models/analysis_mode.dart';
import 'package:evolve/models/evolve_result.dart';
import 'package:evolve/models/locale_config.dart';
import 'package:evolve/models/locale_config_ui.dart';
import 'package:evolve/models/scenario_input.dart';
import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;
import 'package:evolve/perc/services/perc_network_config.dart' as evolve_net;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
import 'package:evolve/perc/widgets/registration_seed_setup_dialog.dart'
    as evolve_reg;
import 'package:evolve/providers/evolve_provider.dart';
import 'package:evolve/providers/locale_provider.dart' as evolve_locale;
import 'package:evolve/screens/evolve_shell_screen.dart';
import 'package:evolve/theme/app_theme.dart' as evolve_theme;

import 'package:perccent_wallet/l10n/wallet_only_localizations.dart';
import 'package:perccent_wallet/perc/providers/perc_wallet_provider.dart'
    as wallet_p;
import 'package:perccent_wallet/perc/services/perc_ledger_hub.dart' as wallet_hub;
import 'package:perccent_wallet/perc/services/perc_network_config.dart'
    as wallet_net;
import 'package:perccent_wallet/perc/services/perc_network_coordinator.dart'
    as wallet_coord;
import 'package:perccent_wallet/perc/widgets/registration_seed_setup_dialog.dart'
    as wallet_reg;
import 'package:perccent_wallet/providers/locale_provider.dart' as wallet_locale;
import 'package:perccent_wallet/screens/wallet_shell_screen.dart';
import 'package:perccent_wallet/theme/app_theme.dart' as wallet_theme;
import 'package:perccent_wallet/wallet_core/models/locale_config_ui.dart';

import 'suite_account.dart';
import 'suite_nav.dart';
import 'suite_parts.dart';
import 'theme.dart';

/// Boots family providers once; exposes them via [MultiProvider] without Theme.
class SuiteFamilyHost extends StatefulWidget {
  const SuiteFamilyHost({
    super.key,
    required this.parts,
    required this.child,
    this.onHasAppAccessChanged,
  });

  final SuitePartsState parts;
  final Widget child;

  /// Notified when Evolve wallet [hasAppAccess] changes (main-bar dest set).
  final ValueChanged<bool>? onHasAppAccessChanged;

  @override
  State<SuiteFamilyHost> createState() => SuiteFamilyHostState();
}

class SuiteFamilyHostState extends State<SuiteFamilyHost> {
  EvolveProvider? _evolve;
  evolve_wallet.PercWalletProvider? _evolveWallet;
  FcgVotingProvider? _fcg;
  evolve_locale.LocaleProvider? _evolveLocale;

  wallet_p.PercWalletProvider? _walletOnly;
  wallet_locale.LocaleProvider? _walletLocale;

  bool _ready = false;
  Object? _error;
  bool _hasAppAccess = true;

  bool get hasAppAccess => _hasAppAccess;

  bool get useEvolvePackage =>
      suitePartShowsFullSurface(widget.parts, SuitePartId.evolve);

  bool get useWalletOnlyPackage =>
      !useEvolvePackage &&
      suitePartShowsFullSurface(widget.parts, SuitePartId.wallet);

  @override
  void initState() {
    super.initState();
    SuiteAccountBus.instance.addListener(_onSuiteAccountChanged);
    _boot();
  }

  @override
  void didUpdateWidget(covariant SuiteFamilyHost oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.parts.evolveInstalled != widget.parts.evolveInstalled ||
        oldWidget.parts.walletInstalled != widget.parts.walletInstalled) {
      _boot();
    }
  }

  @override
  void dispose() {
    SuiteAccountBus.instance.removeListener(_onSuiteAccountChanged);
    _evolveWallet?.removeListener(_onEvolveWalletChanged);
    super.dispose();
  }

  void _onSuiteAccountChanged() {
    unawaited(_reloadLedgers());
  }

  void _onEvolveWalletChanged() {
    final w = _evolveWallet;
    if (w == null) return;
    final next = w.hasAppAccess;
    if (next == _hasAppAccess) return;
    setState(() => _hasAppAccess = next);
    widget.onHasAppAccessChanged?.call(next);
  }

  Future<void> _reloadLedgers() async {
    try {
      if (_evolveWallet != null) {
        await evolve_hub.PercLedgerHub.instance.reloadFromStore();
      }
      if (_walletOnly != null) {
        await wallet_hub.PercLedgerHub.instance.reloadFromStore();
      }
    } catch (_) {}
  }

  Future<void> _boot() async {
    setState(() {
      _ready = false;
      _error = null;
    });
    try {
      if (useEvolvePackage) {
        await _bootEvolve();
      } else if (useWalletOnlyPackage) {
        await _bootWalletOnly();
      } else {
        if (!mounted) return;
        setState(() {
          _ready = true;
          _error = null;
        });
        return;
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _ready = false;
      });
    }
  }

  Future<void> _bootEvolve() async {
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = false;
    evolve_net.PercNetworkConfig.resetForTest();
    await evolve_net.PercNetworkConfig.load();
    try {
      await OutcomeRegistry.ensureLoaded();
    } catch (_) {
      OutcomeRegistry.bundled();
    }

    final locale = evolve_locale.LocaleProvider();
    await locale.initialize();
    final evolve = EvolveProvider();
    final wallet = evolve_wallet.PercWalletProvider();
    final fcg = FcgVotingProvider();

    // Match prior AppBootstrap path: wallet session must initialize before shell.
    await wallet.initialize();
    await evolve.initialize();
    await fcg.initialize();
    try {
      await evolve_hub.PercLedgerHub.instance.reloadFromStore();
    } catch (_) {}

    evolve.setLocale(locale.config);
    evolve.analysisRewardHandler = ({
      required AnalysisMode mode,
      required double outcomeScore,
      String? memo,
      double? continuumScs,
      double? vortexScs,
      double? shearScs,
      double? resistanceScs,
      double? flowScs,
    }) =>
        wallet.creditAnalysis(
          mode: mode,
          outcomeScore: outcomeScore,
          memo: memo,
          continuumScs: continuumScs,
          vortexScs: vortexScs,
          shearScs: shearScs,
          resistanceScs: resistanceScs,
          flowScs: flowScs,
        );
    evolve.scenarioRunRecorder = ({
      required ScenarioInput input,
      required LocaleConfig locale,
      required AnalysisMode mode,
      required EvolveResult result,
    }) =>
        fcg.recordScenarioRun(
          input: input,
          locale: locale,
          mode: mode,
          result: result,
        );

    _evolveWallet?.removeListener(_onEvolveWalletChanged);
    wallet.addListener(_onEvolveWalletChanged);

    if (!mounted) return;
    setState(() {
      _evolve = evolve;
      _evolveWallet = wallet;
      _fcg = fcg;
      _evolveLocale = locale;
      _walletOnly = null;
      _walletLocale = null;
      _hasAppAccess = wallet.hasAppAccess;
      _ready = true;
      _error = null;
    });
    widget.onHasAppAccessChanged?.call(_hasAppAccess);
  }

  Future<void> _bootWalletOnly() async {
    wallet_coord.PercNetworkCoordinator.disableLiveNodesForTests = false;
    wallet_net.PercNetworkConfig.resetForTest();
    await wallet_net.PercNetworkConfig.load();
    final locale = wallet_locale.LocaleProvider();
    await locale.initialize();
    final wallet = wallet_p.PercWalletProvider();
    await wallet.initialize();
    try {
      await wallet_hub.PercLedgerHub.instance.reloadFromStore();
    } catch (_) {}

    if (!mounted) return;
    setState(() {
      _walletOnly = wallet;
      _walletLocale = locale;
      _evolve = null;
      _evolveWallet = null;
      _fcg = null;
      _evolveLocale = null;
      _hasAppAccess = true;
      _ready = true;
      _error = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    // Providers only — never Theme/Localizations around the Suite PageView
    // (VPN/rpAI must keep suite chrome).
    Widget body = _FamilyHostScope(
      ready: _ready,
      error: _error,
      hasAppAccess: _hasAppAccess,
      onRetry: _boot,
      useEvolve: useEvolvePackage,
      evolveLocale: _evolveLocale,
      walletLocale: _walletLocale,
      child: widget.child,
    );

    if (_ready &&
        useEvolvePackage &&
        _evolve != null &&
        _evolveWallet != null &&
        _evolveLocale != null &&
        _fcg != null) {
      body = MultiProvider(
        providers: [
          ChangeNotifierProvider<evolve_locale.LocaleProvider>.value(
            value: _evolveLocale!,
          ),
          ChangeNotifierProvider<EvolveProvider>.value(value: _evolve!),
          ChangeNotifierProvider<evolve_wallet.PercWalletProvider>.value(
            value: _evolveWallet!,
          ),
          ChangeNotifierProvider<FcgVotingProvider>.value(value: _fcg!),
        ],
        child: body,
      );
    } else if (_ready &&
        useWalletOnlyPackage &&
        _walletOnly != null &&
        _walletLocale != null) {
      body = MultiProvider(
        providers: [
          ChangeNotifierProvider<wallet_locale.LocaleProvider>.value(
            value: _walletLocale!,
          ),
          ChangeNotifierProvider<wallet_p.PercWalletProvider>.value(
            value: _walletOnly!,
          ),
        ],
        child: body,
      );
    }

    return body;
  }
}

/// Loading / error / package mode for [SuiteFamilyBody] (VPN pages ignore).
class _FamilyHostScope extends InheritedWidget {
  const _FamilyHostScope({
    required this.ready,
    required this.error,
    required this.hasAppAccess,
    required this.onRetry,
    required this.useEvolve,
    required this.evolveLocale,
    required this.walletLocale,
    required super.child,
  });

  final bool ready;
  final Object? error;
  final bool hasAppAccess;
  final VoidCallback onRetry;
  final bool useEvolve;
  final evolve_locale.LocaleProvider? evolveLocale;
  final wallet_locale.LocaleProvider? walletLocale;

  static _FamilyHostScope? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<_FamilyHostScope>();

  @override
  bool updateShouldNotify(covariant _FamilyHostScope oldWidget) =>
      ready != oldWidget.ready ||
      error != oldWidget.error ||
      hasAppAccess != oldWidget.hasAppAccess ||
      useEvolve != oldWidget.useEvolve;
}

/// Body for one family destination — themed locally; no nested bottom bar.
class SuiteFamilyBody extends StatelessWidget {
  const SuiteFamilyBody({
    super.key,
    required this.dest,
    required this.parts,
    required this.hasAppAccess,
  });

  final SuiteNavDest dest;
  final SuitePartsState parts;
  final bool hasAppAccess;

  @override
  Widget build(BuildContext context) {
    final scope = _FamilyHostScope.maybeOf(context);
    if (scope != null && scope.error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('${scope.error}', textAlign: TextAlign.center),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: scope.onRetry,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }
    if (scope != null && !scope.ready) {
      return Center(
        child: CircularProgressIndicator(color: suitePrimaryOf(context)),
      );
    }

    final access = scope?.hasAppAccess ?? hasAppAccess;
    final useEvolve = suitePartShowsFullSurface(parts, SuitePartId.evolve);

    if (useEvolve) {
      final idx = suiteNavEvolveShellTabIndex(
        dest,
        hasAppAccess: access,
      );
      if (idx == null) {
        return const Center(child: Text('Unavailable'));
      }
      final locale = scope?.evolveLocale;
      Widget shell = EvolveShellScreen(
        key: ValueKey('suite_family_evolve_$idx'),
        showBottomBar: false,
        tabIndex: idx,
      );
      // Registration / seed host (same gate as AppBootstrap path).
      shell = evolve_reg.RegistrationSeedSetupDialogHost(child: shell);
      // Theme only around family body — not Suite VPN/rpAI pages.
      if (locale != null) {
        return Theme(
          data: evolve_theme.AppTheme.dark(),
          child: Localizations(
            locale: locale.config.materialLocale,
            delegates: const [
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            child: Builder(
              builder: (context) {
                evolve_l10n.AppLocalizations.of(locale.config);
                return shell;
              },
            ),
          ),
        );
      }
      return Theme(
        data: evolve_theme.AppTheme.dark(),
        child: shell,
      );
    }

    if (suitePartShowsFullSurface(parts, SuitePartId.wallet)) {
      final idx = suiteNavWalletShellTabIndex(dest);
      if (idx == null) {
        return const Center(child: Text('Unavailable'));
      }
      final locale = scope?.walletLocale;
      Widget shell = WalletShellScreen(
        key: ValueKey('suite_family_wallet_$idx'),
        showBottomBar: false,
        tabIndex: idx,
      );
      shell = wallet_reg.RegistrationSeedSetupDialogHost(child: shell);
      if (locale != null) {
        return Theme(
          data: wallet_theme.AppTheme.dark(),
          child: Localizations(
            locale: locale.config.materialLocale,
            delegates: const [
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            child: Builder(
              builder: (context) {
                walletLocalizationsOf(locale.config);
                return shell;
              },
            ),
          ),
        );
      }
      return Theme(
        data: wallet_theme.AppTheme.dark(),
        child: shell,
      );
    }
    return const SizedBox.shrink();
  }
}
