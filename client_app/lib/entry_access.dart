/// Full-screen licence unlock entry surface (app root gate).
///
/// Shown before Suite shell (VPN / % / EVOLVE) until the device has a valid
/// KEYGEN entitlement unlock. Styling: orange body text on dark navy blue.
/// Do not use the word "paywall" in any user-visible string here.
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'first_run_gate.dart';
import 'first_run_portal.dart';
import 'keygen_field.dart';
import 'licence_gate.dart';
import 'prefs_backend.dart';
import 'settings_store.dart';
import 'suite_account.dart';
import 'suite_version.dart';
import 'theme.dart';

/// Product dark navy for the entry surface (status-host chrome family).
const Color kEntryAccessBg = Color(0xFF0A1628);

/// Orange body text on [kEntryAccessBg].
const Color kEntryAccessOrange = Color(0xFFFF9800);

/// Finder key for the root entry surface.
const Key kEntryAccessScreenKey = Key('entry_access_screen');

/// Finder key for the unlock button on the entry surface.
const Key kEntryAccessUnlockButtonKey = Key('entry_access_unlock_button');

/// Guidance shown on the entry surface (orange). Required phrases preserved.
const String kEntryAccessGuidanceText =
    'If you just paid: enter the keygen from your fulfilment email '
    '(Settings → Payment entitlement / keygen, or the unlock dialog), '
    'then Connect again so this device is bound. Also check internet, '
    'Windows Firewall/UDP, or that the node is online. On Windows, run '
    'AllowFirewall.bat (or reinstall) if residual is blocked.';

const String kEntryAccessTitle = 'Unlock Restore Privacy Suite';
const String kEntryAccessSubtitle =
    'Enter your licence keygen to open the app on this device.';
const String kEntryAccessUnlockLabel = 'Unlock with keygen';
const String kEntryAccessAcceptLicenceLabel = 'Accept end-user licence';
const String kEntryAccessRenewLabel = 'Renew licence';
const String kEntryAccessShopHint =
    'Need a KEYGEN? Get one at restoreprivacy.online/pay (monthly licence).';

const String kEntryAccessTrialHint =
    'Free residual trial: 3 days (72 hours) on this device — no card. '
    'After it ends, a paid KEYGEN / active subscription is required to continue.';

/// Finder key for the Get keygen control (opens public /pay).
const Key kEntryAccessGetKeygenButtonKey = Key('entry_access_get_keygen_button');

/// Finder key for KEYGEN-free 3-day trial start.
const Key kEntryAccessStartTrialButtonKey =
    Key('entry_access_start_trial_button');

/// True when [copy] includes the shipped guidance phrases and omits forbidden wording.
bool entryAccessCopyIsValid(String copy) {
  final s = copy.trim();
  if (s.toLowerCase().contains('paywall')) return false;
  const must = [
    'If you just paid',
    'fulfilment email',
    'Payment entitlement / keygen',
    'unlock dialog',
    'Connect again',
    'Windows Firewall',
    'AllowFirewall.bat',
  ];
  for (final m in must) {
    if (!s.contains(m)) return false;
  }
  return true;
}

/// Whether the device may enter the main Suite shell.
///
/// Shell entry requires **first-run complete** (account → seed → licence).
/// Residual Connect still needs trial or KEYGEN ([LicenceGate.mayConnect]) and
/// is gated inside the shell / Connect path — not at this shell door.
Future<bool> isAppEntryUnlocked(
  LicenceGate? gate, {
  bool requirePayment = true,
  FirstRunStore? firstRunStore,
  SuiteAccountStore? accountStore,
  SettingsBackend? backend,
}) async {
  if (gate == null) return false;
  FirstRunStore store = firstRunStore ??
      FirstRunStore(
        backend: backend ??
            MemorySettingsBackend(), // tests must inject real backend
        isAccountRegistered: () async =>
            accountStore != null && await accountStore.isRegistered(),
        hasAcceptedLicence: () => gate.hasAcceptedLicence(),
      );
  // When no injectable backend was provided, load SharedPreferences.
  if (firstRunStore == null && backend == null) {
    try {
      final prefs = await SharedPreferences.getInstance();
      final b = SharedPreferencesBackend(prefs);
      final accounts = accountStore ?? SuiteAccountStore(b);
      store = FirstRunStore(
        backend: b,
        isAccountRegistered: accounts.isRegistered,
        hasAcceptedLicence: () => gate.hasAcceptedLicence(),
      );
    } catch (_) {
      return false;
    }
  }
  final done = await store.isComplete();
  return mayEnterSuiteShell(firstRunDone: done);
}

