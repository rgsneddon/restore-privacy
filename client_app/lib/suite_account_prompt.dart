/// Optional post-KEYGEN sheet: one register/login for % wallet + Evolve.
library;

import 'package:flutter/material.dart';

import 'suite_account.dart';
import 'suite_account_apply.dart';
import 'theme.dart';

/// Shows the optional Suite account sheet. Returns the outcome.
///
/// [applyCredentials] defaults to [applySuiteAccountToWalletAndEvolve] so both
/// Perccent and Evolve share one identity. Tests inject a stub.
Future<SuiteAccountPromptOutcome> showSuiteAccountPrompt(
  BuildContext context, {
  required SuiteAccountStore store,
  SuiteAccountAuthRunner? applyCredentials,
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
        applyCredentials: applyCredentials ??
            ({
              required String username,
              required String password,
              required bool register,
            }) =>
                applySuiteAccountToWalletAndEvolve(
                  username: username,
                  password: password,
                  register: register,
                ),
      );
    },
  );
  return result ?? SuiteAccountPromptOutcome.dismissed;
}

class _SuiteAccountPromptBody extends StatefulWidget {
  const _SuiteAccountPromptBody({
    required this.store,
    required this.applyCredentials,
  });

  final SuiteAccountStore store;
  final SuiteAccountAuthRunner applyCredentials;

  @override
  State<_SuiteAccountPromptBody> createState() =>
      _SuiteAccountPromptBodyState();
}

class _SuiteAccountPromptBodyState extends State<_SuiteAccountPromptBody> {
  final _user = TextEditingController();
  final _pass = TextEditingController();
  var _busy = false;
  var _status = '';
  var _registerMode = true;

  @override
  void dispose() {
    _user.dispose();
    _pass.dispose();
    super.dispose();
  }

  Future<void> _defer() async {
    if (_busy) return;
    await widget.store.markDeferred();
    if (!mounted) return;
    Navigator.of(context).pop(SuiteAccountPromptOutcome.deferred);
  }

  Future<void> _submit() async {
    if (_busy) return;
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
      await widget.applyCredentials(
        username: u,
        password: p,
        register: _registerMode,
      );
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
            kSuiteAccountPromptTitle,
            key: const Key('suite_account_prompt_title'),
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            kSuiteAccountPromptBody,
            key: Key('suite_account_prompt_body'),
            style: TextStyle(fontSize: 13),
          ),
          const SizedBox(height: 12),
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
          if (_status.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              _status,
              key: const Key('suite_account_status'),
              style: TextStyle(fontSize: 12),
            ),
          ],
          const SizedBox(height: 12),
          FilledButton(
            key: const Key('suite_account_submit'),
            onPressed: _busy ? null : _submit,
            style: FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
            child: Text(
              _busy
                  ? 'Please wait…'
                  : (_registerMode
                      ? kSuiteAccountRegisterLabel
                      : kSuiteAccountLoginLabel),
            ),
          ),
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
            key: const Key('suite_account_defer'),
            onPressed: _busy ? null : _defer,
            child: const Text(kSuiteAccountDeferLabel),
          ),
        ],
      ),
    );
  }
}
