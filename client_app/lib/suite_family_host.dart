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
import 'suite_session_rehydrate.dart';
import 'theme.dart';

/// Cap for live package I/O so Suite never spins forever without Retry.
const Duration kSuiteFamilyBootTimeout = Duration(seconds: 25);

/// Package mode after a successful family boot.
enum SuiteFamilyBootMode { none, evolve, walletOnly }

/// Ready provider scope produced by live boot or a test [SuiteFamilyBootFn].
class SuiteFamilyBootReady {
  const SuiteFamilyBootReady.evolve({
    required this.evolve,
    required this.evolveWallet,
    required this.fcg,
    required this.evolveLocale,
  })  : walletOnly = null,
        walletLocale = null,
        mode = SuiteFamilyBootMode.evolve;

  const SuiteFamilyBootReady.walletOnly({
    required this.walletOnly,
    required this.walletLocale,
  })  : evolve = null,
        evolveWallet = null,
        fcg = null,
        evolveLocale = null,
        mode = SuiteFamilyBootMode.walletOnly;

  const SuiteFamilyBootReady.empty()
      : evolve = null,
        evolveWallet = null,
        fcg = null,
        evolveLocale = null,
        walletOnly = null,
        walletLocale = null,
        mode = SuiteFamilyBootMode.none;

  final SuiteFamilyBootMode mode;
  final EvolveProvider? evolve;
  final evolve_wallet.PercWalletProvider? evolveWallet;
  final FcgVotingProvider? fcg;
  final evolve_locale.LocaleProvider? evolveLocale;
  final wallet_p.PercWalletProvider? walletOnly;
  final wallet_locale.LocaleProvider? walletLocale;

  bool get hasAppAccess {
    switch (mode) {
      case SuiteFamilyBootMode.evolve:
        return evolveWallet?.hasAppAccess ?? true;
      case SuiteFamilyBootMode.walletOnly:
      case SuiteFamilyBootMode.none:
        return true;
    }
  }
}

/// Optional test/prod override for family boot (skip live path_provider I/O).
typedef SuiteFamilyBootFn = Future<SuiteFamilyBootReady> Function();

/// Boots family providers once; exposes them via [MultiProvider] without Theme.
class SuiteFamilyHost extends StatefulWidget {
  const SuiteFamilyHost({
    super.key,
    required this.parts,
    required this.child,
    this.onHasAppAccessChanged,
    this.boot,
  });

  final SuitePartsState parts;
  final Widget child;

  /// Notified when Evolve wallet [hasAppAccess] changes (main-bar dest set).
  final ValueChanged<bool>? onHasAppAccessChanged;

  /// When set, replaces live `_bootEvolve` / `_bootWalletOnly` (widget tests).
  final SuiteFamilyBootFn? boot;

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
  int _bootGeneration = 0;
  final List<Timer> _bootTimers = <Timer>[];

  bool get hasAppAccess => _hasAppAccess;

  /// Exposed for tests that wait for production boot without soft-ifs.
  bool get isReady => _ready;

  Object? get bootError => _error;

  bool get useEvolvePackage =>
      suitePartShowsFullSurface(widget.parts, SuitePartId.evolve);

  bool get useWalletOnlyPackage =>
      !useEvolvePackage &&
      suitePartShowsFullSurface(widget.parts, SuitePartId.wallet);