/// Root gate: first-run portal until complete, then [child] (Suite shell).
///
/// Residual Connect / KEYGEN / trial are enforced on Connect, not at shell entry.
class AppEntryRoot extends StatefulWidget {
  const AppEntryRoot({
    super.key,
    required this.child,
    this.licenceGate,
    this.requirePayment = true,
    this.initialUnlocked,
    this.firstRunStore,
    this.accountStore,
  });

  /// Main app shell (Suite tabs) after first-run.
  final Widget child;

  final LicenceGate? licenceGate;
  final bool requirePayment;

  /// When non-null, skips async load (tests) — treats as first-run complete.
  final bool? initialUnlocked;

  final FirstRunStore? firstRunStore;
  final SuiteAccountStore? accountStore;

  @override
  State<AppEntryRoot> createState() => AppEntryRootState();
}

class AppEntryRootState extends State<AppEntryRoot> {
  bool? _unlocked;
  Object? _loadError;
  LicenceGate? _gate;
  FirstRunStore? _firstRun;
  SuiteAccountStore? _accounts;

  bool get isUnlocked => _unlocked == true;

  LicenceGate? get effectiveGate => widget.licenceGate ?? _gate;

  @override
  void initState() {
    super.initState();
    if (widget.initialUnlocked != null) {
      _unlocked = widget.initialUnlocked;
      _gate = widget.licenceGate;
    } else {
      _bootstrap();
    }
  }

  Future<void> _bootstrap() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final backend = SharedPreferencesBackend(prefs);
      var gate = widget.licenceGate;
      if (gate == null) {
        gate = LicenceGate(
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
      }
      final accounts = widget.accountStore ?? SuiteAccountStore(backend);
      final first = widget.firstRunStore ??
          FirstRunStore(
            backend: backend,
            isAccountRegistered: accounts.isRegistered,
            hasAcceptedLicence: () => gate!.hasAcceptedLicence(),
          );
      final ok = await isAppEntryUnlocked(
        gate,
        requirePayment: widget.requirePayment,
        firstRunStore: first,
        accountStore: accounts,
        backend: backend,
      );
      if (!mounted) return;
      setState(() {
        _gate = gate;
        _accounts = accounts;
        _firstRun = first;
        _unlocked = ok;
        _loadError = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _unlocked = false;
        _loadError = e;
      });
    }
  }

  Future<void> _refreshUnlock() async {
    try {
      final ok = await isAppEntryUnlocked(
        effectiveGate,
        requirePayment: widget.requirePayment,
        firstRunStore: _firstRun ?? widget.firstRunStore,
        accountStore: _accounts ?? widget.accountStore,
      );
      if (!mounted) return;
      setState(() {
        _unlocked = ok;
        _loadError = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _unlocked = false;
        _loadError = e;
      });
    }
  }

  /// Call after first-run complete or keygen verify so the shell appears.
  Future<void> markUnlockedAndRefresh() async {
    await _refreshUnlock();
  }

  @override
  Widget build(BuildContext context) {
    if (_unlocked == null) {
      return const Scaffold(
        backgroundColor: kEntryAccessBg,
        body: Center(
          child: CircularProgressIndicator(color: kEntryAccessOrange),
        ),
      );
    }
    if (_unlocked == true) {
      return widget.child;
    }
    // First-run portal (account → seed → licence) before shell / permissions.
    return FirstRunPortal(
      licenceGate: effectiveGate,
      accountStore: _accounts ?? widget.accountStore,
      firstRunStore: _firstRun ?? widget.firstRunStore,
      onComplete: () {
        markUnlockedAndRefresh();
      },
    );
  }
}

/// Full-screen licence unlock entry (orange text on dark blue).
class EntryAccessScreen extends StatefulWidget {
  const EntryAccessScreen({
    super.key,
    this.licenceGate,
    this.requirePayment = true,
    this.onUnlocked,
    this.loadError,
  });

