import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'package:perccent_wallet/l10n/wallet_only_localizations.dart';
import 'package:perccent_wallet/perc/providers/perc_wallet_provider.dart';
import 'package:perccent_wallet/perc/services/perc_network_config.dart';
import 'package:perccent_wallet/perc/services/perc_network_coordinator.dart';
import 'package:perccent_wallet/providers/locale_provider.dart';
import 'package:perccent_wallet/perc/services/perc_ledger_hub.dart';
import 'package:perccent_wallet/screens/wallet_bootstrap_screen.dart';
import 'package:perccent_wallet/theme/app_theme.dart';
import 'package:perccent_wallet/wallet_core/models/locale_config_ui.dart';

import 'suite_account.dart';
import 'theme.dart';

/// **%** tab — full Perccent / MY PERC wallet (bootstrap → shell).
///
/// Embeds the shipped wallet package surfaces; not a stub. Suite account
/// registration is optional (shared with Evolve via [SuiteAccountBus]); VPN
/// never depends on it.
class SuiteWalletTab extends StatefulWidget {
  const SuiteWalletTab({
    super.key,
    this.walletProvider,
    this.localeProvider,
    this.child,
  });

  /// Injectable for tests; production creates [PercWalletProvider].
  final PercWalletProvider? walletProvider;

  /// Injectable for tests; production creates [LocaleProvider].
  final LocaleProvider? localeProvider;

  /// When set, replaces bootstrap (tests inject a ready surface).
  final Widget? child;

  @override
  State<SuiteWalletTab> createState() => _SuiteWalletTabState();
}

class _SuiteWalletTabState extends State<SuiteWalletTab> {
  PercWalletProvider? _wallet;
  LocaleProvider? _locale;
  bool _ready = false;
  Object? _error;

  @override
  void initState() {
    super.initState();
    SuiteAccountBus.instance.addListener(_onSuiteAccountChanged);
    if (widget.child != null &&
        widget.walletProvider != null &&
        widget.localeProvider != null) {
      _wallet = widget.walletProvider;
      _locale = widget.localeProvider;
      _ready = true;
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

  Future<void> _reloadSharedLedgerSession() async {
    if (_wallet == null) return;
    try {
      await PercLedgerHub.instance.reloadFromStore();
    } catch (_) {}
  }

  Future<void> _boot() async {
    try {
      PercNetworkCoordinator.disableLiveNodesForTests = false;
      // Load suite-hosted perc_network.json (Helsinki; Render paused).
      PercNetworkConfig.resetForTest();
      await PercNetworkConfig.load();

      final locale = widget.localeProvider ?? LocaleProvider();
      if (widget.localeProvider == null) {
        await locale.initialize();
      }

      final wallet = widget.walletProvider ?? PercWalletProvider();
      // Bootstrap screen initializes wallet; do not double-init here.
      // After Suite-wide register, ledger session is on disk — reload so this
      // tab does not force a second independent register wall.
      try {
        await PercLedgerHub.instance.reloadFromStore();
      } catch (_) {}

      if (!mounted) return;
      setState(() {
        _wallet = wallet;
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
      return _SuiteTabError(
        title: 'Wallet',
        message: '$_error',
        onRetry: () {
          setState(() {
            _error = null;
            _ready = false;
          });
          _boot();
        },
      );
    }

    if (!_ready || _wallet == null || _locale == null) {
      return Center(
        child: CircularProgressIndicator(color: suitePrimaryOf(context)),
      );
    }

    final body = widget.child ??
        WalletBootstrapScreen(walletProvider: _wallet!);

    return MultiProvider(
      providers: [
        ChangeNotifierProvider<LocaleProvider>.value(value: _locale!),
        ChangeNotifierProvider<PercWalletProvider>.value(value: _wallet!),
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
              // Ensure wallet string table is warm for nested screens.
              walletLocalizationsOf(_locale!.config);
              return body;
            },
          ),
        ),
      ),
    );
  }
}

class _SuiteTabError extends StatelessWidget {
  const _SuiteTabError({
    required this.title,
    required this.message,
    required this.onRetry,
  });

  final String title;
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: suiteChromeBgOf(context),
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                title,
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: suiteTextOf(context),
                ),
              ),
              const SizedBox(height: 12),
              Text(
                message,
                textAlign: TextAlign.center,
                style: TextStyle(color: suiteTextMutedOf(context)),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: onRetry,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
