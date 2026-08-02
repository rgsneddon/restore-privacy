import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'package:evolve/data/outcome_registry.dart';
import 'package:evolve/fcg/providers/fcg_voting_provider.dart';
import 'package:evolve/l10n/app_localizations.dart';
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
import 'package:evolve/providers/evolve_provider.dart';
import 'package:evolve/providers/locale_provider.dart' as evolve_locale;
import 'package:evolve/screens/app_bootstrap_screen.dart';
import 'package:evolve/theme/app_theme.dart';

import 'suite_account.dart';
import 'theme.dart';

// suiteEvolveInheritsSuiteLogin / suiteEvolveShowsLoginWall live in suite_account.dart

/// **EVOLVE** tab — full Evolve Chronoflux app (bootstrap → analysis shell).
///
/// Embeds the shipped evolve package surfaces; not a stub. Suite account is
/// optional and shared with Perccent (% tab) via [SuiteAccountBus].
class SuiteEvolveTab extends StatefulWidget {
  const SuiteEvolveTab({
    super.key,
    this.evolveProvider,
    this.walletProvider,
    this.fcgProvider,
    this.localeProvider,
    this.child,
    this.showShellBottomBar = false,
    this.shellTabIndex,
    this.accountStore,
  });

  final EvolveProvider? evolveProvider;
  final evolve_wallet.PercWalletProvider? walletProvider;
  final FcgVotingProvider? fcgProvider;
  final evolve_locale.LocaleProvider? localeProvider;

  /// When set, replaces bootstrap (tests inject a ready surface).
  final Widget? child;

  /// Suite path: nested shell bottom bar off (main bar owns destinations).
  final bool showShellBottomBar;

  /// Suite path: which evolve shell tab body to show.
  final int? shellTabIndex;

  /// Optional Suite account store — used to inherit first-run registration.
  final SuiteAccountStore? accountStore;

  @override
  State<SuiteEvolveTab> createState() => _SuiteEvolveTabState();
}

class _SuiteEvolveTabState extends State<SuiteEvolveTab> {
  EvolveProvider? _evolve;
  evolve_wallet.PercWalletProvider? _wallet;
  FcgVotingProvider? _fcg;
  evolve_locale.LocaleProvider? _locale;
  bool _ready = false;
  Object? _error;
  bool _suiteRegistered = false;
  String? _suiteUsername;

  @override
  void initState() {
    super.initState();
    SuiteAccountBus.instance.addListener(_onSuiteAccountChanged);
    if (widget.child != null &&
        widget.evolveProvider != null &&
        widget.walletProvider != null &&
        widget.localeProvider != null) {
      _evolve = widget.evolveProvider;
      _wallet = widget.walletProvider;
      _fcg = widget.fcgProvider;
      _locale = widget.localeProvider;
      _ready = true;
      unawaited(_refreshSuiteRegisteredFlag());
      return;
    }
    _boot();
  }

  @override
  void dispose() {
    SuiteAccountBus.instance.removeListener(_onSuiteAccountChanged);
    super.dispose();
  }

  void _onSuiteAccountChanged() {
    unawaited(_reloadSharedLedgerSession());
  }

  Future<void> _refreshSuiteRegisteredFlag() async {
    final busUser = (SuiteAccountBus.instance.lastUsername ?? '').trim();
    var registered = busUser.isNotEmpty;
    String? user = busUser.isNotEmpty ? busUser : null;
    final store = widget.accountStore;
    if (store != null) {
      try {
        registered = await store.isRegistered() || registered;
        user ??= await store.username();
      } catch (_) {}
    }
    if (!mounted) return;
    setState(() {
      _suiteRegistered = registered;
      _suiteUsername = user;
    });
  }

  Future<void> _reloadSharedLedgerSession() async {
    await _refreshSuiteRegisteredFlag();
    final wallet = _wallet;
    if (wallet == null) return;
    try {
      await evolve_hub.PercLedgerHub.instance.reloadFromStore();
      // Re-init if session appeared on disk after first-run (shared ledger).
      if (!wallet.isReady) {
        await wallet.initialize();
      } else if (!wallet.hasAppAccess) {
        // Hub may have sessionUsername after first-run persist — re-read store.
        try {
          await evolve_hub.PercLedgerHub.instance.reloadFromStore();
        } catch (_) {}
      }
    } catch (_) {}
    if (mounted) setState(() {});
  }