  final LicenceGate? licenceGate;
  final bool requirePayment;
  final Future<void> Function()? onUnlocked;
  final Object? loadError;

  @override
  State<EntryAccessScreen> createState() => _EntryAccessScreenState();
}

class _EntryAccessScreenState extends State<EntryAccessScreen> {
  final _keygenCtrl = TextEditingController();
  bool _busy = false;
  bool _licenceAccepted = false;
  bool _needsRenew = false;
  String _statusLine = '';

  @override
  void initState() {
    super.initState();
    _hydrate();
  }

  @override
  void dispose() {
    _keygenCtrl.dispose();
    super.dispose();
  }

  Future<void> _hydrate() async {
    final gate = widget.licenceGate;
    if (gate == null) return;
    final lic = await gate.hasAcceptedLicence();
    final renew = await gate.needsLicenceRenewal(
      requirePayment: widget.requirePayment,
    );
    if (!mounted) return;
    setState(() {
      _licenceAccepted = lic;
      _needsRenew = renew;
    });
  }

  Future<void> _acceptLicence() async {
    final gate = widget.licenceGate;
    if (gate == null) return;
    setState(() => _busy = true);
    await gate.acceptLicence();
    if (!mounted) return;
    setState(() {
      _licenceAccepted = true;
      _busy = false;
      _statusLine = 'Licence accepted on this device.';
    });
  }

  Future<void> _tryUnlock() async {
    if (_busy) return;
    final gate = widget.licenceGate;
    if (gate == null) {
      setState(() => _statusLine = 'Unlock is unavailable on this build.');
      return;
    }
    if (!_licenceAccepted) {
      setState(() => _statusLine = 'Accept the end-user licence first.');
      return;
    }
    if (_needsRenew) {
      setState(
        () => _statusLine =
            'Licence expired — renew first, then enter your new keygen.',
      );
      return;
    }
    final raw = _keygenCtrl.text.trim();
    if (raw.isEmpty) {
      setState(() => _statusLine = 'Paste the keygen from your fulfilment email.');
      return;
    }
    setState(() {
      _busy = true;
      _statusLine = 'Verifying keygen…';
    });
    final st = await gate.importKeygenAndVerify(raw);
    final ok = await gate.paymentAllowsConnect(require: widget.requirePayment);
    if (!mounted) return;
    if (!ok) {
      setState(() {
        _busy = false;
        _statusLine =
            'Keygen not active (status=$st). Check the code and subscription.';
      });
      return;
    }
    setState(() {
      _busy = false;
      _statusLine = 'Unlocked. Opening the app…';
    });
    await widget.onUnlocked?.call();
  }

  Future<void> _openRenew() async {
    final gate = widget.licenceGate;
    final url = gate != null
        ? await gate.renewPortalUrlForInstall()
        : kDefaultStripePaymentPageUrl;
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {}
  }

  Future<void> _openShop() async {
    // Always send users to the pay page for a KEYGEN (not storefront-only).
    final uri = Uri.parse(shopPayUrl());
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {}
  }

