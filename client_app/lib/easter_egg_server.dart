import 'dart:async';
import 'dart:io';

import 'suite_version.dart';

/// Local loft easter egg — only on loopback port [kEasterEggPort].
///
/// Browse `http://127.0.0.1:18765/` or `http://localhost:18765/` while the
/// Suite app is running. Not advertised on the public web; Settings holds a
/// quiet link.
const int kEasterEggPort = 18765;

/// Canonical loopback URLs (both resolve to the same listener).
const String kEasterEggUrlLoopback = 'http://127.0.0.1:$kEasterEggPort/';
const String kEasterEggUrlLocalhost = 'http://localhost:$kEasterEggPort/';

/// Subtle Settings label (not a marketing banner).
const String kEasterEggSettingsLabel = 'Local loft · 18765';

/// Served HTML for the loft page (pure; used by tests + the live server).
String easterEggPageHtml({
  String suiteVersion = kSuiteDisplayVersion,
  String product = kSuiteProductName,
  int port = kEasterEggPort,
}) {
  final title = '$product — loft';
  return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>$title</title>
<style>
  :root { color-scheme: dark; }
  body {
    margin: 0; min-height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center; text-align: center;
    font-family: "Segoe UI", system-ui, sans-serif;
    background: radial-gradient(ellipse at 50% 20%, #1a4a7a 0%, #0a1628 55%, #050b14 100%);
    color: #e8eef5; padding: 2rem;
  }
  .balloon {
    font-size: 4.5rem; line-height: 1; margin-bottom: 0.4rem;
    animation: float 3.2s ease-in-out infinite;
    filter: drop-shadow(0 8px 18px rgba(0,0,0,0.35));
  }
  @keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-12px); }
  }
  h1 {
    font-size: clamp(1.35rem, 4vw, 1.85rem); letter-spacing: 0.08em;
    text-transform: uppercase; margin: 0.35rem 0 0.5rem; color: #fff;
  }
  .tag {
    display: inline-block; margin: 0.35rem 0 1rem; padding: 0.25rem 0.75rem;
    border-radius: 999px; font-size: 0.78rem; font-weight: 700;
    background: #aed0ea; color: #0a1628; letter-spacing: 0.04em;
  }
  p { max-width: 28rem; line-height: 1.5; color: #aed0ea; margin: 0.45rem auto; }
  .quiet { font-size: 0.85rem; opacity: 0.85; color: #dbeafe; }
  code {
    font-family: ui-monospace, Consolas, monospace; font-size: 0.9em;
    background: rgba(0,0,0,0.28); padding: 0.12rem 0.4rem; border-radius: 6px;
  }
  a { color: #93c5fd; }
</style>
</head>
<body>
  <div class="balloon" aria-hidden="true">🎈</div>
  <h1>You found the loft</h1>
  <span class="tag">$suiteVersion</span>
  <p>
    Loopback only — nothing here phones home. Residual privacy, three tabs,
    and a balloon for the curious.
  </p>
  <p class="quiet">
    Listening on <code>127.0.0.1:$port</code>
    and <code>localhost:$port</code> while the app runs.
  </p>
  <p class="quiet">Tabs: VPN · % · EVOLVE — KEYGEN still guards Connect.</p>
</body>
</html>
''';
}

/// Binds loopback [HttpServer]s on [kEasterEggPort] and serves [easterEggPageHtml].
///
/// Listens on both IPv4 (`127.0.0.1`) and IPv6 (`::1`) so browsers that resolve
/// `localhost` to either family still hit the loft.
class EasterEggServer {
  EasterEggServer({this.port = kEasterEggPort});

  final int port;
  HttpServer? _v4;
  HttpServer? _v6;

  bool get isRunning => _v4 != null || _v6 != null;

  /// Start listening on loopback only. No-op if already running.
  ///
  /// Returns true if at least one family is listening after the call.
  Future<bool> start() async {
    if (isRunning) return true;
    var any = false;
    any = await _tryBind(InternetAddress.loopbackIPv4, (s) => _v4 = s) || any;
    any = await _tryBind(InternetAddress.loopbackIPv6, (s) => _v6 = s) || any;
    return any;
  }

  Future<bool> _tryBind(
    InternetAddress address,
    void Function(HttpServer) store,
  ) async {
    try {
      final server = await HttpServer.bind(address, port);
      store(server);
      unawaited(_serve(server));
      return true;
    } on SocketException {
      // Port busy, family unsupported, or bind denied — that family stays dark.
      return false;
    } catch (_) {
      return false;
    }
  }

  Future<void> stop() async {
    final a = _v4;
    final b = _v6;
    _v4 = null;
    _v6 = null;
    await a?.close(force: true);
    await b?.close(force: true);
  }

  Future<void> _serve(HttpServer server) async {
    await for (final req in server) {
      try {
        await _handle(req);
      } catch (_) {
        try {
          req.response.statusCode = HttpStatus.internalServerError;
          await req.response.close();
        } catch (_) {}
      }
    }
  }

  Future<void> _handle(HttpRequest req) async {
    final path = req.uri.path;
    if (req.method != 'GET' && req.method != 'HEAD') {
      req.response.statusCode = HttpStatus.methodNotAllowed;
      await req.response.close();
      return;
    }
    if (path != '/' && path != '/index.html' && path != '/loft') {
      req.response.statusCode = HttpStatus.notFound;
      req.response.headers.contentType = ContentType.html;
      req.response.write(
        '<!DOCTYPE html><html><body><p>Nothing upstairs. Try <a href="/">/</a>.</p></body></html>',
      );
      await req.response.close();
      return;
    }
    final html = easterEggPageHtml(port: port);
    req.response.statusCode = HttpStatus.ok;
    req.response.headers.contentType = ContentType.html;
    req.response.headers.set('Cache-Control', 'no-store');
    if (req.method == 'GET') {
      req.response.write(html);
    }
    await req.response.close();
  }
}

/// Process-wide loft (started from [main]).
final EasterEggServer easterEggServer = EasterEggServer();

/// Fire-and-forget start for app launch.
void startEasterEggServer() {
  unawaited(easterEggServer.start());
}
