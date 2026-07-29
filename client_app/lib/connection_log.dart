/// Local-only connection log (device storage, user-exportable).
///
/// Events are not uploaded by the client. Export produces plain text the user
/// can save or email to support themselves. Diagnostics (version / platform /
/// outcome) are for that manual handoff only.
library;

import 'dart:io' show Platform;

const String kLogKindConnect = 'connect';
const String kLogKindDisconnect = 'disconnect';
const String kLogKindSession = 'session';
const String kLogKindError = 'error';
const String kLogKindInfo = 'info';
const String kLogKindLeakTest = 'leak_test';

const int kDefaultMaxEvents = 500;

class ConnectionLogEvent {
  final double ts;
  final String kind;
  final String message;
  final Map<String, String> detail;

  const ConnectionLogEvent({
    required this.ts,
    required this.kind,
    required this.message,
    this.detail = const {},
  });

  Map<String, dynamic> toJson() {
    final m = <String, dynamic>{
      'ts': ts,
      'kind': kind,
      'message': message,
    };
    if (detail.isNotEmpty) {
      m['detail'] = detail;
    }
    return m;
  }

  factory ConnectionLogEvent.fromJson(Map<String, dynamic> data) {
    final raw = data['detail'];
    final d = <String, String>{};
    if (raw is Map) {
      raw.forEach((k, v) {
        if (v != null) d[k.toString()] = v.toString();
      });
    }
    return ConnectionLogEvent(
      ts: (data['ts'] is num) ? (data['ts'] as num).toDouble() : 0.0,
      kind: data['kind']?.toString() ?? kLogKindInfo,
      message: data['message']?.toString() ?? '',
      detail: d,
    );
  }

  String formatLine() {
    final dt = DateTime.fromMillisecondsSinceEpoch((ts * 1000).round(), isUtc: false);
    final stamp =
        '${dt.year.toString().padLeft(4, '0')}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}:${dt.second.toString().padLeft(2, '0')}';
    var base = '[$stamp] $kind: $message';
    if (detail.isEmpty) return base;
    final parts = <String>[];
    for (final key in ['outcome', 'error', 'error_code', 'residual_host', 'session_vpn_ip', 'residual_capture']) {
      if (detail.containsKey(key)) parts.add('$key=${detail[key]}');
    }
    detail.forEach((k, v) {
      if (['product', 'client_version', 'platform', 'os_name'].contains(k)) return;
      if (parts.any((p) => p.startsWith('$k='))) return;
      parts.add('$k=$v');
    });
    if (parts.isEmpty) return base;
    return '$base | ${parts.join(' ')}';
  }
}

/// Injectable store so unit tests drive the real [ConnectionLog] path.
abstract class ConnectionLogBackend {
  Future<List<String>> readLines();
  Future<void> writeLines(List<String> lines);
}

/// In-memory backend (tests + ephemeral sessions).
class MemoryConnectionLogBackend implements ConnectionLogBackend {
  MemoryConnectionLogBackend([List<String>? seed]) : _lines = List.of(seed ?? const []);

  final List<String> _lines;

  @override
  Future<List<String>> readLines() async => List.of(_lines);

  @override
  Future<void> writeLines(List<String> lines) async {
    _lines
      ..clear()
      ..addAll(lines);
  }
}

/// Support diagnostic snapshot (local only — no network).
Map<String, String> buildSupportDiagnostics({
  String clientVersion = 'unknown',
  String platform = 'flutter',
  Map<String, String>? extra,
}) {
  final snap = <String, String>{
    'product': 'Restore Privacy',
    'client_version': clientVersion.isEmpty ? 'unknown' : clientVersion,
    'platform': platform.isEmpty ? 'flutter' : platform,
  };
  if (extra != null) {
    snap.addAll(extra);
  }
  return snap;
}

/// Failure line for local connection-log export (support handoff).
///
/// Prefer residual-honest UI / native status over a bare `Connect failed` token
/// so exports match what the user saw and are actionable for support.
String connectionLogConnectFailureMessage(
  String? uiOrNativeStatus, {
  String fallback = 'Connect failed',
}) {
  final s = (uiOrNativeStatus ?? '').trim();
  if (s.isEmpty) return fallback;
  final low = s.toLowerCase();
  // Connecting progress is not a terminal failure detail by itself
  if (low.startsWith('connecting') || low.contains('still connecting')) {
    return '$fallback — tunnel did not complete (last status: $s)';
  }
  // Already a bare failure with no extra detail
  if (low == 'connect failed' || low == fallback.toLowerCase()) {
    return s;
  }
  // Prefer residual-honest status as the error body (do not prefix if already detailed)
  if (low.contains('connect failed')) return s;
  return s;
}

/// Platform label for connection-log / support export (macOS vs iOS vs other).
String connectionLogPlatformLabel() {
  if (Platform.isMacOS) return 'macos';
  if (Platform.isIOS) return 'ios';
  if (Platform.isAndroid) return 'android';
  return 'flutter';
}