  Future<void> _startFreeTrial() async {
    if (_busy) return;
    final gate = widget.licenceGate;
    if (gate == null) {
      setState(() => _statusLine = 'Trial is unavailable on this build.');
      return;
    }
    if (!_licenceAccepted) {
      setState(() => _statusLine = 'Accept the end-user licence first.');
      return;
    }
    if (_needsRenew) {
      setState(
        () => _statusLine =
            'Licence expired — renew first, then enter your new keygen.',
      );
      return;
    }
    setState(() {
      _busy = true;
      _statusLine = 'Starting free 3-day trial…';
    });
    final remote = await gate.claimDeviceTrial();
    final ok = remote['connect_allowed'] == true || remote['ok'] == true;
    if (!mounted) return;
    if (!ok) {
      final err = remote['error']?.toString() ?? 'trial_denied';
      setState(() {
        _busy = false;
        _statusLine = err == 'trial_exhausted'
            ? kTrialExpiredUnlockMsg
            : 'Trial not available ($err). Get a KEYGEN at restoreprivacy.online/pay.';
      });
      return;
    }
    setState(() {
      _busy = false;
      _statusLine = 'Free trial active. Opening the app…';
    });
    await widget.onUnlocked?.call();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: kEntryAccessScreenKey,
      backgroundColor: kEntryAccessBg,
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
                    style: TextStyle(
                      color: kWhite,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.04,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    kSuiteDisplayVersion,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: kWhite.withValues(alpha: 0.75),
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 28),
                  Text(
                    kEntryAccessTitle,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: kWhite,
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    kEntryAccessSubtitle,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: kEntryAccessOrange,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 20),
                  // Required guidance — orange on dark blue.
                  Text(
                    kEntryAccessGuidanceText,
                    style: const TextStyle(
                      color: kEntryAccessOrange,
                      fontSize: 14,
                      height: 1.45,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 24),
                  if (!_licenceAccepted) ...[
                    FilledButton(
                      onPressed: _busy ? null : _acceptLicence,
                      style: FilledButton.styleFrom(
                        backgroundColor: suitePrimaryOf(context),
                        foregroundColor: kWhite,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      child: const Text(kEntryAccessAcceptLicenceLabel),
                    ),
                    const SizedBox(height: 16),
                  ],
                  if (_needsRenew) ...[
                    FilledButton(
                      onPressed: _busy ? null : _openRenew,
                      style: FilledButton.styleFrom(
                        backgroundColor: kEntryAccessOrange,
                        foregroundColor: kEntryAccessBg,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      child: const Text(kEntryAccessRenewLabel),
                    ),
                    const SizedBox(height: 16),
                  ],
                  Theme(
                    data: Theme.of(context).copyWith(
                      inputDecorationTheme: InputDecorationTheme(
                        filled: true,
                        fillColor: const Color(0xFF132A4A),
                        labelStyle: TextStyle(
                          color: kWhite.withValues(alpha: 0.7),
                          fontSize: 12,
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderSide: BorderSide(
                            color: kWhite.withValues(alpha: 0.35),
                          ),
                        ),
                        focusedBorder: const OutlineInputBorder(
                          borderSide: BorderSide(color: kEntryAccessOrange),
                        ),
                      ),
                      iconTheme: const IconThemeData(color: kEntryAccessOrange),
                    ),
                    child: KeygenEntryField(
                      controller: _keygenCtrl,
                      labelText: 'Keygen (RPT-KEY-…) from fulfilment email',
                      isDense: true,
                      enabled: !_busy && _licenceAccepted && !_needsRenew,
                      style: const TextStyle(fontSize: 14, color: kWhite),
                    ),
                  ),
                  const SizedBox(height: 14),
                  FilledButton(
                    key: kEntryAccessUnlockButtonKey,
                    onPressed: (_busy || !_licenceAccepted || _needsRenew)
                        ? null
                        : _tryUnlock,
                    style: FilledButton.styleFrom(
                      backgroundColor: suitePrimaryOf(context),
                      foregroundColor: kWhite,
                      disabledBackgroundColor: kPrimary.withValues(alpha: 0.4),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    child: Text(
                      _busy ? 'Please wait…' : kEntryAccessUnlockLabel,
                    ),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton(
                    key: kEntryAccessStartTrialButtonKey,
                    onPressed: (_busy || !_licenceAccepted || _needsRenew)
                        ? null
                        : _startFreeTrial,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: kWhite,
                      side: BorderSide(color: kWhite.withValues(alpha: 0.55)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    child: const Text(kStartFreeTrialButtonLabel),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    kEntryAccessTrialHint,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: kWhite.withValues(alpha: 0.75),
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton(
                    key: kEntryAccessGetKeygenButtonKey,
                    onPressed: _busy ? null : _openShop,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: kEntryAccessOrange,
                      side: const BorderSide(color: kEntryAccessOrange),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    child: const Text(kGetKeygenButtonLabel),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    kEntryAccessShopHint,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: kWhite.withValues(alpha: 0.8),
                      fontSize: 12,
                    ),
                  ),
                  if (_statusLine.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text(
                      _statusLine,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: kEntryAccessOrange,
                        fontSize: 13,
                      ),
                    ),
                  ],
                  if (widget.loadError != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      'Could not read local unlock state: ${widget.loadError}',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: kWhite.withValues(alpha: 0.6),
                        fontSize: 11,
                      ),
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
}
