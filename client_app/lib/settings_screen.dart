import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'connection_log.dart';
import 'leak_test.dart';
import 'legal_links.dart';
import 'settings_store.dart';
import 'theme.dart';
import 'transparency_copy.dart';

const String _kConnLogPrefsKey = 'connection_log_lines';

/// SharedPreferences-backed local connection log (device only).
class PrefsConnectionLogBackend implements ConnectionLogBackend {
  PrefsConnectionLogBackend(this._prefs);

  final SharedPreferences _prefs;

  @override
  Future<List<String>> readLines() async {
    return List<String>.from(_prefs.getStringList(_kConnLogPrefsKey) ?? const []);
  }

  @override
  Future<void> writeLines(List<String> lines) async {
    await _prefs.setStringList(_kConnLogPrefsKey, lines);
  }
}

/// Settings surface: startup prefs, local connection log, leak test, DPI honesty.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.store,
    required this.initial,
    this.onChanged,
    this.connectionLog,
    this.residualCaptureActive = false,
    this.ipv6Protected = false,
  });

  final SettingsStore store;
  final ProductSettings initial;
  final ValueChanged<ProductSettings>? onChanged;

  /// Injectable log for tests; production creates a SharedPreferences backend.
  final ConnectionLog? connectionLog;

  /// Current tunnel residual posture (from home / native status when known).
  final bool residualCaptureActive;
  final bool ipv6Protected;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  static const _channel = MethodChannel('restore_privacy/vpn');
  late ProductSettings _settings;
  bool _busy = false;
  String? _note;
  String? _leakResult;
  ConnectionLog? _log;
  List<ConnectionLogEvent> _events = const [];

  @override
  void initState() {
    super.initState();
    _settings = widget.initial;
    _log = widget.connectionLog;
    WidgetsBinding.instance.addPostFrameCallback((_) => _ensureLog());
  }

  Future<void> _ensureLog() async {
    if (_log != null) {
      await _refreshLog();
      return;
    }
    try {
      final prefs = await SharedPreferences.getInstance();
      _log = ConnectionLog(PrefsConnectionLogBackend(prefs));
    } catch (_) {
      _log = ConnectionLog(MemoryConnectionLogBackend());
    }
    await _refreshLog();
  }

  Future<void> _refreshLog() async {
    final log = _log;
    if (log == null) return;
    final events = await log.readEvents(limit: 80);
    if (mounted) setState(() => _events = events);
  }

  Future<void> _setRunAtStartup(bool value) async {
    setState(() {
      _busy = true;
      _settings = _settings.copyWith(runAtStartup: value);
    });
    await widget.store.save(_settings);
    try {
      final res = await _channel.invokeMethod<dynamic>('setRunAtStartup', {
        'enabled': value,
      });
      if (res is Map && res['ok'] == false) {
        _note = res['message']?.toString() ?? 'Could not update startup registration';
      } else {
        _note = value
            ? 'Run at startup enabled (best-effort; OEM battery rules may apply).'
            : 'Run at startup disabled.';
      }
    } on MissingPluginException {
      _note = value
          ? 'Run at startup saved (native registration unavailable on this build).'
          : 'Run at startup disabled.';
    } catch (e) {
      _note = 'Saved preference; startup registration: $e';
    }
    widget.onChanged?.call(_settings);
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _setAutoconnect(bool value) async {
    setState(() {
      _busy = true;
      _settings = _settings.copyWith(autoconnectOnLaunch: value);
    });
    await widget.store.save(_settings);
    _note = value
        ? 'Autoconnect on launch enabled — next cold start will Connect.'
        : 'Autoconnect on launch disabled — Connect is manual.';
    widget.onChanged?.call(_settings);
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _openLegalDoc(LegalDocLink link) async {
    final uri = Uri.parse(link.url);
    try {
      final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!ok && mounted) {
        setState(() => _note = 'Could not open ${link.label}. Visit: ${link.url}');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _note = 'Could not open ${link.label}: $e');
      }
    }
  }

  Future<void> _exportLog() async {
    final log = _log;
    if (log == null) return;
    final body = await log.formatExport();
    await Clipboard.setData(ClipboardData(text: body));
    if (!mounted) return;
    setState(() {
      _note =
          'Connection log export copied to clipboard (local only — not uploaded). '
          'Paste into a file to save or share.';
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Export copied to clipboard')),
    );
  }

  Future<void> runLeakTest() async {
    // Prefer live residual flags from parent; fall back to native status.
    var residual = widget.residualCaptureActive;
    var ipv6 = widget.ipv6Protected;
    if (!residual) {
      try {
        final result = await _channel.invokeMethod<dynamic>('status');
        if (result is Map) {
          residual = result['connected'] == true &&
              (result['residualCapture'] == true ||
                  result['systemCapture'] == true ||
                  result['routesApplied'] == true);
          ipv6 = result['ipv6Protected'] == true;
        }
      } catch (_) {
        // Offline / no plugin — evaluate with residual=false.
      }
    }
    final result = runProductLeakTest(
      residualCaptureActive: residual,
      ipv6Protected: ipv6,
      // Offline-safe: no live public-IP probe in the default Settings path.
      publicIpProbeRan: false,
      dnsTunnelGatewayOnly: true,
    );
    await _log?.appendEvent(
      kLogKindLeakTest,
      '${result.verdict}: ${result.summary}',
    );
    if (!mounted) return;
    setState(() {
      _leakResult = result.formatUserMessage();
      _note = 'Leak test: ${result.verdict}';
    });
    await _refreshLog();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kChromeBg,
      appBar: AppBar(
        backgroundColor: kPanelBg,
        foregroundColor: kText,
        elevation: 0,
        title: const Text('Settings'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            decoration: BoxDecoration(
              color: kPanelBg,
              borderRadius: BorderRadius.circular(kCornerRadius),
              border: Border.all(color: kBorder),
            ),
            child: Column(
              children: [
                SwitchListTile(
                  title: const Text(
                    'Run at device startup',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: const Text(
                    'Start Privacy Restored when the device boots or you sign in',
                  ),
                  value: _settings.runAtStartup,
                  activeThumbColor: kWhite,
                  activeTrackColor: kPrimary,
                  onChanged: _busy ? null : _setRunAtStartup,
                ),
                const Divider(height: 1),
                SwitchListTile(
                  title: const Text(
                    'Autoconnect on launch',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: const Text(
                    'When the app opens, start Connect automatically',
                  ),
                  value: _settings.autoconnectOnLaunch,
                  activeThumbColor: kWhite,
                  activeTrackColor: kPrimary,
                  onChanged: _busy ? null : _setAutoconnect,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Both options default to off. Seamless power-up needs both on '
            '(startup launches the app; autoconnect starts the VPN). '
            'OS VPN permission / Administrator may still be required.',
            style: TextStyle(color: kTextMuted, fontSize: 12),
          ),
          const SizedBox(height: 20),
          Text(
            kConnectionLogTitle,
            style: TextStyle(
              color: kPrimaryDark,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kConnectionLogDisclaimer,
            style: TextStyle(color: kTextMuted, fontSize: 12),
          ),
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            constraints: const BoxConstraints(minHeight: 100, maxHeight: 160),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: kPanelBg,
              borderRadius: BorderRadius.circular(kCornerRadius),
              border: Border.all(color: kBorder),
            ),
            child: SingleChildScrollView(
              child: Text(
                _events.isEmpty
                    ? '(No connection events yet. Connect or run a leak test to record.)'
                    : _events.map((e) => e.formatLine()).join('\n'),
                style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              FilledButton(
                onPressed: _exportLog,
                style: FilledButton.styleFrom(backgroundColor: kPrimary),
                child: const Text(kExportLogButton),
              ),
              const SizedBox(width: 8),
              TextButton(
                onPressed: _refreshLog,
                child: const Text('Refresh'),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Text(
            kLeakTestTitle,
            style: TextStyle(
              color: kPrimaryDark,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kLeakTestDisclaimer,
            style: TextStyle(color: kTextMuted, fontSize: 12),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton(
              onPressed: runLeakTest,
              style: FilledButton.styleFrom(backgroundColor: kPrimary),
              child: const Text(kLeakTestButton),
            ),
          ),
          if (_leakResult != null) ...[
            const SizedBox(height: 8),
            Text(
              _leakResult!,
              style: const TextStyle(fontSize: 12, color: kText),
            ),
          ],
          const SizedBox(height: 20),
          Text(
            kDpiMitigationTitle,
            style: TextStyle(
              color: kPrimaryDark,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: kPanelBg,
              borderRadius: BorderRadius.circular(kCornerRadius),
              border: Border.all(color: kBorder),
            ),
            child: const Text(
              kDpiMitigationDisclaimer,
              style: TextStyle(fontSize: 12, color: kText),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Documents',
            style: TextStyle(
              color: kPrimaryDark,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            decoration: BoxDecoration(
              color: kPanelBg,
              borderRadius: BorderRadius.circular(kCornerRadius),
              border: Border.all(color: kBorder),
            ),
            child: Column(
              children: [
                for (var i = 0; i < kLegalDocLinks.length; i++) ...[
                  if (i > 0) const Divider(height: 1),
                  ListTile(
                    title: Text(
                      kLegalDocLinks[i].label,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        color: kPrimary,
                        decoration: TextDecoration.underline,
                      ),
                    ),
                    trailing: const Icon(Icons.open_in_new, size: 18, color: kPrimary),
                    onTap: () => _openLegalDoc(kLegalDocLinks[i]),
                  ),
                ],
              ],
            ),
          ),
          if (_note != null) ...[
            const SizedBox(height: 12),
            Text(_note!, style: const TextStyle(color: kPrimaryDark, fontSize: 12)),
          ],
        ],
      ),
    );
  }
}
