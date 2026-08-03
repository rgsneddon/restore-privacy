import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'connection_log.dart';
import 'easter_egg_server.dart';
import 'free_tier.dart';
import 'keygen_field.dart';
import 'leak_posture.dart';
import 'leak_test.dart';
import 'legal_links.dart';
import 'licence_gate.dart';
import 'node_ping.dart';
import 'node_wipe_timer_panel.dart';
import 'registration_copy.dart';
import 'rpt_config.dart';
import 'breadcrumbs_check.dart';
import 'settings_store.dart';
import 'suite_parts.dart';
import 'suite_parts_store.dart';
import 'suite_update.dart';
import 'suite_update_panel.dart';
import 'suite_usage.dart';
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
    this.partsStore,
    this.initialParts,
    this.onPartsChanged,
    this.usageReporter,
    this.initialUsage,
    this.suiteUpdateReloadToken = 0,
    this.publicIpLookup,
    this.statusInvoker,
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

  /// Injectable public-IP lookup for leak test (tests / offline).
  final Future<String?> Function()? publicIpLookup;

  /// Injectable native `status` invoker (tests); default uses method channel.
  final Future<dynamic> Function()? statusInvoker;

  /// Optional Suite parts install store (remove/retain % · EVOLVE · rpAI).
  final SuitePartsStore? partsStore;
  final SuitePartsState? initialParts;
  final ValueChanged<SuitePartsState>? onPartsChanged;

  /// Disk + process usage probes (injectable for tests).
  final SuiteUsageReporter? usageReporter;

  /// Optional initial usage snapshot (tests / prefetched).
  final SuiteUsageSnapshot? initialUsage;

  /// Bump when residual push stores a pending package (reload honesty panel).
  final int suiteUpdateReloadToken;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  static const _channel = MethodChannel('restore_privacy/vpn');
  late ProductSettings _settings;
  bool _busy = false;
  String? _note;
  String? _leakResult;
  ResidualLeakPosture? _posture;
  ConnectionLog? _log;
  List<ConnectionLogEvent> _events = const [];
  bool _licenceAccepted = false;
  bool _paymentOk = false;
  String _paymentStatus = kPaymentStatusUnknown;
  final TextEditingController _sessionCtrl = TextEditingController();
  String _entryPing = '…';
  String _exitPing = '…';
  bool _pingBusy = false;
  SuitePartsState _parts = SuitePartsState.vpnAndRpai;
  SuitePartsStore? _partsStore;
  String _diskUsageText = '…';
  String _processUsageText = '…';
  bool _usageBusy = false;

  @override
  void initState() {
    super.initState();
    _settings = widget.initial;
    _log = widget.connectionLog;
    _parts = widget.initialParts ?? SuitePartsState.vpnAndRpai;
    _partsStore = widget.partsStore;
    final seed = widget.initialUsage;
    if (seed != null) {
      _diskUsageText = formatSuiteDiskUsage(seed.diskBytes);
      _processUsageText = formatSuiteProcessPercent(seed.processPercent);
    }
    RptConfig.setRuntimeMultiHop(_settings.privacyMultihop);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _ensureLog();
      await _refreshLicenceAndPayment();
      await _refreshPings();
      await _loadParts();
      await _refreshUsage();
      await _refreshPosture();
    });
  }

  Future<void> _loadParts() async {
    final store = _partsStore;
    if (store == null) return;
    final loaded = await store.load();
    if (!mounted) return;
    setState(() => _parts = loaded);
    // Keep shell nav in sync after cold start / reopen Settings.
    widget.onPartsChanged?.call(loaded);
  }

  Future<void> _setPartInstalled(
    SuitePartId id,
    bool installed, {
    String? confirmPhrase,
  }) async {
    if (!suitePartIsRemovable(id)) return;
    if (!installed) {
      final gate = evaluateSuitePartUninstallConfirmation(
        id: id,
        userInput: confirmPhrase,
      );
      if (!gate.allowed) {
        if (mounted) {
          setState(() {
            _note =
                'Uninstall aborted (${gate.reason}). Type the exact part name '
                '“${suitePartConfirmPhrase(id)}” to confirm.';
          });
        }
        return;
      }
    }
    setState(() => _busy = true);
    final store = _partsStore;
    SuitePartsState next;
    if (store != null) {
      next = await store.setInstalled(
        id,
        installed,
        confirmPhrase: confirmPhrase,
      );
    } else {
      next = applySuitePartInstall(
        _parts,
        id: id,
        installed: installed,
        confirmPhrase: confirmPhrase,
      );
    }
    if (!mounted) return;
    setState(() {
      _parts = next;
      _busy = false;
      _note = installed
          ? '${suitePartLabel(id)} installed. It appears on the main bar; licence and Suite account stay as before.'
          : '${suitePartLabel(id)} uninstalled — removed from the main bar. Install again anytime without a new KEYGEN.';
    });
    widget.onPartsChanged?.call(next);
  }

  /// rpOS-style typed gate: user must enter the exact part label.
  Future<void> _confirmUninstallPart(SuitePartId id) async {
    if (!suitePartIsRemovable(id)) return;
    final phrase = suitePartConfirmPhrase(id);
    final ctrl = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) {
        return AlertDialog(
          key: Key('suite_part_uninstall_dialog_${id.name}'),
          title: const Text(kSuitePartConfirmDialogTitle),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '$kSuitePartConfirmHintPrefix $phrase',
                key: Key('suite_part_confirm_hint_${id.name}'),
              ),
              const SizedBox(height: 8),
              const Text(
                kSuitePartConfirmAbortNote,
                style: TextStyle(fontSize: 12),
              ),
              const SizedBox(height: 12),
              TextField(
                key: Key('suite_part_confirm_field_${id.name}'),
                controller: ctrl,
                autofocus: true,
                decoration: InputDecoration(
                  labelText: 'Part name',
                  hintText: phrase,
                  border: const OutlineInputBorder(),
                ),
                onSubmitted: (_) {
                  final ok = suitePartUninstallConfirmationAccepted(
                    id: id,
                    userInput: ctrl.text,
                  );
                  Navigator.of(ctx).pop(ok);
                },
              ),
            ],
          ),
          actions: [
            TextButton(
              key: const Key('suite_part_confirm_cancel'),
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text(kSuitePartConfirmCancelLabel),
            ),
            FilledButton(
              key: Key('suite_part_confirm_proceed_${id.name}'),
              onPressed: () {
                final ok = suitePartUninstallConfirmationAccepted(
                  id: id,
                  userInput: ctrl.text,
                );
                Navigator.of(ctx).pop(ok);
              },
              child: const Text(kSuitePartConfirmProceedLabel),
            ),
          ],
        );
      },
    );
    ctrl.dispose();
    if (confirmed == true) {
      await _setPartInstalled(id, false, confirmPhrase: phrase);
    } else if (mounted && confirmed == false) {
      setState(() {
        _note =
            'Uninstall cancelled or confirmation did not match “$phrase”.';
      });
    }
  }

  Future<void> _refreshUsage() async {
    if (_usageBusy || !mounted) return;
    setState(() => _usageBusy = true);
    try {
      final reporter = widget.usageReporter ?? SuiteUsageReporter();
      final snap = await reporter.measure();
      if (!mounted) return;
      setState(() {
        _diskUsageText = formatSuiteDiskUsage(snap.diskBytes);
        _processUsageText = formatSuiteProcessPercent(snap.processPercent);
      });
    } catch (_) {
      if (mounted) {
        setState(() {
          _diskUsageText = 'n/a';
          _processUsageText = 'n/a';
        });
      }
    } finally {
      if (mounted) setState(() => _usageBusy = false);
    }
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
      _log = ConnectionLog(
        PrefsConnectionLogBackend(prefs),
        clientVersion: RptConfig.displayProductVersion,
        platformLabel: connectionLogPlatformLabel(),
      );
    } catch (_) {
      _log = ConnectionLog(
        MemoryConnectionLogBackend(),
        clientVersion: RptConfig.displayProductVersion,
        platformLabel: connectionLogPlatformLabel(),
      );
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

  Future<void> _setLightAppearance(bool light) async {
    final next = light ? 'light' : 'dark';
    setState(() {
      _busy = true;
      _settings = _settings.copyWith(appearance: next);
    });
    await widget.store.save(_settings);
    _note = light
        ? 'Light appearance on — Evolve light palette.'
        : 'Dark appearance on — Evolve dark chrome (default).';
    widget.onChanged?.call(_settings);
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _setCheckBreadcrumbs(bool value) async {
    setState(() {
      _busy = true;
      _settings = _settings.copyWith(checkBreadcrumbs: value);
    });
    await widget.store.save(_settings);
    if (value) {
      // Live path: enabled → fetch Helsinki breadcrumbs + apply pending update.
      try {
        final crumbsR = await onCheckBreadcrumbsSettingChanged(
          enabled: true,
          settings: _settings,
          productVersion: RptConfig.productVersion,
        );
        if (crumbsR['skipped'] == true) {
          _note =
              '$kSuiteUpdateSettingsTitle on — ${crumbsR['reason'] ?? 'ok'}.';
        } else if (crumbsR['ok'] == true && crumbsR['store'] != null) {
          final store = crumbsR['store'] as Map?;
          final ver = store?['pending_update_version'] ?? crumbsR['monopin'];
          _note =
              '$kSuiteUpdateSettingsTitle on — pending update v$ver '
              '(${store?['pending_update_url'] ?? ''}). '
              'Use “$kSuiteUpdateUnpackButtonLabel” below in this Settings section.';
        } else {
          _note =
              '$kSuiteUpdateSettingsTitle on — fetch/apply: '
              '${crumbsR['error'] ?? 'check failed'}';
        }
        // Best-effort native notify (platforms may no-op).
        try {
          await _channel.invokeMethod<dynamic>('checkBreadcrumbs', {
            'enabled': true,
          });
        } on MissingPluginException {
          // Dart path above is authoritative when native is absent.
        } catch (_) {}
      } catch (e) {
        _note = '$kSuiteUpdateSettingsTitle on — saved; check path error: $e';
      }
    } else {
      _note =
          '$kSuiteUpdateSettingsTitle off — no push-update receive or unpack.';
    }
    widget.onChanged?.call(_settings);
    if (mounted) setState(() => _busy = false);
  }

  /// Residual IPv6 only (IPv4 residual is product always-on, not adjustable).
  Future<void> _setResidualStack({bool? ipv6}) async {
    setState(() {
      _busy = true;
      _settings = _settings.copyWith(
        residualIpv4: kResidualIpv4AlwaysOn,
        residualIpv6: ipv6,
      );
    });
    await widget.store.save(_settings);
    try {
      await _channel.invokeMethod<dynamic>('setResidualStack', {
        'ipv4': kResidualIpv4AlwaysOn,
        'ipv6': _settings.residualIpv6,
      });
    } on MissingPluginException {
      // Persist still valid; Connect rebuilds plan from prefs on next attach.
    } catch (_) {
      // Best-effort native hot-apply.
    }
    String note =
        'Residual IPv6 saved: ${_settings.residualIpv6} '
        '(IPv4 residual is always on).';
    if (widget.residualConnected) {
      note +=
          ' Disconnect then Connect for residual routes / IPv6 leak policy '
          'to match this switch.';
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
    if (_pingBusy || !mounted) return;
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

  Widget _buildPartTile(SuitePartSpec part) {
    final installed = _parts.isInstalled(part.id);
    final keyBase = 'suite_part_${part.id.name}';
    if (!part.removable) {
      return ListTile(
        key: Key(keyBase),
        title: Text(
          part.label,
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Text(kSuitePartVpnRequiredLabel),
        trailing: Text(
          kSuitePartInstalledLabel,
          style: TextStyle(fontWeight: FontWeight.w700, color: suitePrimaryOf(context)),
        ),
      );
    }
    return ListTile(
      key: Key(keyBase),
      title: Text(
        part.label,
        style: const TextStyle(fontWeight: FontWeight.w600),
      ),
      subtitle: Text(
        installed ? kSuitePartInstalledLabel : kSuitePartRemovedLabel,
      ),
      trailing: installed
          ? TextButton(
              key: Key('suite_part_uninstall_btn_${part.id.name}'),
              onPressed: _busy ? null : () => _confirmUninstallPart(part.id),
              child: Text(kSuitePartUninstallLabel),
            )
          : TextButton(
              key: Key('suite_part_reinstall_settings_${part.id.name}'),
              onPressed: _busy
                  ? null
                  : () => _setPartInstalled(part.id, true),
              child: const Text(kSuitePartInstallLabel),
            ),
    );
  }

  Future<dynamic> _invokeStatus() async {
    final inv = widget.statusInvoker;
    if (inv != null) return inv();
    try {
      return await _channel.invokeMethod<dynamic>('status');
    } catch (_) {
      return null;
    }
  }

  Future<void> runLeakTest() async {
    // Live native status + product DNS plan + public egress probe (no invented PASS).
    dynamic statusMap;
    try {
      statusMap = await _invokeStatus();
    } catch (_) {
      statusMap = null;
    }
    final inputs = await collectProductLeakTestInputs(
      nativeStatus: statusMap,
      parentResidualCapture: widget.residualCaptureActive,
      parentIpv6Protected: widget.ipv6Protected,
      runPublicIpProbe: true,
      publicIpLookup: widget.publicIpLookup,
    );
    final result = runProductLeakTest(
      residualCaptureActive: inputs.residualCaptureActive,
      ipv6Protected: inputs.ipv6Protected,
      dnsTunnelGatewayOnly: inputs.dnsTunnelGatewayOnly,
      publicDnsViolations: inputs.publicDnsViolations,
      publicIpProbeRan: inputs.publicIpProbeRan,
      publicIpMatchesExpectedNode: inputs.publicIpMatchesExpectedNode,
    );
    await widget.store.saveLastLeakTest(verdict: result.verdict);
    await _log?.appendEvent(
      kLogKindLeakTest,
      '${result.verdict}: ${result.summary}',
    );
    if (!mounted) return;
    await _refreshPosture(
      residual: inputs.residualCaptureActive,
      ipv6: inputs.ipv6Protected,
      dnsTunnelOnly: inputs.dnsTunnelGatewayOnly,
      forceVerdict: result.verdict,
    );
    setState(() {
      _leakResult = result.formatUserMessage();
      _note = 'Leak test: ${result.verdict}';
    });
    await _refreshLog();
  }

  Future<void> _refreshPosture({
    bool? residual,
    bool? ipv6,
    bool? dnsTunnelOnly,
    String? forceVerdict,
  }) async {
    final last = await widget.store.loadLastLeakTest();
    var cap = residual ?? widget.residualCaptureActive;
    var v6 = ipv6 ?? widget.ipv6Protected;
    bool dnsOnly;
    if (dnsTunnelOnly != null) {
      dnsOnly = dnsTunnelOnly;
    } else {
      // Live status — never hardcode tunnel DNS true.
      dynamic statusMap;
      try {
        statusMap = await _invokeStatus();
      } catch (_) {
        statusMap = null;
      }
      final flags = parseNativeResidualStatus(statusMap);
      if (residual == null && flags.residualCaptureActive) {
        cap = flags.residualCaptureActive;
      }
      if (ipv6 == null && statusMap != null) {
        v6 = flags.ipv6Protected;
      }
      dnsOnly = resolveDnsTunnelOnly(
        flags: NativeResidualStatusFlags(
          connected: flags.connected || cap,
          residualCaptureActive: cap,
          ipv6Protected: v6,
          fullTunnelActive: flags.fullTunnelActive || cap,
          dnsTunnelOnly: flags.dnsTunnelOnly,
          dnsServers: flags.dnsServers,
          vpnIp: flags.vpnIp,
          rawMessage: flags.rawMessage,
        ),
      );
    }
    final posture = evaluateResidualLeakPosture(
      residualCaptureActive: cap,
      ipv6Protected: v6,
      dnsTunnelOnly: dnsOnly,
      lastLeakVerdict: forceVerdict ?? last.verdict,
      lastLeakAtMs: last.atMs,
    );
    if (!mounted) return;
    setState(() => _posture = posture);
  }

  Future<void> _setKillSwitch(bool on) async {
    final next = _settings.copyWith(killSwitchOptIn: on);
    setState(() {
      _settings = next;
      _note = on
          ? 'Kill-switch opt-in ON (fail-closed if residual drops).'
          : 'Kill-switch OFF (product default — scoped allows only).';
    });
    await widget.store.save(next);
    widget.onChanged?.call(next);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: suiteChromeBgOf(context),
      appBar: AppBar(
        backgroundColor: suitePanelBgOf(context),
        foregroundColor: suiteTextOf(context),
        elevation: 0,
        title: Text('Settings'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Material(
            color: suitePanelBgOf(context),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(kCornerRadius),
              side: BorderSide(color: suiteBorderOf(context)),
            ),
            clipBehavior: Clip.antiAlias,
            child: Column(
              children: [
                SwitchListTile(
                  title: Text(
                    'Run at device startup',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: Text(
                    'Start Privacy Restored when the device boots or you sign in',
                  ),
                  value: _settings.runAtStartup,
                  activeThumbColor: suiteOnPrimaryOf(context),
                  activeTrackColor: suitePrimaryOf(context),
                  onChanged: _busy ? null : _setRunAtStartup,
                ),
                const Divider(height: 1),
                SwitchListTile(
                  title: Text(
                    'Autoconnect on launch',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: Text(
                    'When the app opens, start Connect automatically',
                  ),
                  value: _settings.autoconnectOnLaunch,
                  activeThumbColor: suiteOnPrimaryOf(context),
                  activeTrackColor: suitePrimaryOf(context),
                  onChanged: _busy ? null : _setAutoconnect,
                ),
                const Divider(height: 1),
                SwitchListTile(
                  key: const Key(kSuiteUpdateSettingsSwitchMarker),
                  title: Text(
                    kSuiteUpdateSettingsTitle,
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: Text(kSuiteUpdateSettingsSubtitle),
                  value: _settings.checkBreadcrumbs,
                  activeThumbColor: suiteOnPrimaryOf(context),
                  activeTrackColor: suitePrimaryOf(context),
                  onChanged: _busy ? null : _setCheckBreadcrumbs,
                ),
                // Honesty explainer + unpack/relaunch under self-update opt-in.
                Padding(
                  padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
                  child: SuiteUpdateHonestyPanel(
                    settings: _settings,
                    reloadToken: widget.suiteUpdateReloadToken,
                  ),
                ),
                const Divider(height: 1),
                SwitchListTile(
                  key: const Key('suite_appearance_light_switch'),
                  title: Text(
                    'Light appearance',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: Text(
                    'Off = Evolve dark chrome (default). On = light Evolve palette. '
                    'Only controlled here in Settings.',
                  ),
                  value: _settings.isLightAppearance,
                  activeThumbColor: suiteOnPrimaryOf(context),
                  activeTrackColor: suitePrimaryOf(context),
                  onChanged: _busy ? null : _setLightAppearance,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Startup and autoconnect default off. Seamless power-up needs both on '
            '(startup launches the app; autoconnect starts the VPN). '
            'OS VPN permission / Administrator may still be required. '
            '$kSuiteUpdateSettingsTitle defaults off — no push-update receive or '
            'unpack until you allow it. Unpacking still requires your click on '
            '$kSuiteUpdateUnpackButtonLabel in this Settings self-update section. '
            'Appearance (dark/light) is only changed in this Settings panel.',
            style: TextStyle(color: suiteTextMutedOf(context), fontSize: 12),
          ),
          const SizedBox(height: 20),
          Text(
            kSuitePartsSettingsTitle,
            key: const Key('suite_parts_section_title'),
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kSuitePartsSettingsSubtitle,
            style: TextStyle(color: suiteTextMutedOf(context), fontSize: 12),
          ),
          const SizedBox(height: 10),
          Material(
            key: const Key('suite_parts_panel'),
            color: suitePanelBgOf(context),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(kCornerRadius),
              side: BorderSide(color: suiteBorderOf(context)),
            ),
            clipBehavior: Clip.antiAlias,
            child: Column(
              children: [
                for (var i = 0; i < kSuitePartCatalog.length; i++) ...[
                  if (i > 0) const Divider(height: 1),
                  _buildPartTile(kSuitePartCatalog[i]),
                ],
              ],
            ),
          ),
          const SizedBox(height: 20),
          Text(
            kSuiteUsageNotifierTitle,
            key: const Key('suite_usage_section_title'),
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Material(
            key: const Key('suite_usage_panel'),
            color: suitePanelBgOf(context),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(kCornerRadius),
              side: BorderSide(color: suiteBorderOf(context)),
            ),
            clipBehavior: Clip.antiAlias,
            child: Column(
              children: [
                ListTile(
                  key: const Key(kSuiteUsageDiskKey),
                  title: const Text(
                    kSuiteUsageDiskLabel,
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: Text(
                    _diskUsageText,
                    style: const TextStyle(fontSize: 13),
                  ),
                  trailing: _usageBusy
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : IconButton(
                          key: const Key('suite_usage_refresh'),
                          tooltip: 'Refresh usage',
                          onPressed: _busy ? null : _refreshUsage,
                          icon: const Icon(Icons.refresh),
                        ),
                ),
                const Divider(height: 1),
                ListTile(
                  key: const Key(kSuiteUsageProcessKey),
                  title: const Text(
                    kSuiteUsageProcessLabel,
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: Text(
                    '$_processUsageText of process capacity',
                    style: const TextStyle(fontSize: 13),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          // Website-equivalent fleet wipe clock (read-only Settings window).
          const NodeWipeTimerPanel(),
          if (!freeTierSettingsLocked) ...[
            const SizedBox(height: 20),
            Text(
              kPrivacyScaleTitle,
              style: TextStyle(
                color: suitePrimaryOf(context),
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              kExplainerCoreVpn,
              style: TextStyle(color: suiteTextMutedOf(context), fontSize: 12),
            ),
            const SizedBox(height: 10),
            Container(
              decoration: BoxDecoration(
                color: suitePanelBgOf(context),
                borderRadius: BorderRadius.circular(kCornerRadius),
                border: Border.all(color: suiteBorderOf(context)),
              ),
              child: Column(
                children: [
                  // Residual IPv4 is product always-on (not adjustable).
                  ListTile(
                    title: Text(
                      'IPv4 residual',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: Text(kExplainerResidualIpv4),
                    trailing: Text(
                      'Always on',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: suitePrimaryOf(context),
                      ),
                    ),
                  ),
                  const Divider(height: 1),
                  // Residual IPv6 remains user-toggleable.
                  Tooltip(
                    message: kTooltipResidualIpv6,
                    waitDuration: const Duration(milliseconds: 400),
                    child: SwitchListTile(
                      title: Text(
                        'IPv6 residual',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                      subtitle: Text(kExplainerResidualIpv6),
                      value: _settings.residualIpv6,
                      activeThumbColor: suiteOnPrimaryOf(context),
                      activeTrackColor: suitePrimaryOf(context),
                      onChanged: _busy
                          ? null
                          : (v) => _setResidualStack(ipv6: v),
                    ),
                  ),
                  const Divider(height: 1),
                  SwitchListTile(
                    title: Text(
                      'Traffic shaping',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: Text(kExplainerTrafficShape),
                    value: _settings.privacyTrafficShape,
                    activeThumbColor: suiteOnPrimaryOf(context),
                    activeTrackColor: suitePrimaryOf(context),
                    onChanged: _busy
                        ? null
                        : (v) => _setPrivacyScale(trafficShape: v),
                  ),
                  const Divider(height: 1),
                  SwitchListTile(
                    title: Text(
                      'Outer obfuscation',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: Text(kExplainerOuterObfuscation),
                    value: _settings.privacyOuterObfuscation,
                    activeThumbColor: suiteOnPrimaryOf(context),
                    activeTrackColor: suitePrimaryOf(context),
                    onChanged: _busy
                        ? null
                        : (v) => _setPrivacyScale(outerObfuscation: v),
                  ),
                  const Divider(height: 1),
                  SwitchListTile(
                    title: Text(
                      'Multi-hop residual',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: Text(kExplainerMultihop),
                    value: _settings.privacyMultihop,
                    activeThumbColor: suiteOnPrimaryOf(context),
                    activeTrackColor: suitePrimaryOf(context),
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
                color: suitePrimaryOf(context),
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Basic Iceland residual only — privacy options are fixed and '
              'cannot be changed. Single-hop entry; no multi-hop, traffic '
              'shaping, or outer obfuscation toggles.',
              style: TextStyle(color: suiteTextMutedOf(context), fontSize: 12),
            ),
          ],
          const SizedBox(height: 20),
          Text(
            kPingStatsTitle,
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kPingStatsDisclaimer,
            style: TextStyle(color: suiteTextMutedOf(context), fontSize: 12),
          ),
          const SizedBox(height: 8),
          Text(_entryPing, style: TextStyle(fontSize: 13, color: suiteTextOf(context))),
          const SizedBox(height: 4),
          Text(_exitPing, style: TextStyle(fontSize: 13, color: suiteTextOf(context))),
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
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            _licenceAccepted
                ? 'Accepted on this device. Connect is allowed.'
                : 'Not accepted — Connect is blocked until you accept.',
            style: TextStyle(fontSize: 12, color: suiteTextOf(context)),
          ),
          const SizedBox(height: 6),
          Text(
            kShortLicenceSummary,
            style: TextStyle(fontSize: 12, color: suiteTextMutedOf(context)),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton(
              onPressed: _acceptLicence,
              style: FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
              child: Text(kLicenceAcceptButton),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Payment entitlement / keygen',
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kPaymentConnectDisclaimerPlain,
            style: TextStyle(fontSize: 12, color: suiteTextMutedOf(context)),
          ),
          const SizedBox(height: 6),
          Text(
            kKeygenUnlockInstruction,
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: suiteTextOf(context)),
          ),
          const SizedBox(height: 6),
          Text(
            _paymentOk
                ? 'Payment status: $_paymentStatus — Connect allowed for payment.'
                : 'Payment status: $_paymentStatus — Connect blocked until keygen unlocks an active subscription.',
            style: TextStyle(fontSize: 12, color: suiteTextOf(context)),
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
              style: FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
              child: Text('Verify keygen / unlock Connect'),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            kAnonRegistrationTitle,
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kAnonRegistrationSummary,
            style: TextStyle(fontSize: 12, color: suiteTextMutedOf(context)),
          ),
          const SizedBox(height: 6),
          Text(
            kOsPrivilegeHonesty,
            style: TextStyle(fontSize: 12, color: suiteTextMutedOf(context)),
          ),
          const SizedBox(height: 20),
          Text(
            kConnectionLogTitle,
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kConnectionLogDisclaimer,
            style: TextStyle(color: suiteTextMutedOf(context), fontSize: 12),
          ),
          const SizedBox(height: 4),
          Text(
            kSupportLogFindHint,
            style: TextStyle(color: suiteTextMutedOf(context), fontSize: 11),
          ),
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            constraints: const BoxConstraints(minHeight: 100, maxHeight: 160),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: suitePanelBgOf(context),
              borderRadius: BorderRadius.circular(kCornerRadius),
              border: Border.all(color: suiteBorderOf(context)),
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
                style: FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
                child: Text(kExportLogButton),
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
            kLeakPostureSectionTitle,
            key: const Key('residual_leak_posture_title'),
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Container(
            key: const Key('residual_leak_posture_panel'),
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: suitePanelBgOf(context),
              borderRadius: BorderRadius.circular(kCornerRadius),
              border: Border.all(color: suiteBorderOf(context)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  _posture?.headline ??
                      'Residual leak risk: $kLeakPostureLabelUnverified',
                  key: const Key('residual_leak_posture_headline'),
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: suiteTextOf(context),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  _posture?.detail ??
                      'Run Leak test while residual is Connected to confirm '
                      'this session.',
                  style: TextStyle(
                    fontSize: 12,
                    color: suiteTextMutedOf(context),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '• Residual IPv4 capture: '
                  '${(_posture?.residualCaptureActive ?? widget.residualCaptureActive) ? "active" : "not active"}',
                  style: TextStyle(fontSize: 12, color: suiteTextOf(context)),
                ),
                Text(
                  '• IPv6 residual: '
                  '${(_posture?.ipv6Protected ?? widget.ipv6Protected) ? "protected" : "not confirmed"}',
                  style: TextStyle(fontSize: 12, color: suiteTextOf(context)),
                ),
                Text(
                  '• Tunnel DNS: '
                  '${(_posture?.dnsTunnelOnly ?? false) ? "tunnel only" : "not tunnel-only"}',
                  style: TextStyle(fontSize: 12, color: suiteTextOf(context)),
                ),
                Text(
                  '• Kill-switch: '
                  '${_settings.killSwitchOptIn ? "opt-in ON" : "OFF (default)"}',
                  style: TextStyle(fontSize: 12, color: suiteTextOf(context)),
                ),
                const SizedBox(height: 8),
                Text(
                  kLeakPostureHonestyFootnote,
                  key: const Key('residual_leak_posture_footnote'),
                  style: TextStyle(
                    fontSize: 11,
                    height: 1.35,
                    color: suiteTextMutedOf(context),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Text(
            kLeakTestTitle,
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kLeakTestDisclaimer,
            style: TextStyle(color: suiteTextMutedOf(context), fontSize: 12),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton(
              key: const Key('run_leak_test_button'),
              onPressed: runLeakTest,
              style: FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
              child: Text(kLeakTestButton),
            ),
          ),
          if (_leakResult != null) ...[
            const SizedBox(height: 8),
            Text(
              _leakResult!,
              style: TextStyle(fontSize: 12, color: suiteTextOf(context)),
            ),
          ],
          const SizedBox(height: 16),
          Text(
            kPrivateDnsWarningTitle,
            key: const Key('private_dns_warning_title'),
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kPrivateDnsWarningBody,
            key: const Key('private_dns_warning_body'),
            style: TextStyle(fontSize: 12, color: suiteTextMutedOf(context)),
          ),
          const SizedBox(height: 16),
          Text(
            kWebRtcStunGuidanceTitle,
            key: const Key('webrtc_stun_guidance_title'),
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            kWebRtcStunGuidanceBody,
            key: const Key('webrtc_stun_guidance_body'),
            style: TextStyle(fontSize: 12, color: suiteTextMutedOf(context)),
          ),
          const SizedBox(height: 12),
          SwitchListTile(
            key: const Key('kill_switch_opt_in_tile'),
            contentPadding: EdgeInsets.zero,
            title: Text(
              kKillSwitchSettingsLabel,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: suiteTextOf(context),
              ),
            ),
            subtitle: Text(
              kKillSwitchSettingsBody,
              style: TextStyle(fontSize: 11, color: suiteTextMutedOf(context)),
            ),
            value: _settings.killSwitchOptIn,
            onChanged: _busy ? null : (v) => _setKillSwitch(v),
          ),
          const SizedBox(height: 20),
          Text(
            kDpiMitigationTitle,
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: suitePanelBgOf(context),
              borderRadius: BorderRadius.circular(kCornerRadius),
              border: Border.all(color: suiteBorderOf(context)),
            ),
            child: Text(
              '$kDpiMitigationDisclaimer\n\n$kConnectedIdlePowerHonesty',
              style: TextStyle(fontSize: 12, color: suiteTextOf(context)),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Documents',
            style: TextStyle(
              color: suitePrimaryOf(context),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            decoration: BoxDecoration(
              color: suitePanelBgOf(context),
              borderRadius: BorderRadius.circular(kCornerRadius),
              border: Border.all(color: suiteBorderOf(context)),
            ),
            child: Column(
              children: [
                for (var i = 0; i < kLegalDocLinks.length; i++) ...[
                  if (i > 0) const Divider(height: 1),
                  ListTile(
                    title: Text(
                      kLegalDocLinks[i].label,
                      style: TextStyle(fontWeight: FontWeight.w600, color: suitePrimaryOf(context),
                        decoration: TextDecoration.underline,
                      ),
                    ),
                    trailing: Icon(Icons.open_in_new, size: 18, color: suitePrimaryOf(context)),
                    onTap: () => _openLegalDoc(kLegalDocLinks[i]),
                  ),
                ],
                const Divider(height: 1),
                ListTile(
                  key: const Key('easter_egg_loft_link'),
                  title: Text(
                    kEasterEggSettingsLabel,
                    style: TextStyle(
                      fontWeight: FontWeight.w500,
                      color: suiteTextMutedOf(context),
                      fontSize: 13,
                    ),
                  ),
                  subtitle: Text(
                    'http://127.0.0.1:18765  ·  while the app is open',
                    style: TextStyle(fontSize: 11, color: suiteTextMutedOf(context)),
                  ),
                  trailing: Icon(Icons.open_in_new, size: 16, color: suiteTextMutedOf(context)),
                  onTap: _openEasterEggLoft,
                ),
              ],
            ),
          ),
          if (_note != null) ...[
            const SizedBox(height: 12),
            Text(_note!, style: TextStyle(color: suitePrimaryOf(context), fontSize: 12)),
          ],
        ],
      ),
    );
  }

  Future<void> _openEasterEggLoft() async {
    // Ensure the loft is up (no-op if already listening).
    final listening = await easterEggServer.start();
    if (!listening && mounted) {
      setState(() {
        _note =
            'Local loft could not bind :$kEasterEggPort (port busy?). '
            'Try $kEasterEggUrlLoopback while the Suite app is open and nothing else owns that port.';
      });
      return;
    }
    final uri = Uri.parse(kEasterEggUrlLoopback);
    try {
      final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!ok && mounted) {
        setState(() => _note = 'Open $kEasterEggUrlLoopback in a browser (app must stay running).');
      }
    } catch (_) {
      if (mounted) {
        setState(() => _note = 'Open $kEasterEggUrlLoopback in a browser (app must stay running).');
      }
    }
  }
}
