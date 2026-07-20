/// Local-only connection log (device storage, user-exportable).
///
/// Events are not uploaded by the client. Export produces plain text the user
/// can save or share themselves.
library;

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

  const ConnectionLogEvent({
    required this.ts,
    required this.kind,
    required this.message,
  });

  Map<String, dynamic> toJson() => {
        'ts': ts,
        'kind': kind,
        'message': message,
      };

  factory ConnectionLogEvent.fromJson(Map<String, dynamic> data) {
    return ConnectionLogEvent(
      ts: (data['ts'] is num) ? (data['ts'] as num).toDouble() : 0.0,
      kind: data['kind']?.toString() ?? kLogKindInfo,
      message: data['message']?.toString() ?? '',
    );
  }

  String formatLine() {
    final dt = DateTime.fromMillisecondsSinceEpoch((ts * 1000).round(), isUtc: false);
    final stamp =
        '${dt.year.toString().padLeft(4, '0')}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}:${dt.second.toString().padLeft(2, '0')}';
    return '[$stamp] $kind: $message';
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

class ConnectionLog {
  ConnectionLog(this.backend, {this.maxEvents = kDefaultMaxEvents});

  final ConnectionLogBackend backend;
  final int maxEvents;

  Future<ConnectionLogEvent> appendEvent(
    String kind,
    String message, {
    double? ts,
  }) async {
    final event = ConnectionLogEvent(
      ts: ts ?? DateTime.now().millisecondsSinceEpoch / 1000.0,
      kind: kind.isEmpty ? kLogKindInfo : kind,
      message: message.trim().isEmpty ? '(empty)' : message.trim(),
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
    final buf = StringBuffer()
      ..writeln('# Restore Privacy connection log (local only)')
      ..writeln('# Not uploaded by the client. User-exported file.');
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
    return '{"ts":${e.ts},"kind":"${e.kind}","message":"$msg"}';
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
      return ConnectionLogEvent(
        ts: double.parse(tsMatch.group(1)!),
        kind: kindMatch.group(1)!,
        message: msg,
      );
    } catch (_) {
      return null;
    }
  }
}
