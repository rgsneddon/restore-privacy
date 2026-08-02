/// Full-screen first-run portal: account → seed → licence (before shell/VPN).
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'first_run_gate.dart';
import 'licence_gate.dart';
import 'prefs_backend.dart';
import 'settings_store.dart';
import 'suite_account.dart';
import 'suite_account_apply.dart';
import 'suite_account_seed.dart';
import 'suite_version.dart';
import 'theme.dart';

/// Finder keys for tests / automation.
const Key kFirstRunPortalKey = Key('first_run_portal');
const Key kFirstRunAccountContinueKey = Key('first_run_account_continue');
const Key kFirstRunSeedGenerateKey = Key('first_run_seed_generate');
const Key kFirstRunSeedConfirmKey = Key('first_run_seed_confirm');
const Key kFirstRunLicenceAcceptKey = Key('first_run_licence_accept');

/// Ordered first-run surface. Calls [onComplete] when account+seed+licence done.
class FirstRunPortal extends StatefulWidget {
  const FirstRunPortal({
    super.key,
    required this.onComplete,
    this.licenceGate,
    this.accountStore,
    this.firstRunStore,
    this.applyCredentials,
    this.seedOffer,
    this.initialState,
    this.generateSeedWords,
    this.attachAndPublishSeed,
    this.surfaces,
    this.suitePrefsBackend,
    this.licenceBackend,
  });

  final VoidCallback onComplete;
  final LicenceGate? licenceGate;
  final SuiteAccountStore? accountStore;
  final FirstRunStore? firstRunStore;
  final SuiteAccountAuthRunner? applyCredentials;
  final SuiteSeedOfferFn? seedOffer;

  /// When set, skips async load (widget tests).
  final FirstRunState? initialState;

  /// Override real BIP39 generate (tests inject [generateSuiteSeedWords] path).
  final Future<List<String>> Function()? generateSeedWords;

  /// Override attach+publish after write-down confirm.
  final Future<void> Function(List<String> words)? attachAndPublishSeed;

  /// Wallet surfaces for production attach (or injectable test stores).
  final SuiteAccountPackageSurfaces? surfaces;
  final SettingsBackend? suitePrefsBackend;
  final SettingsBackend? licenceBackend;

  @override
  State<FirstRunPortal> createState() => _FirstRunPortalState();
}

class _FirstRunPortalState extends State<FirstRunPortal> {
  FirstRunState? _state;
  LicenceGate? _gate;
  SuiteAccountStore? _accounts;
  FirstRunStore? _firstRun;
  Object? _error;
  var _busy = false;
  final _user = TextEditingController();
  final _pass = TextEditingController();
  /// Credentials retained for post-account seed attach (not uploaded).
  String _pendingUsername = '';
  String _pendingPassword = '';
  List<String>? _seedWords;
  var _status = '';

  @override
  void initState() {
    super.initState();
    if (widget.initialState != null) {
      _state = widget.initialState;
      _gate = widget.licenceGate;
      _accounts = widget.accountStore;
      _firstRun = widget.firstRunStore;
    } else if (widget.firstRunStore != null &&
        widget.licenceGate != null &&
        widget.accountStore != null) {
      // Injectable stores (tests / AppEntryRoot) — no SharedPreferences.
      _gate = widget.licenceGate;
      _accounts = widget.accountStore;
      _firstRun = widget.firstRunStore;
      _loadInjected();
    } else {
      _bootstrap();
    }
  }

  @override
  void dispose() {
    _user.dispose();
    _pass.dispose();
    super.dispose();
  }

  Future<void> _loadInjected() async {
    try {
      final first = _firstRun!;
      final st = await first.load();
      if (!mounted) return;
      setState(() {
        _state = st;
        _error = null;
      });
      if (firstRunComplete(st)) {
        widget.onComplete();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    }
  }

  Future<void> _bootstrap() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final backend = SharedPreferencesBackend(prefs);
      final gate = widget.licenceGate ??
          LicenceGate(
            PrefsLicenceBackend(
              (k) async => prefs.getBool(k),
              (k, v) async {
                await prefs.setBool(k, v);
              },
              (k) async => prefs.getString(k),
              (k, v) async {
                await prefs.setString(k, v);
              },
            ),
          );
      final accounts = widget.accountStore ?? SuiteAccountStore(backend);
      final first = widget.firstRunStore ??
          FirstRunStore(
            backend: backend,
            isAccountRegistered: accounts.isRegistered,
            hasAcceptedLicence: () => gate.hasAcceptedLicence(),
          );
      final st = await first.load();
      if (!mounted) return;
      setState(() {
        _gate = gate;
        _accounts = accounts;
        _firstRun = first;
        _state = st;
        _error = null;
      });
      if (firstRunComplete(st)) {
        widget.onComplete();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    }
  }

