import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'connection_log.dart';
import 'free_tier.dart';
import 'keygen_field.dart';
import 'leak_test.dart';
import 'legal_links.dart';
import 'licence_gate.dart';
import 'node_ping.dart';
import 'registration_copy.dart';
import 'rpt_config.dart';
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
    this.licenceGate,
    this.onLicenceChanged,
    this.residualCaptureActive = false,
    this.ipv6Protected = false,
    this.residualConnected = false,
  });

  final SettingsStore store;
  final ProductSettings initial;
  final ValueChanged<ProductSettings>? onChanged;

  /// Injectable log for tests; production creates a SharedPreferences backend.
  final ConnectionLog? connectionLog;
  final LicenceGate? licenceGate;
  final ValueChanged<bool>? onLicenceChanged;

  /// Current tunnel residual posture (from home / native status when known).
  final bool residualCaptureActive;
  final bool ipv6Protected;

  /// True when residual tunnel is active (for multihop reconnect messaging).
  final bool residualConnected;

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
  bool _licenceAccepted = false;
  bool _paymentOk = false;
  String _paymentStatus = kPaymentStatusUnknown;
  final TextEditingController _sessionCtrl = TextEditingController();
  String _entryPing = '…';
  String _exitPing = '…';
  bool _pingBusy = false;

  @override
  void initState() {
    super.initState();
    _settings = widget.initial;
    _log = widget.connectionLog;
    RptConfig.setRuntimeMultiHop(_settings.privacyMultihop);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _ensureLog();
      await _refreshLicenceAndPayment();
      await _refreshPings();
    });
  }

  @override
  void dispose() {
    _sessionCtrl.dispose();
    super.dispose();
  }

  Future<void> _refreshLicenceAndPayment() async {
    final gate = widget.licenceGate;
    final licOk = await gate?.hasAcceptedLicence() ?? false;
    final payOk = await gate?.paymentAllowsConnect() ?? false;
    final st = await gate?.paymentStatus() ?? kPaymentStatusUnknown;
    final kg = await gate?.paymentKeygen() ?? '';
    final sid = await gate?.paymentSessionId() ?? '';
    if (!mounted) return;
    setState(() {
      _licenceAccepted = licOk;
      _paymentOk = payOk;
      _paymentStatus = st;
      if (_sessionCtrl.text.isEmpty) {
        if (kg.isNotEmpty) {
          _sessionCtrl.text = kg;
        } else if (sid.isNotEmpty) {
          _sessionCtrl.text = sid;
        }
      }
    });
  }

  Future<void> _acceptLicence() async {
    final gate = widget.licenceGate;
    if (gate == null) {
      setState(() => _note = 'Licence store unavailable on this build.');
      return;
    }
    await gate.acceptLicence();
    widget.onLicenceChanged?.call(true);
    if (!mounted) return;
    setState(() {
      _licenceAccepted = true;
      _note =
          'Licence accepted (stored locally only). Enter your keygen below to unlock Connect.';
    });
  }

  Future<void> _verifyPayment() async {
    final gate = widget.licenceGate;
    if (gate == null) {
      setState(() => _note = 'Payment store unavailable on this build.');
      return;
    }
    final raw = _sessionCtrl.text.trim();
    setState(() {
      _busy = true;
      _note = 'Verifying payment entitlement…';
    });
    try {
      final String st;
      final upper = raw.toUpperCase();
      if (upper.startsWith('RPT-KEY') || upper.startsWith('RPTKEY')) {
        st = await gate.importKeygenAndVerify(raw);
      } else if (raw.startsWith('cs_') || raw.startsWith('cs_test')) {
        st = await gate.importSessionAndVerify(raw);
      } else if (raw.isNotEmpty) {
        st = await gate.importKeygenAndVerify(raw);
      } else {
        // Recheck existing keygen/session without forcing a paste
        final existingKg = await gate.paymentKeygen();
        final existing = await gate.paymentSessionId();
        if (existingKg.isEmpty && existing.isEmpty) {
          if (mounted) {
            setState(() {
              _note =
                  'Enter the keygen from your fulfilment email '
                  '($kKeygenUnlockInstruction), or complete pay on '
                  'restoreprivacy.online first.';
              _busy = false;
            });
          }
          return;
        }
        st = await gate.refreshEntitlementFromRemote();
      }
      final ok = await gate.paymentAllowsConnect();
      final kg2 = await gate.paymentKeygen();
      final sid2 = await gate.paymentSessionId();
      if (!mounted) return;
      setState(() {
        _paymentOk = ok;
        _paymentStatus = st;
        if (_sessionCtrl.text.trim().isEmpty) {
          if (kg2.isNotEmpty) {
            _sessionCtrl.text = kg2;
          } else if (sid2.isNotEmpty) {
            _sessionCtrl.text = sid2;
          }
        }
        _note = ok
            ? 'Payment active — Connect allowed (status=$st). Press Connect on the home screen.'
            : 'Payment not active (status=$st). Connect stays blocked until active subscription.';
      });
      widget.onLicenceChanged?.call(await gate.hasAcceptedLicence());
    } catch (e) {
      if (mounted) setState(() => _note = 'Could not verify payment: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
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

  Future<void> _setResidualStack({bool? ipv4, bool? ipv6}) async {
    setState(() {
      _busy = true;
      _settings = _settings.copyWith(
        residualIpv4: ipv4,
        residualIpv6: ipv6,
      );
    });
    await widget.store.save(_settings);
    try {
      await _channel.invokeMethod<dynamic>('setResidualStack', {
        'ipv4': _settings.residualIpv4,
        'ipv6': _settings.residualIpv6,
      });
    } on MissingPluginException {
      // Persist still valid; Connect rebuilds plan from prefs on next attach.
    } catch (_) {
      // Best-effort native hot-apply.
    }
    String note =
        'Residual stack saved: IPv4=${_settings.residualIpv4} '
        'IPv6=${_settings.residualIpv6}.';
    if (widget.residualConnected) {
      note +=
          ' Disconnect then Connect for residual routes / IPv6 leak policy '
          'to match these switches.';
    } else {
      note += ' Takes effect on next Connect.';
    }
    if (!_settings.residualIpv6) {
      note +=
          ' With IPv6 off, Connected will not claim IPv6 ISP path blocked.';
    }
    _note = note;
    widget.onChanged?.call(_settings);
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _setPrivacyScale({
    bool? trafficShape,
    bool? outerObfuscation,
    bool? multihop,
  }) async {
    // Free 3.3.3: privacy-scale is locked lean; ignore user amendments.
    if (freeTierSettingsLocked) {
      setState(() {
        _note =
            'Free edition (${kFreeTierVersion}): privacy options are fixed '
            '(Iceland single-hop, basic residual). Upgrade for full Settings.';
      });
      return;
    }
    final prevMh = _settings.privacyMultihop;
    setState(() {
      _busy = true;
      _settings = _settings.copyWith(
        privacyTrafficShape: trafficShape,
        privacyOuterObfuscation: outerObfuscation,
        privacyMultihop: multihop,
      );
    });
    await widget.store.save(_settings);
    RptConfig.setRuntimeMultiHop(_settings.privacyMultihop);
    // Push to native residual shell (app group / next reconnect).
    try {
      await _channel.invokeMethod<dynamic>('setPrivacyScale', {
        'trafficShape': _settings.privacyTrafficShape,
        'outerObfuscation': _settings.privacyOuterObfuscation,
        'multihop': _settings.privacyMultihop,
      });
    } on MissingPluginException {
      // Persist still valid; residual path uses Connect host from RptConfig.
    } catch (_) {
      // Best-effort native hot-apply.
    }
    final mhChanged = prevMh != _settings.privacyMultihop;
    String note =
        'Privacy scale saved: shape=${_settings.privacyTrafficShape} '
        'obfs=${_settings.privacyOuterObfuscation} '
        'multihop=${_settings.privacyMultihop}.';
    // Packet Tunnel loads App Group prefs at startTunnel only — not mid-session.
    if (widget.residualConnected) {
      note +=
          ' Disconnect then Connect for residual DATA to use the new shape/obfs'
          '${mhChanged ? ' (and multi-hop host)' : ''}.';
    } else if (mhChanged) {
      note +=
          ' Multi-hop takes effect on next Connect (entry vs exit residual host).';
    } else {
      note +=
          ' Shape/obfs take effect on next Connect (Packet Tunnel reads prefs at tunnel start).';
    }
    _note = note;
    widget.onChanged?.call(_settings);
    await _refreshPings();
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _refreshPings() async {
    if (_pingBusy) return;
    setState(() {
      _pingBusy = true;
      _entryPing = '…';
      if (_settings.privacyMultihop) {
        _exitPing = '…';
      } else {
        _exitPing = 'n/a (multi-hop off)';
      }
    });
    try {
      final r = await measureSettingsPings(multihopOn: _settings.privacyMultihop);
      if (!mounted) return;
      setState(() {
        _entryPing = 'Entry (${RptConfig.entryHost}): ${r.entry.display()}';
        if (r.exit != null) {
          _exitPing = 'Exit (${RptConfig.exitHost}): ${r.exit!.display()}';
        } else {
          _exitPing = 'Exit: n/a (multi-hop off)';
        }
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _entryPing = 'Entry: n/a ($e)';
          _exitPing = 'Exit: n/a';
        });
      }
    } finally {
      if (mounted) setState(() => _pingBusy = false);
    }
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
            'Residual dual-stack',
            style: TextStyle(
              color: kPrimaryDark,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'IPv4 routes residual traffic into the VPN tunnel. IPv6 blocks the '
            'ISP IPv6 path while residual is up so dual-stack leaks do not '
            'bypass the tunnel. Both default ON.',
            style: TextStyle(color: kTextMuted, fontSize: 12),
          ),
          const SizedBox(height: 10),
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
                    'IPv4 residual',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: const Text(
                    'Full-tunnel IPv4 capture (dual /1 residual routes)',
                  ),
                  value: _settings.residualIpv4,
                  activeThumbColor: kWhite,
                  activeTrackColor: kPrimary,
                  onChanged: _busy
                      ? null
                      : (v) => _setResidualStack(ipv4: v),
                ),
                const Divider(height: 1),
                SwitchListTile(
                  title: const Text(
                    'IPv6 residual',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: const Text(
                    'Block ISP IPv6 while residual is connected',
                  ),
                  value: _settings.residualIpv6,
                  activeThumbColor: kWhite,
                  activeTrackColor: kPrimary,
                  onChanged: _busy
                      ? null
                      : (v) => _setResidualStack(ipv6: v),
                ),
              ],
            ),
          ),
          if (!freeTierSettingsLocked) ...[
            const SizedBox(height: 20),
            Text(
              kPrivacyScaleTitle,
              style: TextStyle(
                color: kPrimaryDark,
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              kExplainerCoreVpn,
              style: TextStyle(color: kTextMuted, fontSize: 12),
            ),
            const SizedBox(height: 10),
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
                      'Traffic shaping',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: const Text(kExplainerTrafficShape),
                    value: _settings.privacyTrafficShape,
                    activeThumbColor: kWhite,
                    activeTrackColor: kPrimary,
                    onChanged: _busy
                        ? null
                        : (v) => _setPrivacyScale(trafficShape: v),
                  ),
                  const Divider(height: 1),
                  SwitchListTile(
                    title: const Text(
                      'Outer obfuscation',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: const Text(kExplainerOuterObfuscation),
                    value: _settings.privacyOuterObfuscation,
                    activeThumbColor: kWhite,
                    activeTrackColor: kPrimary,
                    onChanged: _busy
                        ? null
                        : (v) => _setPrivacyScale(outerObfuscation: v),
                  ),
                  const Divider(height: 1),
                  SwitchListTile(
                    title: const Text(
                      'Multi-hop residual',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: const Text(kExplainerMultihop),
                    value: _settings.privacyMultihop,
                    activeThumbColor: kWhite,
                    activeTrackColor: kPrimary,
                    onChanged:
                        _busy ? null : (v) => _setPrivacyScale(multihop: v),
                  ),
                ],
              ),
            ),
          ] else ...[
            const SizedBox(height: 20),
            Text(
              'Free edition ($kFreeTierVersion)',
              style: TextStyle(
                color: kPrimaryDark,
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Basic Iceland residual only — privacy options are fixed and '
              'cannot be changed. Single-hop entry; no multi-hop, traffic '
              'shaping, or outer obfuscation toggles.',
              style: TextStyle(color: kTextMuted, fontSize: 12),
            ),
          ],
          const SizedBox(height: 20),
          Text(
            kPingStatsTitle,
            style: TextStyle(
              color: kPrimaryDark,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kPingStatsDisclaimer,
            style: TextStyle(color: kTextMuted, fontSize: 12),
          ),
          const SizedBox(height: 8),
          Text(_entryPing, style: const TextStyle(fontSize: 13, color: kText)),
          const SizedBox(height: 4),
          Text(_exitPing, style: const TextStyle(fontSize: 13, color: kText)),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: OutlinedButton(
              onPressed: (_busy || _pingBusy) ? null : _refreshPings,
              child: Text(_pingBusy ? 'Probing…' : kRefreshPingsButton),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            kLicencePromptTitle,
            style: TextStyle(
              color: kPrimaryDark,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            _licenceAccepted
                ? 'Accepted on this device. Connect is allowed.'
                : 'Not accepted — Connect is blocked until you accept.',
            style: const TextStyle(fontSize: 12, color: kText),
          ),
          const SizedBox(height: 6),
          const Text(
            kShortLicenceSummary,
            style: TextStyle(fontSize: 12, color: kTextMuted),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton(
              onPressed: _acceptLicence,
              style: FilledButton.styleFrom(backgroundColor: kPrimary),
              child: const Text(kLicenceAcceptButton),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Payment entitlement / keygen',
            style: TextStyle(
              color: kPrimaryDark,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            kPaymentConnectDisclaimerPlain,
            style: TextStyle(fontSize: 12, color: kTextMuted),
          ),
          const SizedBox(height: 6),
          const Text(
            kKeygenUnlockInstruction,
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kText),
          ),
          const SizedBox(height: 6),
          Text(
            _paymentOk
                ? 'Payment status: $_paymentStatus — Connect allowed for payment.'
                : 'Payment status: $_paymentStatus — Connect blocked until keygen unlocks an active subscription.',
            style: const TextStyle(fontSize: 12, color: kText),
          ),
          const SizedBox(height: 8),
          KeygenEntryField(
            controller: _sessionCtrl,
            labelText: 'Keygen (RPT-KEY-…) from fulfilment email',
            isDense: true,
            style: const TextStyle(fontSize: 13),
            enabled: !_busy,
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton(
              onPressed: _busy ? null : _verifyPayment,
              style: FilledButton.styleFrom(backgroundColor: kPrimary),
              child: const Text('Verify keygen / unlock Connect'),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            kAnonRegistrationTitle,
            style: TextStyle(
              color: kPrimaryDark,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            kAnonRegistrationSummary,
            style: TextStyle(fontSize: 12, color: kTextMuted),
          ),
          const SizedBox(height: 6),
          const Text(
            kOsPrivilegeHonesty,
            style: TextStyle(fontSize: 12, color: kTextMuted),
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
          const SizedBox(height: 4),
          Text(
            kSupportLogFindHint,
            style: TextStyle(color: kTextMuted, fontSize: 11),
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
