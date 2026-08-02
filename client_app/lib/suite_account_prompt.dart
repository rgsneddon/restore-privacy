/// Optional post-KEYGEN sheet: one register/login for % wallet + Evolve.
///
/// First-register path offers recovery seed export; import restores identity.
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'prefs_backend.dart';
import 'settings_store.dart';
import 'suite_account.dart';
import 'suite_account_apply.dart';
import 'suite_account_seed.dart';
import 'theme.dart';

/// Shows the optional Suite account sheet. Returns the outcome.
///
/// [applyCredentials] defaults to [applySuiteAccountToWalletAndEvolve] so both
/// Perccent and Evolve share one identity. Tests inject a stub.
Future<SuiteAccountPromptOutcome> showSuiteAccountPrompt(
  BuildContext context, {
  required SuiteAccountStore store,
  SuiteAccountAuthRunner? applyCredentials,
  SuiteAccountPackageSurfaces? surfaces,
  SettingsBackend? suitePrefsBackend,
  SettingsBackend? licenceBackend,
  /// When false, seed export dialog is not shown (tests that only exercise auth).
  bool offerSeedOnRegister = true,
}) async {
  if (!context.mounted) return SuiteAccountPromptOutcome.dismissed;
  final result = await showModalBottomSheet<SuiteAccountPromptOutcome>(
    context: context,
    isScrollControlled: true,
    isDismissible: true,
    enableDrag: true,
    backgroundColor: suitePanelBgOf(context),
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (sheetContext) {
      return _SuiteAccountPromptBody(
        store: store,
        surfaces: surfaces,
        suitePrefsBackend: suitePrefsBackend,
        licenceBackend: licenceBackend,
        offerSeedOnRegister: offerSeedOnRegister,
        applyCredentials: applyCredentials,
      );
    },
  );
  return result ?? SuiteAccountPromptOutcome.dismissed;
}

class _SuiteAccountPromptBody extends StatefulWidget {
  const _SuiteAccountPromptBody({
    required this.store,
    required this.offerSeedOnRegister,
    this.applyCredentials,
    this.surfaces,
    this.suitePrefsBackend,
    this.licenceBackend,
  });

  final SuiteAccountStore store;
  final SuiteAccountAuthRunner? applyCredentials;
  final SuiteAccountPackageSurfaces? surfaces;
  final SettingsBackend? suitePrefsBackend;
  final SettingsBackend? licenceBackend;
  final bool offerSeedOnRegister;

  @override
  State<_SuiteAccountPromptBody> createState() =>
      _SuiteAccountPromptBodyState();
}

class _SuiteAccountPromptBodyState extends State<_SuiteAccountPromptBody> {
  final _user = TextEditingController();
  final _pass = TextEditingController();
  final _seed = TextEditingController();
  var _busy = false;
  var _status = '';
  var _registerMode = true;
  var _restoreMode = false;

  @override
  void dispose() {
    _user.dispose();
    _pass.dispose();
    _seed.dispose();
    super.dispose();
  }

  Future<SettingsBackend> _prefsBackend() async {
    if (widget.suitePrefsBackend != null) return widget.suitePrefsBackend!;
    try {
      // Widget tests must call SharedPreferences.setMockInitialValues first;
      // fall back to memory so the sheet never hangs forever.
      final p = await SharedPreferences.getInstance().timeout(
        const Duration(seconds: 2),
      );
      return SharedPreferencesBackend(p);
    } catch (_) {
      return MemorySettingsBackend();
    }
  }

  Future<void> _defer() async {
    if (_busy) return;
    await widget.store.markDeferred();
    if (!mounted) return;
    Navigator.of(context).pop(SuiteAccountPromptOutcome.deferred);
  }

