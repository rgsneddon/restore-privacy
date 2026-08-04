/// Full-screen first-run portal: licence → KEYGEN or continue trial (no account).
///
/// Product is residual VPN only. Username/password and seed steps are removed.
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'first_run_gate.dart';
import 'full_end_user_licence.dart';
import 'keygen_field.dart';
import 'legal_links.dart';
import 'licence_gate.dart';
import 'prefs_backend.dart';
import 'settings_store.dart';
import 'suite_version.dart';
import 'theme.dart';

/// Finder keys for tests / automation.
const Key kFirstRunPortalKey = Key('first_run_portal');
const Key kFirstRunLicenceAcceptKey = Key('first_run_licence_accept');
const Key kFirstRunLicenceScrollKey = Key('first_run_licence_scroll');
const Key kFirstRunLicenceLinkKey = Key('first_run_licence_link');
const Key kFirstRunKeygenContinueKey = Key('first_run_keygen_continue');
const Key kFirstRunContinueTrialKey = Key('first_run_continue_trial');
const Key kFirstRunGetKeygenKey = Key('first_run_get_keygen');

/// Public licence page opened from first-run (status-host LICENSE).
final Uri kFirstRunPublicLicenceUri = Uri.parse(
  kLegalDocLinks
      .firstWhere((l) => l.statusPath == '/LICENSE')
      .url,
);

/// Ordered first-run surface. Calls [onComplete] when licence + entitlement done.
class FirstRunPortal extends StatefulWidget {
  const FirstRunPortal({
    super.key,
    required this.onComplete,
    this.licenceGate,
    this.firstRunStore,
    this.initialState,
    this.suitePrefsBackend,
    this.licenceBackend,
    this.openLicenceUrl,
    this.requirePayment = true,
    // Legacy Suite injects (ignored — no account/seed path).
    this.accountStore,
    this.applyCredentials,
    this.seedOffer,
    this.generateSeedWords,
    this.attachAndPublishSeed,
    this.seedConfirmTimeout = const Duration(seconds: 60),
    this.surfaces,
  });

  final VoidCallback onComplete;
  final LicenceGate? licenceGate;
  final FirstRunStore? firstRunStore;

  /// When set, skips async load (widget tests).
  final FirstRunState? initialState;

  final SettingsBackend? suitePrefsBackend;
  final SettingsBackend? licenceBackend;

  /// Open public licence URL (tests inject).
  final Future<bool> Function(Uri url)? openLicenceUrl;

  final bool requirePayment;

  /// @deprecated ignored
  final Object? accountStore;
  /// @deprecated ignored
  final Object? applyCredentials;
  /// @deprecated ignored
  final Object? seedOffer;
  /// @deprecated ignored
  final Object? generateSeedWords;
  /// @deprecated ignored
  final Object? attachAndPublishSeed;
  /// @deprecated ignored
  final Duration seedConfirmTimeout;
  /// @deprecated ignored
  final Object? surfaces;

  @override
  State<FirstRunPortal> createState() => _FirstRunPortalState();
}

