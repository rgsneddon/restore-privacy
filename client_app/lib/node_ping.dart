/// Best-effort device→node RTT probes for Settings ping statistics (Dart).
///
/// Mirrors `client/node_ping.py` intent: measure approximate latency to product
/// **entry** (IS / DE; default Germany) and multi-hop **exit** (Germany).
/// Uses TCP connect RTT to the node status port (8080) as a portable probe —
/// residual HELLO is crypto-gated and not used here. Results are **probe RTT**,
/// not a browser SLA.
library;

import 'dart:async';
import 'dart:io';

import 'rpt_config.dart';

const int kStatusTcpPort = 8080;
const Duration kDefaultProbeTimeout = Duration(milliseconds: 1500);

class PingResult {
  final String host;
  final int port;
  final bool ok;
  final double? rttMs;
  final String method;
  final String error;

  const PingResult({
    required this.host,
    required this.port,
    required this.ok,
    this.rttMs,
    this.method = 'none',
    this.error = '',
  });

  String display() {
    if (ok && rttMs != null) return '${rttMs!.round()} ms';
    if (error.isNotEmpty) {
      final short = error.length > 40 ? error.substring(0, 40) : error;
      return 'n/a ($short)';
    }
    return 'n/a';
  }
}

/// TCP connect RTT to [host]:[port] (default status port 8080).
Future<PingResult> probeTcpRttMs(
  String host, {
  int port = kStatusTcpPort,
  Duration timeout = kDefaultProbeTimeout,
}) async {
  final h = host.trim();
  if (h.isEmpty) {
    return const PingResult(
      host: '',
      port: kStatusTcpPort,
      ok: false,
      method: 'none',
      error: 'no_host',
    );
  }
  final sw = Stopwatch()..start();
  try {
    final socket = await Socket.connect(h, port, timeout: timeout);
    final rtt = sw.elapsedMicroseconds / 1000.0;
    await socket.close();
    return PingResult(
      host: h,
      port: port,
      ok: true,
      rttMs: rtt,
      method: 'tcp',
    );
  } on Object catch (e) {
    return PingResult(
      host: h,
      port: port,
      ok: false,
      method: 'tcp',
      error: e.toString(),
    );
  }
}

/// Entry + optional exit probes for Settings UI.
Future<({PingResult entry, PingResult? exit})> measureSettingsPings({
  required bool multihopOn,
  Future<PingResult> Function(String host)? probe,
}) async {
  final p = probe ?? (h) => probeTcpRttMs(h);
  final entry = await p(RptConfig.entryHost);
  PingResult? exit;
  if (multihopOn) {
    exit = await p(RptConfig.exitHost);
  }
  return (entry: entry, exit: exit);
}
