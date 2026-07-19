import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'theme.dart';
import 'vpn_controller.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Colors.transparent,
      systemNavigationBarIconBrightness: Brightness.light,
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
        brightness: Brightness.dark,
        scaffoldBackgroundColor: kChromeBg,
        fontFamily: 'monospace',
        colorScheme: const ColorScheme.dark(
          primary: kButtonBg,
          surface: kChromeBg,
        ),
      ),
      home: const TunnelHome(),
    );
  }
}

/// Dark-blue chrome, black log, logo + title, single Connect/Disconnect button.
///
/// Closing / disposing the UI does **not** stop the tunnel — only the button does.
class TunnelHome extends StatefulWidget {
  const TunnelHome({super.key});

  @override
  State<TunnelHome> createState() => _TunnelHomeState();
}

class _TunnelHomeState extends State<TunnelHome> {
  late final VpnController _vpn;
  final List<String> _log = [];
  final ScrollController _logScroll = ScrollController();
  String _status = 'Ready — press Connect to start the tunnel';
  bool _connected = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _vpn = VpnController(onStatus: _onStatus);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _append(kAppTitle);
      _append(kScrollingPrivacyText);
      _append('Press Connect to attach to the RPT node.');
      _append(
        'Closing this window does not disconnect — use Disconnect to stop the tunnel.',
      );
    });
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
          _status = 'Disconnected — press Connect to reconnect';
        });
        _append('Disconnected.');
      } else {
        _append('Connect — starting RPT handshake…');
        final ok = await _vpn.connect();
        if (!mounted) return;
        setState(() {
          _connected = ok;
          if (ok) {
            _status = 'CONNECTED — tunnel active';
          }
        });
        if (ok) {
          _append('Connected.');
        }
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    // Window/widget teardown only (tunnel keeps running until user taps Disconnect).
    _logScroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final btnLabel = connectButtonLabel(_connected);
    final btnColor = _connected ? kButtonActiveBg : kButtonBg;

    return Scaffold(
      backgroundColor: kChromeBg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header: logo + title
              Row(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.asset(
                      kLogoAsset,
                      width: 48,
                      height: 48,
                      errorBuilder: (_, __, ___) => Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: kBannerBg,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        alignment: Alignment.center,
                        child: const Text(
                          'RP',
                          style: TextStyle(
                            color: kWindowFg,
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
                            color: kWindowFg,
                            fontWeight: FontWeight.bold,
                            fontSize: 18,
                            letterSpacing: 0.5,
                          ),
                        ),
                        Text(
                          kBannerTitle,
                          style: TextStyle(
                            color: kStatusFg,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              // Black log window with rounded border
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: kLogBorder,
                    borderRadius: BorderRadius.circular(kCornerRadius),
                  ),
                  padding: const EdgeInsets.all(3),
                  child: Container(
                    decoration: BoxDecoration(
                      color: kWindowBg,
                      borderRadius: BorderRadius.circular(kCornerRadius - 2),
                    ),
                    padding: const EdgeInsets.all(10),
                    child: ListView.builder(
                      controller: _logScroll,
                      itemCount: _log.length,
                      itemBuilder: (_, i) => Text(
                        _log[i],
                        style: const TextStyle(
                          color: kWindowFg,
                          fontSize: 13,
                          fontFamily: 'monospace',
                          height: 1.35,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              // Single Connect / Disconnect button
              SizedBox(
                height: 52,
                child: ElevatedButton(
                  onPressed: _busy ? null : _onToggle,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: btnColor,
                    foregroundColor: kWindowFg,
                    disabledBackgroundColor: btnColor.withValues(alpha: 0.5),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(kCornerRadius),
                    ),
                    textStyle: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      fontFamily: 'monospace',
                    ),
                  ),
                  child: Text(_busy ? 'Please wait…' : btnLabel),
                ),
              ),
              const SizedBox(height: 10),
              Text(
                _status,
                style: const TextStyle(
                  color: kStatusFg,
                  fontSize: 12,
                  fontFamily: 'monospace',
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
