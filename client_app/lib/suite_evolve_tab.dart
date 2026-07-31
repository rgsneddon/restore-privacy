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
import 'package:evolve/perc/services/perc_network_config.dart' as evolve_net;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
import 'package:evolve/providers/evolve_provider.dart';
import 'package:evolve/providers/locale_provider.dart' as evolve_locale;
import 'package:evolve/screens/app_bootstrap_screen.dart';
import 'package:evolve/theme/app_theme.dart';

import 'theme.dart';

/// **EVOLVE** tab — full Evolve Chronoflux app (bootstrap → analysis shell).
///
/// Embeds the shipped evolve package surfaces; not a stub.
class SuiteEvolveTab extends StatefulWidget {
  const SuiteEvolveTab({
    super.key,
    this.evolveProvider,
    this.walletProvider,
    this.fcgProvider,
    this.localeProvider,
    this.child,
  });

  final EvolveProvider? evolveProvider;
  final evolve_wallet.PercWalletProvider? walletProvider;
  final FcgVotingProvider? fcgProvider;
  final evolve_locale.LocaleProvider? localeProvider;

  /// When set, replaces bootstrap (tests inject a ready surface).
  final Widget? child;

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

  @override
  void initState() {
    super.initState();
    if (widget.child != null &&
        widget.evolveProvider != null &&
        widget.walletProvider != null &&
        widget.localeProvider != null) {
      _evolve = widget.evolveProvider;
      _wallet = widget.walletProvider;
      _fcg = widget.fcgProvider;
      _locale = widget.localeProvider;
      _ready = true;
      return;
    }
    _boot();
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
        color: kChromeBg,
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'EVOLVE',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: kText,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  '$_error',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: kTextMuted),
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
                  child: const Text('Retry'),
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
      return const Center(
        child: CircularProgressIndicator(color: kPrimary),
      );
    }

    final body = widget.child ??
        AppBootstrapScreen(walletProvider: _wallet!);

    return MultiProvider(
      providers: [
        ChangeNotifierProvider<evolve_locale.LocaleProvider>.value(
          value: _locale!,
        ),
        ChangeNotifierProvider<EvolveProvider>.value(value: _evolve!),
        ChangeNotifierProvider<evolve_wallet.PercWalletProvider>.value(
          value: _wallet!,
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
              return body;
            },
          ),
        ),
      ),
    );
  }
}
