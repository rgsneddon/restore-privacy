import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'connect_status.dart';
import 'connection_log.dart';
import 'country_select.dart';
import 'licence_gate.dart';
import 'macos_window.dart';
import 'prefs_backend.dart';
import 'registration_copy.dart';
import 'rpt_config.dart';
import 'free_tier.dart';
import 'settings_screen.dart';
import 'settings_store.dart';
import 'theme.dart';
import 'vpn_controller.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
      systemNavigationBarColor: Colors.transparent,
      systemNavigationBarIconBrightness: Brightness.dark,
    ),
  );
  runApp(const RestorePrivacyApp());
}

class RestorePrivacyApp extends StatelessWidget {
  const RestorePrivacyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: kAppTitle,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.light,
        scaffoldBackgroundColor: kChromeBg,
        fontFamily: 'Segoe UI',
        colorScheme: const ColorScheme.light(
          primary: kPrimary,
          surface: kPanelBg,
          onPrimary: kWhite,
          onSurface: kText,
        ),
        useMaterial3: true,
      ),
      home: const TunnelHome(),
    );
  }
}

/// Seamless product shell: hero status, Connect/Disconnect, Settings transparency.
///
/// Minimize / background does **not** stop the tunnel — only Disconnect does.
/// Licence acceptance is required before Connect; autoconnect cannot bypass it.
class TunnelHome extends StatefulWidget {
  const TunnelHome({super.key, this.settingsStore, this.licenceGate});

  /// Injectable store for tests; production loads SharedPreferences.
  final SettingsStore? settingsStore;
  final LicenceGate? licenceGate;

  @override
  State<TunnelHome> createState() => _TunnelHomeState();
}

