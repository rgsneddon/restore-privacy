import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/node_ping.dart';
import 'package:restore_privacy_client/rpt_config.dart';

void main() {
  test('measureSettingsPings entry only when multihop off', () async {
    final r = await measureSettingsPings(
      multihopOn: false,
      probe: (host) async => PingResult(
        host: host,
        port: kStatusTcpPort,
        ok: true,
        rttMs: 12.0,
        method: 'tcp',
      ),
    );
    expect(r.entry.ok, isTrue);
    expect(r.entry.host, RptConfig.entryHost);
    expect(r.exit, isNull);
  });

  test('measureSettingsPings includes exit when multihop on', () async {
    // Product monopin: default entry may equal exit (both DE). Probe must still
    // return an exit sample when multihop is on; RTTs match when hosts match.
    final r = await measureSettingsPings(
      multihopOn: true,
      probe: (host) async => PingResult(
        host: host,
        port: kStatusTcpPort,
        ok: true,
        rttMs: host == RptConfig.exitHost ? 40.0 : 10.0,
        method: 'tcp',
      ),
    );
    expect(r.entry.host, RptConfig.entryHost);
    expect(r.exit, isNotNull);
    expect(r.exit!.host, RptConfig.exitHost);
    if (RptConfig.entryHost == RptConfig.exitHost) {
      expect(r.entry.rttMs, 40.0);
      expect(r.exit!.rttMs, 40.0);
    } else {
      expect(r.entry.rttMs, 10.0);
      expect(r.exit!.rttMs, 40.0);
    }
  });

  test('PingResult.display formats ok and errors', () {
    expect(
      const PingResult(
        host: 'a',
        port: 1,
        ok: true,
        rttMs: 15.4,
        method: 'tcp',
      ).display(),
      '15 ms',
    );
    expect(
      const PingResult(
        host: 'a',
        port: 1,
        ok: false,
        method: 'tcp',
        error: 'timeout',
      ).display(),
      'n/a (timeout)',
    );
  });
}
