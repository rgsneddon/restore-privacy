import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'theme.dart';

/// Live Perccent Network Explorer URL (Render) embedded in the Suite wallet tab.
const String kSuitePercBlockExplorerUrl =
    'https://evolve-perc-internet.onrender.com';

/// Compact iframe-style embed of the community block explorer for the % tab.
///
/// Uses [WebViewController] on mobile/desktop platforms that support it;
/// falls back to a launch control when the webview cannot initialise (tests).
class SuitePercExplorerPanel extends StatefulWidget {
  const SuitePercExplorerPanel({
    super.key,
    this.explorerUrl = kSuitePercBlockExplorerUrl,
    this.height = 280,
    this.controller,
  });

  final String explorerUrl;
  final double height;

  /// Injectable controller (tests / hot-swap). When null, a production
  /// controller is created that loads [explorerUrl].
  final WebViewController? controller;

  @override
  State<SuitePercExplorerPanel> createState() => _SuitePercExplorerPanelState();
}

class _SuitePercExplorerPanelState extends State<SuitePercExplorerPanel> {
  WebViewController? _controller;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _initController();
  }

  void _initController() {
    if (widget.controller != null) {
      _controller = widget.controller;
      _loading = false;
      return;
    }
    try {
      final c = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setBackgroundColor(const Color(0xFF0B0D14))
        ..setNavigationDelegate(
          NavigationDelegate(
            onPageFinished: (_) {
              if (mounted) setState(() => _loading = false);
            },
            onWebResourceError: (err) {
              if (mounted) {
                setState(() {
                  _error = err.description;
                  _loading = false;
                });
              }
            },
          ),
        )
        ..loadRequest(Uri.parse(_normalizedUrl(widget.explorerUrl)));
      _controller = c;
    } catch (e) {
      _error = e;
      _loading = false;
    }
  }

  static String _normalizedUrl(String raw) {
    final t = raw.trim();
    if (t.isEmpty) return kSuitePercBlockExplorerUrl;
    return t.endsWith('/') ? t : '$t/';
  }

  Future<void> _openFull() async {
    final uri = Uri.parse(_normalizedUrl(widget.explorerUrl));
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: kChromeBg,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    'Perc wallet · block explorer',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.6,
                      color: kTextMuted,
                    ),
                  ),
                ),
                TextButton(
                  key: const Key('suite_perc_explorer_open_full'),
                  onPressed: _openFull,
                  child: const Text('Open full'),
                ),
              ],
            ),
          ),
          SizedBox(
            height: widget.height,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: const Color(0xFF0B0D14),
                border: Border.all(color: const Color(0x5939FF6A)),
              ),
              child: _buildBody(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_error != null && _controller == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Block explorer embed unavailable on this surface.',
                textAlign: TextAlign.center,
                style: TextStyle(color: kTextMuted),
              ),
              const SizedBox(height: 8),
              FilledButton(
                key: const Key('suite_perc_explorer_fallback_open'),
                onPressed: _openFull,
                child: const Text('Open evolve-perc-internet explorer'),
              ),
            ],
          ),
        ),
      );
    }
    final c = _controller;
    if (c == null) {
      return const Center(child: CircularProgressIndicator(color: kPrimary));
    }
    return Stack(
      fit: StackFit.expand,
      children: [
        WebViewWidget(
          key: const Key('suite_perc_explorer_webview'),
          controller: c,
        ),
        if (_loading)
          const Center(child: CircularProgressIndicator(color: kPrimary)),
      ],
    );
  }
}