class _TunnelHomeState extends State<TunnelHome> with WidgetsBindingObserver {
  late final VpnController _vpn;
  final MacWindowController _macWindow = MacWindowController();
  SettingsStore? _store;
  LicenceGate? _licence;
  ProductSettings _settings = ProductSettings.defaults;
  ConnectionLog? _connectionLog;
  final List<String> _log = [];
  final ScrollController _logScroll = ScrollController();
  String _status = 'Not connected. Press Connect when you want protection.';
  String? _vpnIp;
  bool _connected = false;
  bool _busy = false;
  bool _autoconnectAttempted = false;
  bool _licenceAccepted = false;
  /// Sticky until product Connect succeeds so Open VPN settings survives open feedback.
  bool _needsVpnSystemSettingsApproval = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _vpn = VpnController(onStatus: _onStatus);
    // macOS menu bar tray → Flutter Disconnect / Show
    _macWindow.setHandlers(
      onTrayDisconnect: () {
        if (!_connected || _busy) return;
        _onToggle();
      },
      onTrayShow: () {
        // Native already orders the window front; keep Flutter mounted.
      },
    );
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _initSettings();
      if (!mounted) return;
      _append(kAppTitle);
      _append(kPrivacyMessageText);
      _append(kSeamlessHint);
      _append('Version ${RptConfig.displayProductVersion}');
      await _rehydrateSession(from: 'launch');
      if (!_licenceAccepted) {
        await _showLicenceSheet();
      }
      // After licence: renew if EXPIRED, else keygen if still required.
      if (mounted && await (_licence?.needsLicenceRenewal() ?? false)) {
        await _showRenewLicenceSheet();
      } else if (mounted && await (_licence?.needsKeygenUnlock() ?? false)) {
        await _showKeygenSheet();
      }
      await _maybeAutoconnect();
    });
  }

  Future<void> _initSettings() async {
    if (widget.settingsStore != null) {
      _store = widget.settingsStore;
    } else {
      try {
        final backend = await SharedPreferencesBackend.create();
        _store = SettingsStore(backend);
      } catch (_) {
        _store = SettingsStore(MemorySettingsBackend());
      }
    }
    if (widget.licenceGate != null) {
      _licence = widget.licenceGate;
    } else {
      try {
        final prefs = await SharedPreferences.getInstance();
        _licence = LicenceGate(
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
      } catch (_) {
        _licence = LicenceGate(MemoryLicenceBackend());
      }
    }
    try {
      final prefs = await SharedPreferences.getInstance();
      _connectionLog = ConnectionLog(PrefsConnectionLogBackend(prefs));
    } catch (_) {
      _connectionLog = ConnectionLog(MemoryConnectionLogBackend());
    }
    final loaded = await _store!.load();
    RptConfig.setRuntimeMultiHop(loaded.privacyMultihop);
    RptConfig.setRuntimeEntryCountry(loaded.entryCountry);
    if (mounted) {
      setState(() => _settings = loaded);
    } else {
      _settings = loaded;
    }
    // Refresh payment if we already have a session id (post-pay recheck)
    final sid = await _licence!.paymentSessionId();
    if (sid.isNotEmpty) {
      try {
        await _licence!.refreshEntitlementFromRemote();
      } catch (_) {}
    }
    final licOk = await _licence!.hasAcceptedLicence();
    final canConnect = await _licence!.mayConnect();
    if (!mounted) return;
    setState(() {
      _settings = loaded;
      _licenceAccepted = licOk;
      if (!canConnect) {
        _status = licOk
            ? 'Enter keygen from your fulfilment email (unlock dialog), then Connect.'
            : 'Accept the licence, enter keygen, then Connect for residual protection.';
      } else {
        _status =
            'Ready. Press Connect when you want residual protection.';
      }
    });
  }

  Future<void> _connLog(String kind, String message) async {
    try {
      await _connectionLog?.appendEvent(kind, message);
    } catch (_) {}
  }

  Future<void> _showLicenceSheet() async {
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: kPanelBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                kLicencePromptTitle,
                style: TextStyle(
                  color: kPrimaryDark,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 10),
              const Text(kShortLicenceSummary, style: TextStyle(fontSize: 13)),
              const SizedBox(height: 10),
              const Text(
                kAnonRegistrationSummary,
                style: TextStyle(fontSize: 12, color: kTextMuted),
              ),
              const SizedBox(height: 6),
              const Text(
                kOsPrivilegeHonesty,
                style: TextStyle(fontSize: 12, color: kTextMuted),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () async {
                  await _licence?.acceptLicence();
                  if (!mounted) return;
                  setState(() {
                    _licenceAccepted = true;
                    _status =
                        'Licence accepted. Enter your keygen from the fulfilment email to unlock Connect.';
                  });
                  _append('Licence accepted (stored locally only).');
                  Navigator.of(ctx).pop();
                  if (mounted &&
                      await (_licence?.needsLicenceRenewal() ?? false)) {
                    await _showRenewLicenceSheet();
                  } else if (mounted &&
                      await (_licence?.needsKeygenUnlock() ?? false)) {
                    await _showKeygenSheet();
                  }
                },
                style: FilledButton.styleFrom(backgroundColor: kPrimary),
                child: const Text(kLicenceAcceptButton),
              ),
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: const Text('Not now'),
              ),
            ],
          ),
        );
      },
    );
  }

  /// EXPIRED hard-lock: renew your licence *here* + platform payment portal.
  Future<void> _showRenewLicenceSheet() async {
    if (!mounted) return;
    final gate = _licence;
    final url = await gate?.renewPortalUrlForInstall() ??
        renewLicenceUrl(platform: platformForRenew());
    final body = await gate?.renewMessageForInstall() ??
        renewLicenceMessage(platform: platformForRenew(), renewUrl: url);
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: kPanelBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return Padding(
          padding: EdgeInsets.fromLTRB(
            20,
            16,
            20,
            28 + MediaQuery.of(ctx).viewInsets.bottom,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                kRenewLicencePromptTitle,
                style: TextStyle(
                  color: kPrimaryDark,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                'Your subscription is EXPIRED. Renew your licence *here*:',
                style: TextStyle(fontSize: 14),
              ),
              const SizedBox(height: 10),
              SelectableText(
                url,
                style: const TextStyle(
                  fontSize: 13,
                  color: kPrimary,
                  decoration: TextDecoration.underline,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                body,
                style: const TextStyle(fontSize: 12, color: kTextMuted),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () async {
                  final uri = Uri.tryParse(url);
                  if (uri != null) {
                    try {
                      await launchUrl(
                        uri,
                        mode: LaunchMode.externalApplication,
                      );
                    } catch (_) {
                      _append('Could not open browser. Visit: $url');
                    }
                  }
                },
                style: FilledButton.styleFrom(backgroundColor: kPrimary),
                child: const Text('Open payment portal'),
              ),
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: const Text('Close'),
              ),
            ],
          ),
        );
      },
    );
  }

  /// Forced keygen unlock surface (parity with Windows/Linux desktop modals).
  Future<void> _showKeygenSheet() async {
    // EXPIRED installs must renew — never show keygen in place of renew.
    if (await (_licence?.needsLicenceRenewal() ?? false)) {
      await _showRenewLicenceSheet();
      return;
    }
    if (!mounted) return;
    final controller = TextEditingController();
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: kPanelBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        var statusLine = '';
        return StatefulBuilder(
          builder: (ctx, setModal) {
            return Padding(
              padding: EdgeInsets.fromLTRB(
                20,
                16,
                20,
                28 + MediaQuery.of(ctx).viewInsets.bottom,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    kKeygenPromptTitle,
                    style: TextStyle(
                      color: kPrimaryDark,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 10),
                  const Text(kKeygenPromptBody, style: TextStyle(fontSize: 13)),
                  const SizedBox(height: 8),
                  const Text(
                    kConnectBlockedKeygenMsg,
                    style: TextStyle(fontSize: 12, color: kTextMuted),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: controller,
                    decoration: const InputDecoration(
                      labelText: 'RPT-KEY-…',
                      border: OutlineInputBorder(),
                    ),
                    autocorrect: false,
                    enableSuggestions: false,
                  ),
                  if (statusLine.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(statusLine, style: const TextStyle(fontSize: 12)),
                  ],
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: () async {
                      final raw = controller.text.trim();
                      if (raw.isEmpty) {
                        setModal(() => statusLine = 'Paste the keygen first.');
                        return;
                      }
                      setModal(
                        () => statusLine =
                            'Verifying keygen with status host…',
                      );
                      final st = await _licence?.importKeygenAndVerify(raw) ??
                          kPaymentStatusUnknown;
                      final ok = await _licence?.paymentAllowsConnect() ?? false;
                      if (!mounted) return;
                      if (ok) {
                        setState(() {
                          _status =
                              'Keygen verified. Press Connect for residual protection.';
                        });
                        _append('Keygen unlocked (status=$st).');
                        Navigator.of(ctx).pop();
                      } else {
                        setModal(
                          () => statusLine =
                              'Keygen not active (status=$st). Check email code / subscription.',
                        );
                      }
                    },
                    style: FilledButton.styleFrom(backgroundColor: kPrimary),
                    child: const Text('Unlock Connect'),
                  ),
                  TextButton(
                    onPressed: () => Navigator.of(ctx).pop(),
                    child: const Text('Cancel'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<bool> assertMayConnect() async {
    final gate = _licence;
    if (gate == null) return false;
    // Refreshes remote payment entitlement so refunds cancel Connect.
    final r = await gate.assertMayConnect(refreshPayment: true);
    if (!r.ok) {
      _append(r.message);
      setState(() => _status = r.message);
      final licOk = await gate.hasAcceptedLicence();
      if (!licOk) {
        await _showLicenceSheet();
      } else if (await gate.needsLicenceRenewal()) {
        await _showRenewLicenceSheet();
      } else if (await gate.needsKeygenUnlock()) {
        await _showKeygenSheet();
      }
      return false;
    }
    return true;
  }

  Future<void> _maybeAutoconnect() async {
    if (_autoconnectAttempted) return;
    _autoconnectAttempted = true;
    final store = _store;
    if (store == null) return;
    final s = await store.load();
    if (!store.shouldAutoconnectOnLaunch(s)) return;
    if (_connected || _busy) return;
    // Never bypass licence on autoconnect.
    if (!await assertMayConnect()) {
      _append('Settings: autoconnect skipped — accept the end-user licence first.');
      return;
    }
    _append('Settings: autoconnect on launch — starting Connect…');
    await _onToggleConnectOnly();
  }

  Future<void> _onToggleConnectOnly() async {
    // Connect path only (used by autoconnect)
    if (_busy || _connected) return;
    // Gate: valid catalog entry country (empty → Iceland default).
    final resolved = resolveEntryCountrySelection(
      _settings.entryCountry,
      allowDefault: true,
    );
    if (!resolved.ok ||
        !entryCountryAllowsConnect(resolved.code, allowDefault: false)) {
      final msg =
          'Choose a valid entry country above Connect (Iceland is the default).';
      _append(msg);
      setState(() {
        _status = msg;
        _settings = _settings.copyWith(entryCountry: kDefaultEntryCountry);
      });
      RptConfig.setRuntimeEntryCountry(kDefaultEntryCountry);
      await _store?.save(_settings);
      return;
    }
    RptConfig.setRuntimeEntryCountry(resolved.code);
    RptConfig.setRuntimeMultiHop(_settings.privacyMultihop);
    if (!await assertMayConnect()) return;
    setState(() => _busy = true);
    try {
      _append(
        'Connect — entry ${countryOptionForCode(resolved.code)?.label ?? resolved.code}…',
      );
      await _connLog(kLogKindConnect, 'Connect started (RPT full tunnel)');
      final ok = await _vpn.connect();
      if (!mounted) return;
      setState(() {
        _connected = ok;
        if (ok) {
          _needsVpnSystemSettingsApproval = false;
          final ipMatch = RegExp(r'10\.\d+\.\d+\.\d+').firstMatch(_status);
          _vpnIp = ipMatch?.group(0);
          final v6Not = _status.toLowerCase().contains('ipv6 not protected');
          final v6Ok = _status.toLowerCase().contains('ipv6 isp path blocked');
          _status = plainConnectedStatus(
            vpnIp: _vpnIp,
            residual: true,
            ipv6Protected: v6Not ? false : (v6Ok ? true : null),
          );
        } else if (isNeVpnPermissionFailureMessage(_status) ||
            shouldPromptOpenVpnSystemSettings({
              'ok': false,
              'message': _status,
              'fullTunnelActive': false,
            })) {
          // Sticky so Open VPN settings remains after log-only open feedback.
          _needsVpnSystemSettingsApproval = true;
        }
      });
      if (ok) {
        _append(_status);
        await _connLog(kLogKindConnect, 'Connected — residual path active');
        // macOS: hide to menu-bar tray only after product full-tunnel success.
        if (shouldHideToTrayAfterConnectSuccess(ok)) {
          await _macWindow.setTrayConnected(true);
          await _macWindow.hideToTray(connected: true);
          _append('Window hidden to menu bar tray — restore via the RP tray icon.');
        }
      } else {
        await _connLog(kLogKindError, 'Connect failed');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (shouldStopTunnelOnAppLifecycle(state.name)) {
      return;
    }
    if (state == AppLifecycleState.resumed) {
      _rehydrateSession(from: 'resume');
    }
  }

  Future<void> _rehydrateSession({required String from}) async {
    final snap = await _vpn.querySession();
    if (!mounted) return;
    // While Connect is in flight, do not overwrite Connecting… with Disconnected.
    if (_busy && !snap.connected) {
      if (snap.connecting && (snap.message ?? '').isNotEmpty) {
        setState(() => _status = snap.message!);
      }
      return;
    }
    setState(() {
      _connected = snap.connected;
      _vpnIp = snap.vpnIp;
      if (snap.connected) {
        final msg = (snap.message ?? '').toLowerCase();
        final v6Not = msg.contains('ipv6 not protected');
        final v6Ok = msg.contains('ipv6 isp path blocked');
        _status = plainConnectedStatus(
          vpnIp: snap.vpnIp,
          residual: true,
          ipv6Protected: v6Not ? false : (v6Ok ? true : null),
        );
      } else if (snap.connecting) {
        _status = snap.message ?? connectingStatusMessage();
      } else if (from == 'resume' && !_busy) {
        if (_status.toLowerCase().contains('connected') && !snap.connected) {
          _status = 'Not connected. Press Connect when you want protection.';
        }
      }
    });
    if (snap.connected && from == 'resume') {
      _append('Resumed — VPN still active (minimize did not disconnect).');
    }
  }

  void _onStatus(String msg) {
    if (!mounted) return;
    setState(() {
      // Open-settings feedback is log-only — never replace residual failure card text
      // (that would hide the Open VPN settings control).
      if (isOpenVpnSettingsFeedbackMessage(msg)) {
        _log.add(msg);
        return;
      }
      _status = msg;
      _log.add(msg);
      if (isNeVpnPermissionFailureMessage(msg)) {
        _needsVpnSystemSettingsApproval = true;
      }
    });
    _scrollLogToEnd();
  }

  void _append(String msg) {
    setState(() => _log.add(msg));
    _scrollLogToEnd();
  }

  void _scrollLogToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_logScroll.hasClients) {
        _logScroll.jumpTo(_logScroll.position.maxScrollExtent);
      }
    });
  }

  Future<void> _onToggle() async {
    if (_busy) return;
    if (_connected) {
      setState(() => _busy = true);
      try {
        _append('Disconnect — tearing down tunnel…');
        await _connLog(kLogKindDisconnect, 'Disconnect started');
        await _vpn.disconnect();
        if (!mounted) return;
        setState(() {
          _connected = false;
          _vpnIp = null;
          _status = 'Disconnected. Press Connect when you want protection.';
        });
        _append('Disconnected.');
        await _connLog(kLogKindDisconnect, 'Disconnected');
        await _macWindow.setTrayConnected(false);
        // Restore UI after explicit disconnect so status is visible.
        await _macWindow.showFromTray();
      } finally {
        if (mounted) setState(() => _busy = false);
      }
    } else {
      await _onToggleConnectOnly();
    }
  }

  Future<void> _openSettings() async {
    final store = _store;
    if (store == null) return;
    final updated = await Navigator.of(context).push<ProductSettings>(
      MaterialPageRoute(
        builder: (_) => SettingsScreen(
          store: store,
          initial: _settings,
          connectionLog: _connectionLog,
          licenceGate: _licence,
          residualCaptureActive: _connected,
          residualConnected: _connected,
          ipv6Protected: _status.toLowerCase().contains('ipv6 isp path blocked'),
          onLicenceChanged: (accepted) {
            if (mounted) setState(() => _licenceAccepted = accepted);
          },
          onChanged: (s) {
            RptConfig.setRuntimeMultiHop(s.privacyMultihop);
            if (mounted) setState(() => _settings = s);
          },
        ),
      ),
    );
    if (updated != null && mounted) {
      setState(() => _settings = updated);
    }
    if (mounted) {
      final s = await store.load();
      final licOk = await _licence?.hasAcceptedLicence() ?? false;
      setState(() {
        _settings = s;
        _licenceAccepted = licOk;
      });
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _logScroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final btnLabel = connectButtonLabel(_connected);
    final btnColor = _connected ? kButtonDisconnectBg : kButtonConnectBg;
    final statusColor = _connected
        ? kStatusOk
        : (_busy ? kPrimary : kText);
    final cardTitle = statusCardTitle(
      connected: _connected,
      busyConnecting: _busy && !_connected,
      vpnIp: _vpnIp,
      residual: true,
    );

    return Scaffold(
      backgroundColor: kChromeBg,
      body: SafeArea(
        top: true,
        bottom: true,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.asset(
                      kLogoAsset,
                      width: 48,
                      height: 48,
                      errorBuilder: (context, error, stackTrace) => Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: kPrimaryDark,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        alignment: Alignment.center,
                        child: const Text(
                          'RP',
                          style: TextStyle(
                            color: kWhite,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          kAppTitle,
                          style: TextStyle(
                            color: kPrimaryDark,
                            fontWeight: FontWeight.bold,
                            fontSize: 18,
                          ),
                        ),
                        const Text(
                          kBannerTitle,
                          style: TextStyle(
                            color: kTextMuted,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          kSeamlessTagline,
                          style: TextStyle(
                            color: kPrimary,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Settings',
                    onPressed: _openSettings,
                    icon: const Icon(Icons.settings, color: kPrimaryDark),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Container(
                decoration: BoxDecoration(
                  color: kPanelBg,
                  borderRadius: BorderRadius.circular(kCornerRadius),
                  border: Border.all(color: kBorder),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Expanded(
                          child: Text(
                            'VPN status',
                            style: TextStyle(
                              color: kTextMuted,
                              fontSize: 11,
                            ),
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: _licenceAccepted
                                ? kLightAccent
                                : const Color(0xFFFDECEC),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            _licenceAccepted
                                ? 'Licence accepted'
                                : 'Licence required',
                            style: TextStyle(
                              color: _licenceAccepted
                                  ? kPrimaryDark
                                  : kStatusError,
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      cardTitle,
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.w700,
                        fontSize: 17,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _status,
                      style: const TextStyle(
                        color: kTextMuted,
                        fontSize: 12,
                      ),
                    ),
                    if (!_licenceAccepted) ...[
                      const SizedBox(height: 10),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: FilledButton(
                          onPressed: _showLicenceSheet,
                          style: FilledButton.styleFrom(
                            backgroundColor: kPrimary,
                          ),
                          child: const Text(kLicenceAcceptButton),
                        ),
                      ),
                    ],
                    // macOS NE permission / host-only HELLO: open System Settings so user can Allow VPN.
                    // Sticky flag keeps the control after open success/failure feedback (log-only).
                    if (shouldShowOpenVpnSettingsControl(
                      connected: _connected,
                      needsVpnSystemSettingsApproval:
                          _needsVpnSystemSettingsApproval,
                      statusMessage: _status,
                    )) ...[
                      const SizedBox(height: 10),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: OutlinedButton.icon(
                          onPressed: _busy
                              ? null
                              : () async {
                                  _append(
                                    'Opening System Settings → Network / VPN…',
                                  );
                                  // reportStatus: false — keep residual failure on the card.
                                  final opened = await _vpn
                                      .openVpnSystemSettings(
                                    reportStatus: false,
                                  );
                                  if (!mounted) return;
                                  setState(() {
                                    _needsVpnSystemSettingsApproval = true;
                                  });
                                  _append(
                                    opened
                                        ? kOpenVpnSettingsOpenedFeedback
                                        : kOpenVpnSettingsFailedFeedback,
                                  );
                                },
                          icon: const Icon(Icons.settings_ethernet, size: 18),
                          label: const Text(kOpenVpnSettingsLabel),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: kPanelBg,
                    borderRadius: BorderRadius.circular(kCornerRadius),
                    border: Border.all(color: kBorder),
                  ),
                  padding: const EdgeInsets.all(10),
                  child: ListView.builder(
                    controller: _logScroll,
                    itemCount: _log.length,
                    itemBuilder: (_, i) => Text(
                      _log[i],
                      style: const TextStyle(
                        color: kText,
                        fontSize: 13,
                        height: 1.35,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              // Entry country (flags) — main shell above Connect, not Settings-only
              Text(
                'Entry country',
                style: TextStyle(
                  color: kTextMuted,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: kPanelBg,
                  borderRadius: BorderRadius.circular(kCornerRadius),
                  border: Border.all(color: kBorder),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    isExpanded: true,
                    value: normalizeEntryCountry(_settings.entryCountry),
                    items: [
                      for (final o in kProductCountryCatalog)
                        DropdownMenuItem<String>(
                          value: o.code,
                          child: Text(
                            o.label,
                            style: const TextStyle(fontSize: 15),
                          ),
                        ),
                    ],
                    onChanged: _busy
                        ? null
                        : (code) async {
                            if (code == null) return;
                            final next = normalizeEntryCountry(code);
                            final updated =
                                _settings.copyWith(entryCountry: next);
                            setState(() => _settings = updated);
                            RptConfig.setRuntimeEntryCountry(next);
                            await _store?.save(updated);
                            _append(
                              'Entry country: ${countryOptionForCode(next)?.label ?? next} (next Connect)',
                            );
                          },
                  ),
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                height: 52,
                child: ElevatedButton(
                  onPressed: _busy ? null : _onToggle,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: btnColor,
                    foregroundColor: kButtonFg,
                    disabledBackgroundColor: btnColor.withValues(alpha: 0.5),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(kCornerRadius),
                    ),
                    textStyle: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  child: Text(_busy ? 'Please wait…' : btnLabel),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _settings.autoconnectOnLaunch
                    ? 'Autoconnect on launch is ON (Settings). Minimize keeps VPN alive.'
                    : 'Manual Connect, or enable seamless power-up in Settings ⚙',
                style: const TextStyle(
                  color: kTextMuted,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

typedef RetroTunnelHome = TunnelHome;
