import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connect_status.dart';
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

/// Windows-aligned product shell: logo, status card, Connect/Disconnect.
///
/// Minimize / background does **not** stop the tunnel — only Disconnect does.
/// On resume, session status is rehydrated from the native VPN service.
class TunnelHome extends StatefulWidget {
  const TunnelHome({super.key});

  @override
  State<TunnelHome> createState() => _TunnelHomeState();
}

class _TunnelHomeState extends State<TunnelHome> with WidgetsBindingObserver {
  late final VpnController _vpn;
  final List<String> _log = [];
  final ScrollController _logScroll = ScrollController();
  String _status = 'Not connected. Press Connect when you want protection.';
  String? _vpnIp;
  bool _connected = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _vpn = VpnController(onStatus: _onStatus);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _append(kAppTitle);
      _append(kScrollingPrivacyText);
      _append('Manual only — Connect starts, Disconnect stops.');
      _append(
        'Minimize keeps the VPN running. Use Disconnect to stop the tunnel.',
      );
      // Never auto-connect on launch (product policy).
      assert(!VpnController.autoConnectOnLaunchEnabled);
      _rehydrateSession(from: 'launch');
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Product policy: never stop tunnel on pause/inactive/detached/hidden.
    if (shouldStopTunnelOnAppLifecycle(state.name)) {
      // Unreachable with current policy (always false) — kept for contract.
      return;
    }
    if (state == AppLifecycleState.resumed) {
      _rehydrateSession(from: 'resume');
    }
  }

  Future<void> _rehydrateSession({required String from}) async {
    final snap = await _vpn.querySession();
    if (!mounted) return;
    setState(() {
      _connected = snap.connected;
      _vpnIp = snap.vpnIp;
      if (snap.connected) {
        _status = plainConnectedStatus(vpnIp: snap.vpnIp, residual: true);
      } else if (from == 'resume' && !_busy) {
        // Keep last status unless we know we are down
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
    setState(() => _busy = true);
    try {
      if (_connected) {
        _append('Disconnect — tearing down tunnel…');
        await _vpn.disconnect();
        if (!mounted) return;
        setState(() {
          _connected = false;
          _vpnIp = null;
          _status = 'Disconnected. Press Connect when you want protection.';
        });
        _append('Disconnected.');
      } else {
        _append('Connect — starting RPT full tunnel…');
        final ok = await _vpn.connect();
        if (!mounted) return;
        setState(() {
          _connected = ok;
          if (ok) {
            // Prefer message already set by controller; refine card title
            final ipMatch = RegExp(r'10\.\d+\.\d+\.\d+').firstMatch(_status);
            _vpnIp = ipMatch?.group(0);
            _status = plainConnectedStatus(vpnIp: _vpnIp, residual: true);
          }
        });
        if (ok) {
          _append('Connected — residual traffic uses the VPN node.');
        }
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    // Widget teardown only — must NOT call disconnect (tunnel stays up).
    WidgetsBinding.instance.removeObserver(this);
    _logScroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final btnLabel = connectButtonLabel(_connected);
    final btnColor = _connected ? kButtonDisconnectBg : kButtonConnectBg;
    final statusColor = _connected ? kStatusOk : kText;

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
              // Header: logo + title (Windows-aligned)
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
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          kAppTitle,
                          style: TextStyle(
                            color: kPrimaryDark,
                            fontWeight: FontWeight.bold,
                            fontSize: 18,
                          ),
                        ),
                        Text(
                          kBannerTitle,
                          style: TextStyle(
                            color: kTextMuted,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              // Status card (plain language)
              Container(
                decoration: BoxDecoration(
                  color: kPanelBg,
                  borderRadius: BorderRadius.circular(kCornerRadius),
                  border: Border.all(color: kBorder),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _connected
                          ? plainConnectedStatus(vpnIp: _vpnIp, residual: true)
                          : 'Disconnected',
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.w600,
                        fontSize: 15,
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
                  ],
                ),
              ),
              const SizedBox(height: 12),
              // Activity log
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
              // Primary Connect / Disconnect
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
              const Text(
                'Manual only — Connect starts, Disconnect stops. Minimize keeps the VPN alive.',
                style: TextStyle(
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

/// Back-compat alias used by older tests / docs.
typedef RetroTunnelHome = TunnelHome;