class ConnectionLog {
  ConnectionLog(
    this.backend, {
    this.maxEvents = kDefaultMaxEvents,
    this.clientVersion = 'unknown',
    this.platformLabel = 'flutter',
  });

  final ConnectionLogBackend backend;
  final int maxEvents;
  final String clientVersion;
  final String platformLabel;

  Future<ConnectionLogEvent> appendEvent(
    String kind,
    String message, {
    double? ts,
    Map<String, String>? detail,
    bool includeDiagnostics = true,
  }) async {
    final merged = <String, String>{};
    if (includeDiagnostics) {
      merged.addAll(buildSupportDiagnostics(
        clientVersion: clientVersion,
        platform: platformLabel,
      ));
    }
    if (detail != null) merged.addAll(detail);
    final event = ConnectionLogEvent(
      ts: ts ?? DateTime.now().millisecondsSinceEpoch / 1000.0,
      kind: kind.isEmpty ? kLogKindInfo : kind,
      message: message.trim().isEmpty ? '(empty)' : message.trim(),
      detail: merged,
    );
    final lines = await backend.readLines();
    lines.add(_encodeLine(event));
    final trimmed = maxEvents > 0 && lines.length > maxEvents
        ? lines.sublist(lines.length - maxEvents)
        : lines;
    await backend.writeLines(trimmed);
    return event;
  }

  Future<List<ConnectionLogEvent>> readEvents({int? limit}) async {
    final lines = await backend.readLines();
    final events = <ConnectionLogEvent>[];
    for (final line in lines) {
      final e = _decodeLine(line);
      if (e != null) events.add(e);
    }
    if (limit != null && limit >= 0 && events.length > limit) {
      return events.sublist(events.length - limit);
    }
    return events;
  }

  /// Plain-text export body (local only — not uploaded by the client).
  Future<String> formatExport({int? limit}) async {
    final events = await readEvents(limit: limit);
    final snap = buildSupportDiagnostics(
      clientVersion: clientVersion,
      platform: platformLabel,
    );
    final buf = StringBuffer()
      ..writeln('# Restore Privacy connection log (local only)')
      ..writeln('# Not uploaded by the client. User-exported file for support handoff.')
      ..writeln('# Support: email this file to support yourself (no automatic upload).')
      ..writeln('# product=${snap['product']} client_version=${snap['client_version']}')
      ..writeln('# platform=${snap['platform']}')
      ..writeln('# --- events ---');
    for (final e in events) {
      buf.writeln(e.formatLine());
    }
    return buf.toString();
  }

  Future<void> clear() async => backend.writeLines([]);

  String _encodeLine(ConnectionLogEvent e) {
    // Minimal JSON without extra deps.
    final msg = e.message
        .replaceAll('\\', '\\\\')
        .replaceAll('"', '\\"')
        .replaceAll('\n', '\\n');
    final parts = <String>[
      '"ts":${e.ts}',
      '"kind":"${e.kind}"',
      '"message":"$msg"',
    ];
    if (e.detail.isNotEmpty) {
      final dparts = e.detail.entries.map((en) {
        final k = en.key.replaceAll('\\', '\\\\').replaceAll('"', '\\"');
        final v = en.value.replaceAll('\\', '\\\\').replaceAll('"', '\\"');
        return '"$k":"$v"';
      }).join(',');
      parts.add('"detail":{$dparts}');
    }
    return '{${parts.join(',')}}';
  }

  ConnectionLogEvent? _decodeLine(String line) {
    final t = line.trim();
    if (t.isEmpty) return null;
    try {
      // Tiny parser for our fixed shape.
      final tsMatch = RegExp(r'"ts"\s*:\s*([0-9.]+)').firstMatch(t);
      final kindMatch = RegExp(r'"kind"\s*:\s*"([^"]*)"').firstMatch(t);
      final msgMatch = RegExp(r'"message"\s*:\s*"((?:\\.|[^"\\])*)"').firstMatch(t);
      if (tsMatch == null || kindMatch == null || msgMatch == null) return null;
      final msg = msgMatch.group(1)!
          .replaceAll('\\n', '\n')
          .replaceAll('\\"', '"')
          .replaceAll('\\\\', '\\');
      final detail = <String, String>{};
      final detailBlock = RegExp(r'"detail"\s*:\s*\{([^}]*)\}').firstMatch(t);
      if (detailBlock != null) {
        final body = detailBlock.group(1)!;
        for (final m in RegExp(r'"([^"]+)"\s*:\s*"((?:\\.|[^"\\])*)"').allMatches(body)) {
          detail[m.group(1)!] = m
              .group(2)!
              .replaceAll('\\n', '\n')
              .replaceAll('\\"', '"')
              .replaceAll('\\\\', '\\');
        }
      }
      return ConnectionLogEvent(
        ts: double.parse(tsMatch.group(1)!),
        kind: kindMatch.group(1)!,
        message: msg,
        detail: detail,
      );
    } catch (_) {
      return null;
    }
  }
}
