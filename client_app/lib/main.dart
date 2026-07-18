import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connect_status.dart';
import 'theme.dart';
import 'vpn_controller.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Edge-to-edge system UI; content uses SafeArea so bars are not overlapped.
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
        scaffoldBackgroundColor: kWindowBg,
        fontFamily: 'monospace',
      ),
      home: const RetroTunnelHome(),
    );
  }
}

/// CLI-style retro window: dark blue banner, black bg, white text, scrolling copy.
/// Layout respects status bar and navigation/gesture bar (SafeArea).
class RetroTunnelHome extends StatefulWidget {
  const RetroTunnelHome({super.key});

  @override
  State<RetroTunnelHome> createState() => _RetroTunnelHomeState();
}

class _RetroTunnelHomeState extends State<RetroTunnelHome>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late final AnimationController _scrollCtrl;
  late final VpnController _vpn;
  final List<String> _log = [];
  String _status = 'Launching…';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _scrollCtrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 18),
    )..repeat();
    _vpn = VpnController(onStatus: _onStatus);
    // Auto-connect on launch — primary product flow
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _append(kScrollingPrivacyText);
      _append('RESTORE PRIVACY tunnel client');
      _vpn.autoConnectOnLaunch();
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // On full app exit/detach, stop Packet Tunnel so residual ISP IP returns.
    if (shouldStopTunnelOnAppLifecycle(state.name)) {
      _vpn.disconnect();
    }
  }

  void _onStatus(String msg) {
    if (!mounted) return;
    setState(() {
      _status = msg;
      _log.add(msg);
    });
  }

  void _append(String msg) {
    setState(() => _log.add(msg));
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    // Window/widget teardown — stop tunnel if still up.
    _vpn.disconnect();
    _scrollCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Respect status bar + nav/gesture insets so chrome is not under system trays.
    return Scaffold(
      backgroundColor: kWindowBg,
      body: SafeArea(
        // Keep system bars clear on all sides (status + nav / gesture bar).
        top: true,
        bottom: true,
        left: true,
        right: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Dark blue top banner (inside safe area)
            Container(
              color: kBannerBg,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: const Text(
                kBannerTitle,
                style: TextStyle(
                  color: kWindowFg,
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  letterSpacing: 0.5,
                ),
              ),
            ),
            // Scrolling privacy text
            SizedBox(
              height: 28,
              child: ClipRect(
                child: AnimatedBuilder(
                  animation: _scrollCtrl,
                  builder: (context, _) {
                    final w = MediaQuery.sizeOf(context).width;
                    final offset = (1 - _scrollCtrl.value) * (w + 800) - 400;
                    return Stack(
                      children: [
                        Positioned(
                          left: offset,
                          top: 6,
                          child: Text(
                            '$kScrollingPrivacyText   ·   $kScrollingPrivacyText',
                            style: const TextStyle(
                              color: kWindowFg,
                              fontSize: 13,
                              fontFamily: 'monospace',
                            ),
                            maxLines: 1,
                            softWrap: false,
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
            // CLI log
            Expanded(
              child: Container(
                color: kWindowBg,
                padding: const EdgeInsets.all(10),
                child: ListView.builder(
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
            Container(
              color: kWindowBg,
              padding: const EdgeInsets.all(8),
              child: Text(
                _status,
                style: const TextStyle(
                  color: kStatusFg,
                  fontSize: 12,
                  fontFamily: 'monospace',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