  Future<void> _reload() async {
    final first = _firstRun;
    if (first == null) return;
    final st = await first.load();
    if (!mounted) return;
    setState(() => _state = st);
    if (firstRunComplete(st)) {
      widget.onComplete();
    }
  }

  Future<void> _submitAccount({required bool register}) async {
    if (_busy) return;
    final u = _user.text.trim();
    final p = _pass.text;
    if (u.isEmpty || p.isEmpty) {
      setState(() => _status = 'Enter username and password.');
      return;
    }
    if (p.length < 8) {
      setState(() => _status = 'Password must be at least 8 characters.');
      return;
    }
    setState(() {
      _busy = true;
      _status = register ? 'Creating account…' : 'Signing in…';
    });
    final store = _accounts!;
    final SuiteAccountAuthRunner apply = widget.applyCredentials ??
        ({
          required String username,
          required String password,
          required bool register,
        }) =>
            applySuiteAccountToWalletAndEvolve(
              username: username,
              password: password,
              register: register,
              // Portal owns seed write-down after account; attach on confirm.
              skipSeedOffer: true,
              surfaces: widget.surfaces,
              suitePrefsBackend: widget.suitePrefsBackend,
              licenceBackend: widget.licenceBackend,
            );
    try {
      await apply(
        username: u,
        password: p,
        register: register,
      );
      await store.markRegistered(u);
      SuiteAccountBus.instance.notifyRegistered(u);
      if (!mounted) return;
      setState(() {
        _pendingUsername = u;
        _pendingPassword = p;
        _busy = false;
        _status = '';
      });
      await _reload();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _status = 'Account failed: $e';
      });
    }
  }

  Future<void> _generateSeed() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _status = 'Generating seed…';
    });
    try {
      final gen = widget.generateSeedWords ?? generateSuiteSeedWords;
      final words = await gen();
      if (isStubSuiteSeedWords(words)) {
        throw StateError('stub seed words rejected');
      }
      if (!mounted) return;
      setState(() {
        _seedWords = words;
        _busy = false;
        _status = 'Write these words offline, then continue.';
      });
    } catch (e) {
      // Fail closed — never substitute fake word01..word12.
      if (!mounted) return;
      setState(() {
        _seedWords = null;
        _busy = false;
        _status = 'Could not generate recovery seed: $e';
      });
    }
  }

  Future<void> _confirmSeed() async {
    if (_busy) return;
    if (_seedWords == null || _seedWords!.length != 12) {
      setState(() => _status = 'Generate the 12-word phrase first.');
      return;
    }
    if (isStubSuiteSeedWords(_seedWords!)) {
      setState(() => _status = 'Invalid seed — generate again.');
      return;
    }
    setState(() {
      _busy = true;
      _status = 'Saving recovery envelope…';
    });
    try {
      final attach = widget.attachAndPublishSeed;
      if (attach != null) {
        await attach(_seedWords!);
      } else {
        final u = _pendingUsername.trim().isNotEmpty
            ? _pendingUsername.trim()
            : _user.text.trim();
        final p = _pendingPassword.isNotEmpty ? _pendingPassword : _pass.text;
        if (u.isEmpty || p.isEmpty) {
          throw StateError('Account credentials required to save seed');
        }
        await attachAndPublishSuiteSeedForUser(
          words: _seedWords!,
          username: u,
          password: p,
          surfaces: widget.surfaces,
          suitePrefsBackend: widget.suitePrefsBackend,
          licenceBackend: widget.licenceBackend,
        );
      }
      await _firstRun?.markSeedDone();
      if (!mounted) return;
      setState(() {
        _busy = false;
        _status = '';
      });
      await _reload();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _status = 'Seed save failed: $e';
      });
    }
  }

  Future<void> _acceptLicence() async {
    if (_busy) return;
    final gate = _gate;
    if (gate == null) return;
    setState(() => _busy = true);
    await gate.acceptLicence();
    if (!mounted) return;
    setState(() => _busy = false);
    await _reload();
  }

  @override
  Widget build(BuildContext context) {
    final st = _state;
    if (st == null) {
      return Scaffold(
        key: kFirstRunPortalKey,
        backgroundColor: const Color(0xFF0A1628),
        body: Center(
          child: _error != null
              ? Text('Setup error: $_error',
                  style: const TextStyle(color: Colors.orange))
              : const CircularProgressIndicator(color: Colors.orange),
        ),
      );
    }
    final step = nextFirstRunStep(st);
    return Scaffold(
      key: kFirstRunPortalKey,
      backgroundColor: const Color(0xFF0A1628),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 28),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    kSuiteProductName,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    kSuiteDisplayVersion,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.75),
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Step ${_stepIndex(step)} of 3',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.6),
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 24),
                  if (step == FirstRunStep.account) _buildAccountStep(context),
                  if (step == FirstRunStep.seed) _buildSeedStep(context),
                  if (step == FirstRunStep.licence) _buildLicenceStep(context),
                  if (_status.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text(
                      _status,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Color(0xFFFF9800), fontSize: 13),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  int _stepIndex(FirstRunStep s) {
    switch (s) {
      case FirstRunStep.account:
        return 1;
      case FirstRunStep.seed:
        return 2;
      case FirstRunStep.licence:
        return 3;
      case FirstRunStep.complete:
        return 3;
    }
  }

  Widget _buildAccountStep(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          kFirstRunAccountTitle,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          kFirstRunAccountBody,
          style: TextStyle(color: Color(0xFFFF9800), fontSize: 14, height: 1.4),
        ),
        const SizedBox(height: 20),
        _field(_user, kSuiteAccountUsernameLabel),
        const SizedBox(height: 12),
        _field(_pass, kSuiteAccountPasswordLabel, obscure: true),
        const SizedBox(height: 16),
        FilledButton(
          key: kFirstRunAccountContinueKey,
          onPressed: _busy ? null : () => _submitAccount(register: true),
          child: Text(_busy ? 'Please wait…' : kSuiteAccountRegisterLabel),
        ),
        const SizedBox(height: 8),
        TextButton(
          onPressed: _busy ? null : () => _submitAccount(register: false),
          child: Text(
            kSuiteAccountLoginLabel,
            style: TextStyle(color: Colors.white.withValues(alpha: 0.85)),
          ),
        ),
      ],
    );
  }

  Widget _buildSeedStep(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          kFirstRunSeedTitle,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          kFirstRunSeedBody,
          style: TextStyle(color: Color(0xFFFF9800), fontSize: 14, height: 1.4),
        ),
        const SizedBox(height: 16),
        if (_seedWords != null) ...[
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFF132A4A),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.white24),
            ),
            child: Text(
              _seedWords!.join(' '),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 15,
                height: 1.5,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Write these words on paper. Do not screenshot cloud storage.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.7),
              fontSize: 12,
            ),
          ),
        ],
        const SizedBox(height: 16),
        if (_seedWords == null)
          FilledButton(
            key: kFirstRunSeedGenerateKey,
            onPressed: _busy ? null : _generateSeed,
            child: Text(_busy ? 'Please wait…' : kSuiteSeedGenerateLabel),
          )
        else
          FilledButton(
            key: kFirstRunSeedConfirmKey,
            onPressed: _busy ? null : _confirmSeed,
            child: Text(
              _busy ? 'Please wait…' : kFirstRunSeedConfirmLabel,
            ),
          ),
      ],
    );
  }

  Widget _buildLicenceStep(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          kFirstRunLicenceStepTitle,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 12),
        Text(
          kPaymentConnectDisclaimerPlain,
          style: const TextStyle(
            color: Color(0xFFFF9800),
            fontSize: 13,
            height: 1.4,
          ),
        ),
        const SizedBox(height: 12),
        Text(
          kFirstRunCompleteHint,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.8),
            fontSize: 13,
            height: 1.35,
          ),
        ),
        const SizedBox(height: 20),
        FilledButton(
          key: kFirstRunLicenceAcceptKey,
          onPressed: _busy ? null : _acceptLicence,
          child: Text(_busy ? 'Please wait…' : kLicenceAcceptButton),
        ),
      ],
    );
  }

  Widget _field(
    TextEditingController c,
    String label, {
    bool obscure = false,
  }) {
    return TextField(
      controller: c,
      obscureText: obscure,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: TextStyle(color: Colors.white.withValues(alpha: 0.7)),
        filled: true,
        fillColor: const Color(0xFF132A4A),
        enabledBorder: OutlineInputBorder(
          borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.35)),
        ),
        focusedBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFFFF9800)),
        ),
      ),
    );
  }
}
