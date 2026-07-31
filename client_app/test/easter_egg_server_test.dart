import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/easter_egg_server.dart';
import 'package:restore_privacy_client/suite_version.dart';

void main() {
  test('easter egg constants and page HTML', () {
    expect(kEasterEggPort, 18765);
    expect(kEasterEggUrlLoopback, 'http://127.0.0.1:18765/');
    expect(kEasterEggUrlLocalhost, 'http://localhost:18765/');
    expect(kEasterEggSettingsLabel, contains('18765'));

    final html = easterEggPageHtml();
    expect(html, contains('You found the loft'));
    expect(html, contains('127.0.0.1:18765'));
    expect(html, contains('localhost'));
    expect(html, contains(kSuiteDisplayVersion));
    expect(html, contains('🎈'));
    expect(html, contains('KEYGEN'));
  });

  test('EasterEggServer binds loopback and serves loft page', () async {
    // Free port for isolation (production pin remains 18765).
    final probe = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
    final port = probe.port;
    await probe.close();

    final server = EasterEggServer(port: port);
    final ok = await server.start();
    expect(ok, isTrue);
    expect(server.isRunning, isTrue);

    final client = HttpClient();
    try {
      final req = await client.getUrl(Uri.parse('http://127.0.0.1:$port/'));
      final res = await req.close();
      expect(res.statusCode, 200);
      final body = await res.transform(utf8.decoder).join();
      expect(body, contains('You found the loft'));
      expect(body, contains('$port'));

      final req2 = await client.getUrl(Uri.parse('http://127.0.0.1:$port/loft'));
      final res2 = await req2.close();
      expect(res2.statusCode, 200);
      await res2.drain<void>();

      final req3 = await client.getUrl(Uri.parse('http://127.0.0.1:$port/nope'));
      final res3 = await req3.close();
      expect(res3.statusCode, 404);
      await res3.drain<void>();

      // IPv6 loopback (::1) when the platform supports it — covers localhost.
      try {
        final req6 = await client.getUrl(Uri.parse('http://[::1]:$port/'));
        final res6 = await req6.close();
        expect(res6.statusCode, 200);
        final body6 = await res6.transform(utf8.decoder).join();
        expect(body6, contains('You found the loft'));
      } on SocketException {
        // Some CI hosts lack IPv6 loopback; IPv4 path already covered.
      }
    } finally {
      client.close(force: true);
      await server.stop();
    }
    expect(server.isRunning, isFalse);
  });

  test('page HTML is pure and includes suite branding', () {
    final html = easterEggPageHtml(
      suiteVersion: 'Restore Privacy Suite v 1.0.0',
      product: 'Restore Privacy Suite',
    );
    expect(html, contains('Restore Privacy Suite'));
    expect(html.toLowerCase(), contains('loopback'));
  });
}
