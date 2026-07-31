/// Post-KEYGEN VPN main-surface panel: Suite update honesty + unpack button.
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'settings_store.dart';
import 'suite_update.dart';
import 'suite_version.dart';
import 'theme.dart';

/// Honesty explainer + optional unpack/relaunch control on the entitled VPN home.
class SuiteUpdateHonestyPanel extends StatefulWidget {
  const SuiteUpdateHonestyPanel({
    super.key,
    required this.settings,
    this.prefs,
    this.memoryPending,
    this.onAfterUnpack,
    this.compact = false,
    this.reloadToken = 0,
  });

  final ProductSettings settings;

  /// Injectable prefs (tests).
  final SharedPreferences? prefs;

  /// In-memory pending map (tests; skips SharedPreferences).
  final Map<String, String>? memoryPending;

  final VoidCallback? onAfterUnpack;

  /// Shorter body for nested Suite chrome with limited height.
  final bool compact;

  /// Bump when residual push stores a new pending package (forces reload).
  final int reloadToken;

  @override
  State<SuiteUpdateHonestyPanel> createState() =>
      _SuiteUpdateHonestyPanelState();
}

class _SuiteUpdateHonestyPanelState extends State<SuiteUpdateHonestyPanel> {
  PendingSuiteUpdate? _pending;
  bool _busy = false;
  String? _note;

  @override
  void initState() {
    super.initState();
    _reloadPending();
  }

  @override
  void didUpdateWidget(covariant SuiteUpdateHonestyPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.settings.checkBreadcrumbs !=
            widget.settings.checkBreadcrumbs ||
        oldWidget.memoryPending != widget.memoryPending ||
        oldWidget.reloadToken != widget.reloadToken) {
      _reloadPending();
    }
  }

  Future<void> _reloadPending() async {
    final p = await loadPendingSuiteUpdate(
      prefs: widget.prefs,
      memory: widget.memoryPending,
    );
    if (!mounted) return;
    setState(() => _pending = p);
  }

  Future<void> _onUnpack() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _note = null;
    });
    try {
      final prep = await prepareUnpackAndRelaunch(
        settings: widget.settings,
        pending: _pending,
        runningVersion: kSuiteVersion,
      );
      if (prep['ok'] != true) {
        if (mounted) {
          setState(() {
            _note = (prep['error'] ?? 'Cannot unpack').toString();
            _busy = false;
          });
        }
        return;
      }
      final handoff = Map<String, dynamic>.from(
        prep['handoff'] as Map? ?? const {},
      );
      final exec = await executeUnpackAndRelaunchHandoff(
        settings: widget.settings,
        handoff: handoff,
        openUri: (uri) async {
          try {
            return await launchUrl(uri, mode: LaunchMode.externalApplication);
          } catch (_) {
            return false;
          }
        },
      );
      if (mounted) {
        setState(() {
          _note = exec['ok'] == true
              ? 'Opened update package — finish install, then relaunch the Suite.'
              : (exec['error'] ?? 'Unpack handoff failed').toString();
          _busy = false;
        });
      }
      if (exec['ok'] == true) {
        widget.onAfterUnpack?.call();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _note = 'Unpack error: $e';
          _busy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final optIn = suiteSelfUpdateEnabled(widget.settings);
    final canUnpack = mayUnpackSuiteUpdate(
      settings: widget.settings,
      pending: _pending,
    );
    final pendingLabel = _pending?.isPresent == true
        ? 'Pending: Suite v${_pending!.version}'
        : 'No update package waiting right now.';

    return Container(
      key: const Key(kSuiteUpdateExplainerMarker),
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: kPanelBg,
        borderRadius: BorderRadius.circular(kCornerRadius),
        border: Border.all(color: kBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            kSuiteUpdateExplainerHeading,
            style: TextStyle(
              color: kPrimaryDark,
              fontWeight: FontWeight.w800,
              fontSize: widget.compact ? 13 : 14,
            ),
          ),
          SizedBox(height: widget.compact ? 4 : 8),
          Text(
            // Full honesty copy always present for product/tests; compact
            // trims visual height only via font/spacing — body stays complete.
            kSuiteUpdateExplainerBody,
            style: TextStyle(
              color: kTextMuted,
              fontSize: widget.compact ? 11 : 12,
              height: widget.compact ? 1.3 : 1.45,
            ),
            maxLines: widget.compact ? 6 : null,
            overflow: widget.compact ? TextOverflow.ellipsis : TextOverflow.visible,
          ),
          SizedBox(height: widget.compact ? 4 : 8),
          Text(
            optIn
                ? 'Self-update is on in VPN Settings. $pendingLabel'
                : 'Self-update is off in VPN Settings. $pendingLabel',
            style: TextStyle(
              color: optIn ? kPrimaryDark : kTextMuted,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
          SizedBox(height: widget.compact ? 6 : 10),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton.icon(
              key: const Key(kSuiteUpdateUnpackButtonMarker),
              onPressed: canUnpack && !_busy ? _onUnpack : null,
              icon: _busy
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.system_update_alt, size: 18),
              label: Text(kSuiteUpdateUnpackButtonLabel),
              style: FilledButton.styleFrom(
                backgroundColor: kPrimary,
                foregroundColor: kWhite,
                disabledBackgroundColor: kBorder,
                disabledForegroundColor: kTextMuted,
              ),
            ),
          ),
          if (_note != null) ...[
            const SizedBox(height: 8),
            Text(
              _note!,
              style: const TextStyle(color: kPrimaryDark, fontSize: 11),
            ),
          ],
        ],
      ),
    );
  }
}