  /// True under `flutter_test` (avoid live seed nodes; still use timeouts).
  static bool get underFlutterTest {
    try {
      return WidgetsBinding.instance.runtimeType
          .toString()
          .contains('TestWidgetsFlutterBinding');
    } catch (_) {
      return false;
    }
  }

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
        oldWidget.parts.walletInstalled != widget.parts.walletInstalled ||
        oldWidget.boot != widget.boot) {
      _boot();
    }
  }

  @override
  void dispose() {
    _bootGeneration++;
    _cancelBootTimers();
    SuiteAccountBus.instance.removeListener(_onSuiteAccountChanged);
    _evolveWallet?.removeListener(_onEvolveWalletChanged);
    super.dispose();
  }

  void _cancelBootTimers() {
    for (final t in _bootTimers) {
      t.cancel();
    }
    _bootTimers.clear();
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
    // Splash identity already done — restore session without a second login form.
    if (!next && SuiteAccountBus.instance.hasRegisteredSession) {
      unawaited(() async {
        final ok = await rehydrateSuiteFamilyWalletSession(wallet: w);
        if (!mounted) return;
        if (ok) _onEvolveWalletChanged();
      }());
    }
  }

  Future<void> _reloadLedgers() async {
    try {
      if (_evolveWallet != null) {
        if (!_evolveWallet!.isReady) {
          await _evolveWallet!.initialize();
        }
        await rehydrateSuiteFamilyWalletSession(wallet: _evolveWallet!);
        _onEvolveWalletChanged();
      }
      if (_walletOnly != null) {
        if (!_walletOnly!.isReady) {
          await _walletOnly!.initialize();
        }
        await rehydrateSuitePercWalletSession(wallet: _walletOnly!);
      }
    } catch (_) {}
    if (mounted) setState(() {});
  }

  /// After first-run / Suite register: ensure live wallet reflects disk session.
  ///
  /// Safe to call when the wallet is already [isReady] — still reloads the hub
  /// and restores session for the Suite-registered username when needed.
  Future<bool> rehydrateEvolveSessionFromStore() async {
    final wallet = _evolveWallet;
    if (wallet == null) return false;
    try {
      if (!wallet.isReady) {
        await wallet.initialize();
      }
      final ok = await rehydrateSuiteFamilyWalletSession(wallet: wallet);
      _onEvolveWalletChanged();
      return ok;
    } catch (_) {
      return false;
    }
  }

  /// Timeout that is cancelled on [dispose] (no pending-timer test flakes).
  Future<T> _step<T>(String name, Future<T> future) {
    final completer = Completer<T>();
    late final Timer timer;
    timer = Timer(kSuiteFamilyBootTimeout, () {
      if (!completer.isCompleted) {
        completer.completeError(
          TimeoutException(
            'Suite family boot timed out ($name)',
            kSuiteFamilyBootTimeout,
          ),
          StackTrace.current,
        );
      }
    });
    _bootTimers.add(timer);
    future.then((value) {
      if (!completer.isCompleted) completer.complete(value);
    }, onError: (Object e, StackTrace st) {
      if (!completer.isCompleted) completer.completeError(e, st);
    }).whenComplete(() {
      timer.cancel();
      _bootTimers.remove(timer);
    });
    return completer.future;
  }

  Future<void> _boot() async {
    final gen = ++_bootGeneration;
    _cancelBootTimers();
    setState(() {
      _ready = false;
      _error = null;
    });
    try {
      final SuiteFamilyBootReady ready;
      final inject = widget.boot;
      if (inject != null) {
        ready = await _step('inject_boot', inject());
      } else if (useEvolvePackage) {
        ready = await _bootEvolve();
      } else if (useWalletOnlyPackage) {
        ready = await _bootWalletOnly();
      } else {
        ready = const SuiteFamilyBootReady.empty();
      }
      if (!mounted || gen != _bootGeneration) return;
      _applyReady(ready);
    } catch (e) {
      if (!mounted || gen != _bootGeneration) return;
      setState(() {
        _error = e;
        _ready = false;
      });
    }
  }

  void _applyReady(SuiteFamilyBootReady ready) {
    _evolveWallet?.removeListener(_onEvolveWalletChanged);
    if (ready.evolveWallet != null) {
      ready.evolveWallet!.addListener(_onEvolveWalletChanged);
    }

    final access = ready.hasAppAccess;
    setState(() {
      _evolve = ready.evolve;
      _evolveWallet = ready.evolveWallet;
      _fcg = ready.fcg;
      _evolveLocale = ready.evolveLocale;
      _walletOnly = ready.walletOnly;
      _walletLocale = ready.walletLocale;
      _hasAppAccess = access;
      _ready = true;
      _error = null;
    });
    widget.onHasAppAccessChanged?.call(_hasAppAccess);

    // If boot still cold but Suite just registered, rehydrate before leaving
    // nav in a collapsed (no Analysis/Voting) state.
    if (!access &&
        ready.evolveWallet != null &&
        SuiteAccountBus.instance.hasRegisteredSession) {
      unawaited(() async {
        final ok = await rehydrateSuiteFamilyWalletSession(
          wallet: ready.evolveWallet!,
        );
        if (!mounted) return;
        if (ok) _onEvolveWalletChanged();
      }());
    }
  }

  Future<SuiteFamilyBootReady> _bootEvolve() async {
    // Never hang widget tests on live seed/path_provider forever.
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests =
        underFlutterTest;
    evolve_net.PercNetworkConfig.resetForTest();
    await _step('network_config', evolve_net.PercNetworkConfig.load());
    try {
      await _step('outcome_registry', OutcomeRegistry.ensureLoaded());
    } catch (_) {
      OutcomeRegistry.bundled();
    }

    final locale = evolve_locale.LocaleProvider();
    await _step('locale', locale.initialize());
    final evolve = EvolveProvider();
    final wallet = evolve_wallet.PercWalletProvider();
    final fcg = FcgVotingProvider();

    // Match prior AppBootstrap path: wallet session must initialize before shell.
    // Order: wallet.initialize loads store, then explicit reload so a Suite
    // first-run session written moments earlier is always applied to hasAppAccess.
    await _step('wallet_initialize', wallet.initialize());
    if (SuiteAccountBus.instance.hasRegisteredSession) {
      wallet.suiteSplashIdentityActive = true;
    }
    // Rehydrate Suite first-run session before publishing hasAppAccess to nav.
    await _step(
      'suite_session_rehydrate',
      rehydrateSuiteFamilyWalletSession(wallet: wallet),
    );
    await _step('evolve_initialize', evolve.initialize());
    await _step('fcg_initialize', fcg.initialize());
    // Final rehydrate after package inits (covers late first-run persist).
    await _step(
      'suite_session_rehydrate_post',
      rehydrateSuiteFamilyWalletSession(wallet: wallet),
    );

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

    return SuiteFamilyBootReady.evolve(
      evolve: evolve,
      evolveWallet: wallet,
      fcg: fcg,
      evolveLocale: locale,
    );
  }

  Future<SuiteFamilyBootReady> _bootWalletOnly() async {
    wallet_coord.PercNetworkCoordinator.disableLiveNodesForTests =
        underFlutterTest;
    wallet_net.PercNetworkConfig.resetForTest();
    await _step('wallet_network_config', wallet_net.PercNetworkConfig.load());
    final locale = wallet_locale.LocaleProvider();
    await _step('wallet_locale', locale.initialize());
    final wallet = wallet_p.PercWalletProvider();
    await _step('wallet_only_initialize', wallet.initialize());
    try {
      await _step(
        'wallet_ledger_reload',
        wallet_hub.PercLedgerHub.instance.reloadFromStore(),
      );
    } catch (_) {}
    // Splash Suite identity → no secondary % login form.
    await _step(
      'suite_perc_session_rehydrate',
      rehydrateSuitePercWalletSession(wallet: wallet),
    );

    return SuiteFamilyBootReady.walletOnly(
      walletOnly: wallet,
      walletLocale: locale,
    );
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

    // Ready marker for production-path widget tests (no soft-if on shells).
    if (_ready && _error == null) {
      body = KeyedSubtree(
        key: const Key('suite_family_host_ready'),
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
                key: const Key('suite_family_boot_retry'),
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
        child: CircularProgressIndicator(
          key: const Key('suite_family_boot_spinner'),
          color: suitePrimaryOf(context),
        ),
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
      // Suite first-run identity: no secondary login — banner only when access live.
      final suiteUser = (SuiteAccountBus.instance.lastUsername ?? '').trim();
      final suiteRegistered =
          SuiteAccountBus.instance.hasRegisteredSession || suiteUser.isNotEmpty;
      final inherits = suiteEvolveInheritsSuiteLogin(
        suiteAccountRegistered: suiteRegistered,
        walletHasAppAccess: access,
      );
      // Splash identity scope so WalletScreen skips secondary create/login forms.
      shell = SuiteSplashIdentityScope(
        suiteAccountRegistered: suiteRegistered,
        username: suiteUser.isEmpty ? null : suiteUser,
        child: shell,
      );
      if (inherits) {
        final label =
            'Suite account${suiteUser.isEmpty ? '' : ' ($suiteUser)'} — '
            'same identity from setup (no second sign-in).';
        shell = Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Material(
              color: const Color(0xFF1A3A5C),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                child: Text(
                  label,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Color(0xFFFF9800),
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
            Expanded(child: shell),
          ],
        );
      }
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
      final suiteUser = (SuiteAccountBus.instance.lastUsername ?? '').trim();
      final suiteRegistered =
          SuiteAccountBus.instance.hasRegisteredSession || suiteUser.isNotEmpty;
      shell = SuiteSplashIdentityScope(
        suiteAccountRegistered: suiteRegistered,
        username: suiteUser.isEmpty ? null : suiteUser,
        child: shell,
      );
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