  Future<void> _boot() async {
    try {
      evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = false;
      // Load suite-hosted perc_network.json (Helsinki; Render paused).
      evolve_net.PercNetworkConfig.resetForTest();
      await evolve_net.PercNetworkConfig.load();

      // Prefer full registry; fallback records still enable analysis shell.
      try {
        await OutcomeRegistry.ensureLoaded();
      } catch (_) {
        OutcomeRegistry.bundled();
      }

      final locale =
          widget.localeProvider ?? evolve_locale.LocaleProvider();
      final evolve = widget.evolveProvider ?? EvolveProvider();
      final wallet =
          widget.walletProvider ?? evolve_wallet.PercWalletProvider();
      final fcg = widget.fcgProvider ?? FcgVotingProvider();

      if (widget.localeProvider == null) {
        await locale.initialize();
      }
      if (widget.evolveProvider == null) {
        await evolve.initialize();
      }
      if (widget.fcgProvider == null) {
        await fcg.initialize();
      }
      // Shared Suite account session may already be on disk from first-run,
      // % tab, or the post-KEYGEN prompt — load wallet + hub before bootstrap
      // so Evolve can inherit login (no redundant create-account wall).
      try {
        await evolve_hub.PercLedgerHub.instance.reloadFromStore();
      } catch (_) {}
      if (widget.walletProvider == null) {
        try {
          await wallet.initialize();
        } catch (_) {}
      }
      await _refreshSuiteRegisteredFlag();

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

      if (!mounted) return;
      setState(() {
        _evolve = evolve;
        _wallet = wallet;
        _fcg = fcg;
        _locale = locale;
        _ready = true;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _ready = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return ColoredBox(
        color: suiteChromeBgOf(context),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'EVOLVE',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: suiteTextOf(context),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  '$_error',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: suiteTextMutedOf(context)),
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () {
                    setState(() {
                      _error = null;
                      _ready = false;
                    });
                    _boot();
                  },
                  child: Text('Retry'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (!_ready ||
        _evolve == null ||
        _wallet == null ||
        _locale == null ||
        _fcg == null) {
      return Center(
        child: CircularProgressIndicator(color: suitePrimaryOf(context)),
      );
    }

    final wallet = _wallet!;
    final inherits = suiteEvolveInheritsSuiteLogin(
      suiteAccountRegistered: _suiteRegistered ||
          (SuiteAccountBus.instance.lastUsername ?? '').trim().isNotEmpty,
      walletHasAppAccess: wallet.hasAppAccess,
    );
    final body = widget.child ??
        AppBootstrapScreen(
          walletProvider: wallet,
          showShellBottomBar: widget.showShellBottomBar,
          shellTabIndex: widget.shellTabIndex,
        );

    return MultiProvider(
      providers: [
        ChangeNotifierProvider<evolve_locale.LocaleProvider>.value(
          value: _locale!,
        ),
        ChangeNotifierProvider<EvolveProvider>.value(value: _evolve!),
        ChangeNotifierProvider<evolve_wallet.PercWalletProvider>.value(
          value: wallet,
        ),
        ChangeNotifierProvider<FcgVotingProvider>.value(value: _fcg!),
      ],
      child: Theme(
        data: AppTheme.dark(),
        child: Localizations(
          locale: _locale!.config.materialLocale,
          delegates: const [
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          child: Builder(
            builder: (context) {
              AppLocalizations.of(_locale!.config);
              // Banner when Suite first-run registered the same identity.
              if (inherits) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Material(
                      color: const Color(0xFF1A3A5C),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                        child: Text(
                          'Suite account'
                          '${(_suiteUsername ?? SuiteAccountBus.instance.lastUsername ?? '').trim().isEmpty ? '' : ' (${_suiteUsername ?? SuiteAccountBus.instance.lastUsername})'}'
                          ' — Evolve uses the same login from setup.',
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Color(0xFFFF9800),
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                    Expanded(child: body),
                  ],
                );
              }
              if (_suiteRegistered && !wallet.hasAppAccess) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Material(
                      color: const Color(0xFF3A2A10),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                        child: Text(
                          'Sign in with your Suite username'
                          '${(_suiteUsername ?? '').isEmpty ? '' : ' (${_suiteUsername!})'}'
                          ' — account already created in setup (not a new register).',
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Color(0xFFFF9800),
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                    Expanded(child: body),
                  ],
                );
              }
              return body;
            },
          ),
        ),
      ),
    );
  }
}
