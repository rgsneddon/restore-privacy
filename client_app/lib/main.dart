import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'connect_status.dart';
import 'connection_log.dart';
import 'licence_gate.dart';
import 'macos_window.dart';
import 'prefs_backend.dart';
import 'registration_copy.dart';
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
      await _rehydrateSession(from: 'launch');
      if (!_licenceAccepted) {
        await _showLicenceSheet();
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
    final accepted = await _licence!.mayConnect();
    if (!mounted) return;
    setState(() {
      _settings = loaded;
      _licenceAccepted = accepted;
      if (!accepted) {
        _status =
            'Accept the licence, then press Connect for residual protection.';
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
                        'Licence accepted. Press Connect when you want protection.';
                  });
                  _append('Licence accepted (stored locally only).');
                  Navigator.of(ctx).pop();
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

  Future<bool> assertMayConnect() async {
    final gate = _licence;
    if (gate == null) return false;
    final r = await gate.assertMayConnect();
    if (!r.ok) {
      _append(r.message);
      setState(() => _status = r.message);
      await _showLicenceSheet();
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
    if (!await assertMayConnect()) return;
    setState(() => _busy = true);
    try {
      _append('Connect — starting RPT full tunnel…');
      await _connLog(kLogKindConnect, 'Connect started (RPT full tunnel)');
      final ok = await _vpn.connect();
      if (!mounted) return;
      setState(() {
        _connected = ok;
        if (ok) {
          final ipMatch = RegExp(r'10\.\d+\.\d+\.\d+').firstMatch(_status);
          _vpnIp = ipMatch?.group(0);
          final v6Not = _status.toLowerCase().contains('ipv6 not protected');
          final v6Ok = _status.toLowerCase().contains('ipv6 isp path blocked');
          _status = plainConnectedStatus(
            vpnIp: _vpnIp,
            residual: true,
            ipv6Protected: v6Not ? false : (v6Ok ? true : null),
          );
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
      _status = msg;
      _log.add(msg);
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
          ipv6Protected: _status.toLowerCase().contains('ipv6 isp path blocked'),
          onLicenceChanged: (accepted) {
            if (mounted) setState(() => _licenceAccepted = accepted);
          },
          onChanged: (s) {
            if (mounted) setState(() => _settings = s);
          },
        ),
      ),
    );
    if (updated != null && mounted) {
      setState(() => _settings = updated);
    } else if (mounted) {
      final s = await store.load();
      final accepted = await _licence?.mayConnect() ?? false;
      setState(() {
        _settings = s;
        _licenceAccepted = accepted;
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