class _FirstRunPortalState extends State<FirstRunPortal> {
  FirstRunState? _state;
  LicenceGate? _gate;
  FirstRunStore? _firstRun;
  Object? _error;
  var _busy = false;
  var _status = '';
  var _licenceScrolledToBottom = false;
  var _entitled = false;
  final ScrollController _licenceScroll = ScrollController();
  final _keygenCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _licenceScroll.addListener(_onLicenceScroll);
    if (widget.initialState != null) {
      _state = widget.initialState;
      _gate = widget.licenceGate;
      _firstRun = widget.firstRunStore;
      _hydrateEntitlement();
    } else if (widget.firstRunStore != null && widget.licenceGate != null) {
      _gate = widget.licenceGate;
      _firstRun = widget.firstRunStore;
      _loadInjected();
    } else {
      _bootstrap();
    }
  }

  @override
  void dispose() {
    _licenceScroll.removeListener(_onLicenceScroll);
    _licenceScroll.dispose();
    _keygenCtrl.dispose();
    super.dispose();
  }

  Future<void> _hydrateEntitlement() async {
    final gate = _gate ?? widget.licenceGate;
    if (gate == null) return;
    final ok = await gate.paymentAllowsConnect(require: widget.requirePayment);
    if (!mounted) return;
    setState(() => _entitled = ok);
    final st = _state;
    if (st != null && st.licenceAccepted && ok) {
      await _firstRun?.markEntryUnlockDone();
      widget.onComplete();
    }
  }

  Future<void> _loadInjected() async {
    try {
      final first = _firstRun!;
      final st = await first.load();
      final gate = _gate!;
      final ok = await gate.paymentAllowsConnect(require: widget.requirePayment);
      if (!mounted) return;
      setState(() {
        _state = st;
        _entitled = ok;
        _error = null;
      });
      if (st.licenceAccepted && ok) {
        if (!st.entryUnlockDone) await first.markEntryUnlockDone();
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
      final first = widget.firstRunStore ??
          FirstRunStore(
            backend: backend,
            hasAcceptedLicence: () => gate.hasAcceptedLicence(),
          );
      final st = await first.load();
      final ok = await gate.paymentAllowsConnect(require: widget.requirePayment);
      if (!mounted) return;
      setState(() {
        _gate = gate;
        _firstRun = first;
        _state = st;
        _entitled = ok;
        _error = null;
      });
      if (st.licenceAccepted && ok) {
        if (!st.entryUnlockDone) await first.markEntryUnlockDone();
        widget.onComplete();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    }
  }

  Future<void> _reload() async {
    final first = _firstRun;
    final gate = _gate;
    if (first == null || gate == null) return;
    final st = await first.load();
    final ok = await gate.paymentAllowsConnect(require: widget.requirePayment);
    if (!mounted) return;
    setState(() {
      _state = st;
      _entitled = ok;
    });
    if (st.licenceAccepted && ok) {
      if (!st.entryUnlockDone) await first.markEntryUnlockDone();
      widget.onComplete();
    }
  }

  Future<void> _acceptLicence() async {
    if (_busy) return;
    if (!_licenceScrolledToBottom) {
      setState(() => _status = 'Scroll to the bottom of the licence to accept.');
      return;
    }
    final gate = _gate;
    if (gate == null) return;
    setState(() => _busy = true);
    await gate.acceptLicence();
    if (!mounted) return;
    setState(() {
      _busy = false;
      _status = '';
    });
    await _reload();
  }

  Future<void> _tryKeygenUnlock() async {
    if (_busy) return;
    final gate = _gate;
    if (gate == null) {
      setState(() => _status = 'Unlock is unavailable on this build.');
      return;
    }
    final raw = _keygenCtrl.text.trim();
    if (raw.isEmpty) {
      setState(() => _status = 'Paste the KEYGEN from your fulfilment email.');
      return;
    }
    setState(() {
      _busy = true;
      _status = 'Verifying KEYGEN…';
    });
    final st = await gate.importKeygenAndVerify(raw);
    final ok = await gate.paymentAllowsConnect(require: widget.requirePayment);
    if (!mounted) return;
    if (!ok) {
      setState(() {
        _busy = false;
        _status =
            'KEYGEN not active (status=$st). Check the code and subscription.';
      });
      return;
    }
    await _firstRun?.markEntryUnlockDone();
    if (!mounted) return;
    setState(() {
      _busy = false;
      _status = 'Unlocked. Opening residual VPN…';
      _entitled = true;
    });
    widget.onComplete();
  }

  Future<void> _continueOrStartTrial() async {
    if (_busy) return;
    final gate = _gate;
    if (gate == null) {
      setState(() => _status = 'Trial is unavailable on this build.');
      return;
    }
    setState(() {
      _busy = true;
      _status = 'Checking free 3-day trial…';
    });
    // Active trial: paymentAllowsConnect already true after claim/refresh.
    var ok = await gate.paymentAllowsConnect(require: widget.requirePayment);
    if (!ok) {
      final remote = await gate.claimDeviceTrial();
      ok = remote['connect_allowed'] == true || remote['ok'] == true;
      if (!ok) {
        final err = remote['error']?.toString() ?? 'trial_denied';
        if (!mounted) return;
        setState(() {
          _busy = false;
          _status = err == 'trial_exhausted'
              ? kContinueTrialExpiredHint
              : (err == kDeviceTrialStatusExpired
                  ? kContinueTrialExpiredHint
                  : 'Trial not available ($err). Enter a KEYGEN to continue.');
        });
        return;
      }
    }
    await _firstRun?.markEntryUnlockDone();
    if (!mounted) return;
    setState(() {
      _busy = false;
      _status = 'Trial active. Opening residual VPN…';
      _entitled = true;
    });
    widget.onComplete();
  }

  Future<void> _openShop() async {
    final uri = Uri.parse(shopPayUrl());
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {}
  }

  void _onLicenceScroll() {
    if (!_licenceScroll.hasClients) return;
    final pos = _licenceScroll.position;
    final atBottom = pos.maxScrollExtent <= 0 ||
        pos.pixels >= (pos.maxScrollExtent - 12);
    if (atBottom && !_licenceScrolledToBottom) {
      setState(() => _licenceScrolledToBottom = true);
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final st = _state;
      if (st != null && nextFirstRunStep(st) == FirstRunStep.licence) {
        _onLicenceScroll();
      }
    });
  }

  Future<void> _openPublicLicence() async {
    final opener = widget.openLicenceUrl;
    final uri = kFirstRunPublicLicenceUri;
    if (opener != null) {
      await opener(uri);
      return;
    }
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (e) {
      if (!mounted) return;
      setState(() => _status = 'Could not open licence page: $e');
    }
  }

  /// UI step: licence, or KEYGEN/trial when not entitled.
  FirstRunStep _uiStep(FirstRunState st) {
    if (!st.licenceAccepted) return FirstRunStep.licence;
    if (_entitled) return FirstRunStep.complete;
    return FirstRunStep.keygenOrTrial;
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
    final step = _uiStep(st);
    final header = <Widget>[
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
        _stepHeadline(step),
        key: Key('first_run_step_label_${_stepIndex(step)}'),
        textAlign: TextAlign.center,
        style: TextStyle(
          color: Colors.white.withValues(alpha: 0.85),
          fontSize: 13,
          fontWeight: FontWeight.w600,
        ),
      ),
      const SizedBox(height: 24),
    ];
    final status = _status.isNotEmpty
        ? <Widget>[
            const SizedBox(height: 12),
            Text(
              _status,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xFFFF9800), fontSize: 13),
            ),
          ]
        : const <Widget>[];

    if (step == FirstRunStep.licence) {
      return Scaffold(
        key: kFirstRunPortalKey,
        backgroundColor: const Color(0xFF0A1628),
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    ...header,
                    Expanded(child: _buildLicenceStep(context)),
                    ...status,
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }

    // KEYGEN / continue trial (first-use step 2 and return when trial expired).
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
                  ...header,
                  _buildKeygenOrTrialStep(context),
                  ...status,
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
      case FirstRunStep.licence:
        return 1;
      case FirstRunStep.keygenOrTrial:
        return 2;
      case FirstRunStep.complete:
        return 2;
    }
  }

  /// Visible first-use step chrome (Step 1 = licence, Step 2 = KEYGEN/trial).
  String _stepHeadline(FirstRunStep s) {
    switch (s) {
      case FirstRunStep.licence:
        return 'Step 1 of 2 — Accept the end-user licence';
      case FirstRunStep.keygenOrTrial:
        return 'Step 2 of 2 — KEYGEN or free trial';
      case FirstRunStep.complete:
        return 'Step 2 of 2 — Ready';
    }
  }

  Widget _buildKeygenOrTrialStep(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          kFirstRunKeygenStepTitle,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          kFirstRunKeygenStepBody,
          textAlign: TextAlign.justify,
          style: TextStyle(
            color: Color(0xFFFF9800),
            fontSize: 14,
            height: 1.45,
          ),
        ),
        const SizedBox(height: 20),
        Theme(
          data: Theme.of(context).copyWith(
            inputDecorationTheme: InputDecorationTheme(
              filled: true,
              fillColor: const Color(0xFF132A4A),
              labelStyle: TextStyle(
                color: Colors.white.withValues(alpha: 0.7),
                fontSize: 12,
              ),
              enabledBorder: OutlineInputBorder(
                borderSide: BorderSide(
                  color: Colors.white.withValues(alpha: 0.35),
                ),
              ),
              focusedBorder: const OutlineInputBorder(
                borderSide: BorderSide(color: Color(0xFFFF9800)),
              ),
            ),
          ),
          child: KeygenEntryField(
            controller: _keygenCtrl,
            labelText: 'KEYGEN (RPT-KEY-…) from fulfilment email',
            isDense: true,
            enabled: !_busy,
            style: const TextStyle(fontSize: 14, color: Colors.white),
          ),
        ),
        const SizedBox(height: 14),
        FilledButton(
          key: kFirstRunKeygenContinueKey,
          onPressed: _busy ? null : _tryKeygenUnlock,
          style: FilledButton.styleFrom(
            backgroundColor: suitePrimaryOf(context),
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 14),
          ),
          child: Text(_busy ? 'Please wait…' : kEntryAccessUnlockLabelFallback),
        ),
        const SizedBox(height: 12),
        OutlinedButton(
          key: kFirstRunContinueTrialKey,
          onPressed: _busy ? null : _continueOrStartTrial,
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.white,
            side: BorderSide(color: Colors.white.withValues(alpha: 0.55)),
            padding: const EdgeInsets.symmetric(vertical: 12),
          ),
          child: const Text(kContinueTrialButtonLabel),
        ),
        const SizedBox(height: 8),
        Text(
          kFirstRunCompleteHint,
          textAlign: TextAlign.justify,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.75),
            fontSize: 12,
            height: 1.4,
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton(
          key: kFirstRunGetKeygenKey,
          onPressed: _busy ? null : _openShop,
          style: OutlinedButton.styleFrom(
            foregroundColor: const Color(0xFFFF9800),
            side: const BorderSide(color: Color(0xFFFF9800)),
            padding: const EdgeInsets.symmetric(vertical: 12),
          ),
          child: const Text(kGetKeygenButtonLabel),
        ),
      ],
    );
  }

  Widget _buildLicenceStep(BuildContext context) {
    const licenceBody = '$kFullEndUserLicenceText\n\n'
        '---\n\n'
        '$kPaymentConnectDisclaimerPlain\n\n'
        '$kFirstRunCompleteHint';
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
          'Scroll through the full residual VPN licence below. Accept unlocks '
          'only after you reach the end.',
          textAlign: TextAlign.justify,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.75),
            fontSize: 12,
            height: 1.35,
          ),
        ),
        const SizedBox(height: 12),
        Expanded(
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: const Color(0xFF132A4A),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.white24),
            ),
            child: NotificationListener<ScrollNotification>(
              onNotification: (n) {
                if (n is ScrollUpdateNotification ||
                    n is ScrollEndNotification ||
                    n is ScrollMetricsNotification) {
                  _onLicenceScroll();
                }
                return false;
              },
              child: Scrollbar(
                controller: _licenceScroll,
                thumbVisibility: true,
                child: SingleChildScrollView(
                  key: kFirstRunLicenceScrollKey,
                  controller: _licenceScroll,
                  padding: const EdgeInsets.all(14),
                  child: const Text(
                    licenceBody,
                    textAlign: TextAlign.justify,
                    style: TextStyle(
                      color: Color(0xFFFF9800),
                      fontSize: 13,
                      height: 1.45,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 10),
        TextButton(
          key: kFirstRunLicenceLinkKey,
          onPressed: _busy ? null : _openPublicLicence,
          child: Text(
            kEndUserLicenceLabel,
            style: TextStyle(
              color: Colors.lightBlueAccent.withValues(alpha: 0.95),
              decoration: TextDecoration.underline,
            ),
          ),
        ),
        const SizedBox(height: 8),
        FilledButton(
          key: kFirstRunLicenceAcceptKey,
          onPressed:
              (_busy || !_licenceScrolledToBottom) ? null : _acceptLicence,
          child: Text(
            _busy
                ? 'Please wait…'
                : (_licenceScrolledToBottom
                    ? kLicenceAcceptButton
                    : 'Scroll to bottom to accept'),
          ),
        ),
      ],
    );
  }
}

/// Local label (avoids entry_access import cycle).
const String kEntryAccessUnlockLabelFallback = 'Unlock with KEYGEN';