  Future<SuiteSeedOfferResult> _offerSeed(
    Future<List<String>> Function() generate,
  ) async {
    if (!mounted) return const SuiteSeedOfferResult.skip();
    final result = await showDialog<SuiteSeedOfferResult>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => _SuiteSeedExportDialog(generate: generate),
    );
    return result ?? const SuiteSeedOfferResult.skip();
  }

  Future<void> _submit() async {
    if (_busy) return;
    if (_restoreMode) {
      await _restoreFromSeed();
      return;
    }
    final u = _user.text.trim();
    final p = _pass.text;
    if (u.isEmpty || p.isEmpty) {
      setState(() => _status = 'Enter a username and password.');
      return;
    }
    setState(() {
      _busy = true;
      _status = _registerMode ? 'Creating account…' : 'Signing in…';
    });
    try {
      final apply = widget.applyCredentials;
      if (apply != null) {
        // Injected apply (tests) — never block on SharedPreferences.
        await apply(username: u, password: p, register: _registerMode);
      } else {
        final prefs = await _prefsBackend();
        await applySuiteAccountToWalletAndEvolve(
          username: u,
          password: p,
          register: _registerMode,
          surfaces: widget.surfaces,
          suitePrefsBackend: prefs,
          licenceBackend: widget.licenceBackend,
          skipSeedOffer: !widget.offerSeedOnRegister || !_registerMode,
          seedOffer: widget.offerSeedOnRegister && _registerMode
              ? _offerSeed
              : null,
        );
      }
      await widget.store.markRegistered(u);
      if (!mounted) return;
      Navigator.of(context).pop(
        _registerMode
            ? SuiteAccountPromptOutcome.registered
            : SuiteAccountPromptOutcome.signedIn,
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _status = e.toString().replaceFirst('Bad state: ', '');
      });
    }
  }

  Future<void> _restoreFromSeed() async {
    setState(() {
      _busy = true;
      _status = 'Restoring from seed…';
    });
    try {
      final words = parseSuiteSeedPhrase(_seed.text);
      final prefs = await _prefsBackend();
      final username = await restoreSuiteIdentityFromSeed(
        words: words,
        accountStore: widget.store,
        surfaces: widget.surfaces,
        suitePrefsBackend: prefs,
        licenceBackend: widget.licenceBackend,
      );
      if (!mounted) return;
      setState(() => _status = 'Restored $username');
      Navigator.of(context).pop(SuiteAccountPromptOutcome.signedIn);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _status = e.toString().replaceFirst('Bad state: ', '');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        20,
        16,
        20,
        28 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            _restoreMode ? kSuiteSeedImportTitle : kSuiteAccountPromptTitle,
            key: const Key('suite_account_prompt_title'),
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            _restoreMode ? kSuiteSeedImportBody : kSuiteAccountPromptBody,
            key: const Key('suite_account_prompt_body'),
            style: const TextStyle(fontSize: 13),
          ),
          const SizedBox(height: 12),
          if (_restoreMode) ...[
            TextField(
              key: const Key('suite_account_seed_import'),
              controller: _seed,
              enabled: !_busy,
              maxLines: 3,
              autocorrect: false,
              decoration: const InputDecoration(
                labelText: '12-word recovery seed',
                border: OutlineInputBorder(),
              ),
            ),
          ] else ...[
            TextField(
              key: const Key('suite_account_username'),
              controller: _user,
              enabled: !_busy,
              autocorrect: false,
              decoration: const InputDecoration(
                labelText: kSuiteAccountUsernameLabel,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              key: const Key('suite_account_password'),
              controller: _pass,
              enabled: !_busy,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: kSuiteAccountPasswordLabel,
                border: OutlineInputBorder(),
              ),
            ),
          ],
          if (_status.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              _status,
              key: const Key('suite_account_status'),
              style: const TextStyle(fontSize: 12),
            ),
          ],
          const SizedBox(height: 12),
          FilledButton(
            key: const Key('suite_account_submit'),
            onPressed: _busy ? null : _submit,
            style: FilledButton.styleFrom(
              backgroundColor: suitePrimaryOf(context),
            ),
            child: Text(
              _busy
                  ? 'Please wait…'
                  : (_restoreMode
                      ? kSuiteSeedImportLabel
                      : (_registerMode
                          ? kSuiteAccountRegisterLabel
                          : kSuiteAccountLoginLabel)),
            ),
          ),
          if (!_restoreMode)
            TextButton(
              key: const Key('suite_account_toggle_mode'),
              onPressed: _busy
                  ? null
                  : () => setState(() => _registerMode = !_registerMode),
              child: Text(
                _registerMode
                    ? 'Already have an account? Sign in'
                    : 'Need an account? Create one',
              ),
            ),
          TextButton(
            key: const Key('suite_account_toggle_restore'),
            onPressed: _busy
                ? null
                : () => setState(() {
                      _restoreMode = !_restoreMode;
                      _status = '';
                    }),
            child: Text(
              _restoreMode
                  ? 'Back to username / password'
                  : kSuiteSeedImportLabel,
            ),
          ),
          TextButton(
            key: const Key('suite_account_defer'),
            onPressed: _busy ? null : _defer,
            child: const Text(kSuiteAccountDeferLabel),
          ),
        ],
      ),
    );
  }
}

/// First-register seed export opportunity (generate / write down / skip).
class _SuiteSeedExportDialog extends StatefulWidget {
  const _SuiteSeedExportDialog({required this.generate});

  final Future<List<String>> Function() generate;

  @override
  State<_SuiteSeedExportDialog> createState() => _SuiteSeedExportDialogState();
}

class _SuiteSeedExportDialogState extends State<_SuiteSeedExportDialog> {
  List<String>? _words;
  var _busy = false;

  Future<void> _generate() async {
    setState(() => _busy = true);
    try {
      final words = await widget.generate();
      if (!mounted) return;
      setState(() => _words = words);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(
        SnackBar(content: Text('$e')),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final words = _words;
    return AlertDialog(
      key: const Key('suite_seed_export_dialog'),
      title: const Text(kSuiteSeedExportTitle),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(kSuiteSeedExportBody, style: TextStyle(fontSize: 13)),
            const SizedBox(height: 12),
            if (words != null)
              Wrap(
                key: const Key('suite_seed_export_words'),
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (var i = 0; i < words.length; i++)
                    Chip(label: Text('${i + 1}. ${words[i]}')),
                ],
              ),
          ],
        ),
      ),
      actions: [
        if (words == null)
          FilledButton(
            key: const Key('suite_seed_export_generate'),
            onPressed: _busy ? null : _generate,
            child: Text(_busy ? '…' : kSuiteSeedGenerateLabel),
          ),
        if (words != null)
          FilledButton(
            key: const Key('suite_seed_export_confirm'),
            onPressed: () => Navigator.of(context).pop(
              SuiteSeedOfferResult.enable(words),
            ),
            child: const Text(kSuiteSeedConfirmLabel),
          ),
        TextButton(
          key: const Key('suite_seed_export_skip'),
          onPressed: _busy
              ? null
              : () => Navigator.of(context).pop(
                    const SuiteSeedOfferResult.skip(),
                  ),
          child: const Text(kSuiteSeedSkipLabel),
        ),
      ],
    );
  }
}
