/// In-client AUDIT.md split view: left browsing stats (dynamic), right project files (manual).
///
/// Opening this surface **always** appends a visit event to the on-device
/// connection log. Nothing is uploaded.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

import 'connection_log.dart';
import 'legal_links.dart';
import 'node_ping.dart';
import 'rpt_config.dart';
import 'suite_version.dart';
import 'theme.dart';

const String kLeftPaneId = 'user_browsing_stats';
const String kRightPaneId = 'project_files';
const String kLeftPaneLabel = 'Your browsing stats';
const String kRightPaneLabel = 'Project and files';

const String kDeviceOnlyRetentionPrefix =
    'your data is only retained by your own device. ';
const String kDeviceOnlyRetentionTypewriter = 'privacy, restored.';
const String kDeviceOnlyRetentionSentence =
    '$kDeviceOnlyRetentionPrefix$kDeviceOnlyRetentionTypewriter';

const String kAuditVisitKind = 'audit_visit';
const String kAuditVisitMessage = 'AUDIT.md visit (device-only log)';

const List<String> kDefaultProjectFileNames = [
  'AUDIT.md',
  'README.md',
  'PRIVACY_POLICY.md',
  'LICENSE',
  'CREDITS.md',
  'client/VERSION',
];

const Key kAuditSplitViewKey = Key('audit_split_view');
const Key kAuditLeftPaneKey = Key('audit_left_pane');
const Key kAuditRightPaneKey = Key('audit_right_pane');
const Key kAuditRightRefreshKey = Key('audit_right_refresh');

bool paneMayAutoUpdate(String paneId) => paneId == kLeftPaneId;

/// Apply a sample to one pane. Right side ignores implicit (non-explicit) updates.
Map<String, dynamic> applyPaneRefresh(
  Map<String, dynamic> state,
  String paneId,
  Map<String, dynamic> payload, {
  bool explicit = false,
}) {
  final next = Map<String, dynamic>.from(state);
  if (paneId == kRightPaneId && !explicit) {
    return next;
  }
  if (paneId == kLeftPaneId) {
    next['left_sample'] = Map<String, dynamic>.from(payload);
    next['left_generation'] = (next['left_generation'] as int? ?? 0) + 1;
  } else if (paneId == kRightPaneId) {
    next['right_snapshot'] = Map<String, dynamic>.from(payload);
    next['right_generation'] = (next['right_generation'] as int? ?? 0) + 1;
  }
  return next;
}

/// Worst RAG among packages this device actually has installed.
String catalogOverallForInstalled(
  List<Map<String, String>> packages,
  List<String> installedPlatforms,
) {
  const order = {'Green': 0, 'Amber': 1, 'Red': 2};
  final installed = installedPlatforms
      .map((p) => p.trim().toLowerCase())
      .where((p) => p.isNotEmpty)
      .toSet();
  if (installed.isEmpty) return 'Green';
  final considered = packages.where((p) {
    return installed.contains((p['platform'] ?? '').toLowerCase());
  });
  var worst = 'Green';
  for (final row in considered) {
    final st = row['state'] ?? 'Red';
    if ((order[st] ?? 2) > (order[worst] ?? 0)) worst = st;
  }
  return worst;
}

Map<String, dynamic> buildUserBrowsingStats({
  required List<ConnectionLogEvent> events,
  PingResult? ping,
  String platform = '',
  double? now,
}) {
  var visitCount = 0;
  var lastVisit = '';
  var lastConnect = '';
  for (final e in events) {
    if (e.kind == kAuditVisitKind) {
      visitCount += 1;
      lastVisit = e.message;
    }
    if (e.kind == kLogKindConnect) lastConnect = e.message;
  }
  return {
    'pane': kLeftPaneId,
    'label': kLeftPaneLabel,
    'dynamic': true,
    'platform': platform,
    'ping_ok': ping?.ok ?? false,
    'ping_ms': ping?.rttMs,
    'ping_host': ping?.host ?? '',
    'event_count': events.length,
    'audit_visit_count': visitCount,
    'last_connect': lastConnect,
    'last_visit': lastVisit,
    'retention': kDeviceOnlyRetentionSentence,
    'device_only': true,
    'sampled_at': now ?? DateTime.now().millisecondsSinceEpoch / 1000.0,
  };
}

Map<String, dynamic> buildProjectFilesSnapshot({
  String auditText = '',
  List<String> fileNames = const [],
  String catalogOverall = '',
  String catalogVersion = '',
}) {
  return {
    'pane': kRightPaneId,
    'label': kRightPaneLabel,
    'dynamic': false,
    'manual_refresh_only': true,
    'catalog_version': catalogVersion,
    'catalog_overall': catalogOverall,
    'audit_excerpt': auditText.length > 4000 ? auditText.substring(0, 4000) : auditText,
    'files': List<String>.from(fileNames),
  };
}

/// Fetch the public project AUDIT.md (no user stats). Used on first open and
/// every explicit right-pane refresh so the project half can change.
Future<String> fetchPublicAuditMarkdown({
  Uri? uri,
  Future<String> Function(Uri url)? getText,
}) async {
  final target = uri ?? Uri.parse('${LegalDocLink.statusOrigin}/AUDIT.md');
  if (getText != null) {
    return getText(target);
  }
  final client = HttpClient();
  try {
    final req = await client.getUrl(target);
    req.headers.set(HttpHeaders.userAgentHeader, 'rpt-client-audit-split/1');
    final resp = await req.close();
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      return '';
    }
    return await resp.transform(utf8.decoder).join();
  } catch (_) {
    return '';
  } finally {
    client.close(force: true);
  }
}

/// Load the right-pane project snapshot (AUDIT.md + file names).
Future<Map<String, dynamic>> loadProjectAuditSnapshot({
  String platform = '',
  String catalogVersion = kSuiteVersion,
  Future<String> Function()? fetchAuditText,
  List<String>? fileNames,
}) async {
  final text = fetchAuditText != null
      ? await fetchAuditText()
      : await fetchPublicAuditMarkdown();
  return buildProjectFilesSnapshot(
    auditText: text,
    fileNames: fileNames ?? kDefaultProjectFileNames,
    catalogVersion: catalogVersion,
    catalogOverall: catalogOverallForInstalled(
      [
        {'platform': platform, 'state': 'Green'},
      ],
      platform.isEmpty ? const <String>[] : [platform],
    ),
  );
}

/// Imperative: record this AUDIT visit on the **device** connection log.
Future<ConnectionLogEvent> appendAuditVisitToDeviceLog(
  ConnectionLog log, {
  String platform = '',
  double? pingMs,
}) {
  final detail = <String, String>{
    'surface': 'AUDIT.md',
    'device_only': 'true',
    'uploaded': 'false',
  };
  if (platform.isNotEmpty) detail['platform'] = platform;
  if (pingMs != null) detail['ping_ms'] = pingMs.toString();
  return log.appendEvent(kAuditVisitKind, kAuditVisitMessage, detail: detail);
}

/// In-client two-pane AUDIT surface (opened instead of the public AUDIT.md URL).
class AuditSplitView extends StatefulWidget {
  const AuditSplitView({
    super.key,
    required this.connectionLog,
    this.platformLabel = 'flutter',
    this.multihopOn = false,
    this.auditText = '',
    this.fileNames = kDefaultProjectFileNames,
    this.leftPoll,
    this.pingProbe,
    this.projectSnapshotLoader,
    this.fetchAuditText,
  });

  final ConnectionLog connectionLog;
  final String platformLabel;
  final bool multihopOn;
  final String auditText;
  final List<String> fileNames;

  /// Injected ticker for tests (left-pane dynamic refresh).
  final Stream<void>? leftPoll;
  final Future<PingResult> Function(String host)? pingProbe;

  /// Right pane: called on first open and every explicit refresh.
  final Future<Map<String, dynamic>> Function()? projectSnapshotLoader;
  final Future<String> Function()? fetchAuditText;

  @override
  State<AuditSplitView> createState() => _AuditSplitViewState();
}

class _AuditSplitViewState extends State<AuditSplitView> {
  Map<String, dynamic> _state = {
    'left_sample': <String, dynamic>{},
    'right_snapshot': <String, dynamic>{},
    'left_generation': 0,
    'right_generation': 0,
  };
  StreamSubscription<void>? _poll;
  Timer? _timer;
  bool _typed = false;

  @override
  void initState() {
    super.initState();
    _openVisit();
    final poll = widget.leftPoll;
    if (poll != null) {
      _poll = poll.listen((_) => _refreshLeft());
    } else {
      _timer = Timer.periodic(const Duration(seconds: 8), (_) => _refreshLeft());
    }
    Future<void>.delayed(const Duration(milliseconds: 80), () {
      if (mounted) setState(() => _typed = true);
    });
  }

  @override
  void dispose() {
    _poll?.cancel();
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _openVisit() async {
    final ping = await _probe();
    await appendAuditVisitToDeviceLog(
      widget.connectionLog,
      platform: widget.platformLabel,
      pingMs: ping.rttMs,
    );
    await _refreshLeft(ping: ping);
    await _refreshRight();
  }

  Future<PingResult> _probe() async {
    final fn = widget.pingProbe;
    if (fn != null) return fn(RptConfig.entryHost);
    try {
      final r = await measureSettingsPings(
        multihopOn: widget.multihopOn,
        probe: widget.pingProbe,
      );
      return r.entry;
    } catch (_) {
      return const PingResult(host: '', port: kStatusTcpPort, ok: false, error: 'probe_failed');
    }
  }

  Future<void> _refreshLeft({PingResult? ping}) async {
    final p = ping ?? await _probe();
    final events = await widget.connectionLog.readEvents(limit: 40);
    final sample = buildUserBrowsingStats(
      events: events,
      ping: p,
      platform: widget.platformLabel,
    );
    if (!mounted) return;
    setState(() {
      _state = applyPaneRefresh(_state, kLeftPaneId, sample);
    });
  }

  Future<void> _refreshRight() async {
    final loader = widget.projectSnapshotLoader;
    final Map<String, dynamic> snap;
    if (loader != null) {
      snap = await loader();
    } else {
      snap = await loadProjectAuditSnapshot(
        platform: widget.platformLabel,
        catalogVersion: kSuiteVersion,
        fetchAuditText: widget.fetchAuditText ??
            (widget.auditText.isEmpty ? null : () async => widget.auditText),
        fileNames: widget.fileNames,
      );
    }
    if (!mounted) return;
    setState(() {
      _state = applyPaneRefresh(_state, kRightPaneId, snap, explicit: true);
    });
  }

  @override
  Widget build(BuildContext context) {
    final left = Map<String, dynamic>.from(_state['left_sample'] as Map? ?? {});
    final right = Map<String, dynamic>.from(_state['right_snapshot'] as Map? ?? {});
    final pingMs = left['ping_ms'];
    final files = (right['files'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[];
    return Scaffold(
      key: kAuditSplitViewKey,
      backgroundColor: suiteChromeBgOf(context),
      appBar: AppBar(
        title: const Text('Most recent audit'),
        backgroundColor: suitePanelBgOf(context),
      ),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: Container(
              key: kAuditLeftPaneKey,
              padding: const EdgeInsets.all(16),
              color: suitePanelBgOf(context),
              child: ListView(
                children: [
                  Text(
                    kLeftPaneLabel,
                    style: TextStyle(
                      color: suitePrimaryOf(context),
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'dedicated ping: ${pingMs == null ? 'n/a' : '$pingMs ms'}',
                    style: TextStyle(color: suiteTextOf(context)),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'visits on this device: ${left['audit_visit_count'] ?? 0}',
                    style: TextStyle(color: suiteTextOf(context)),
                  ),
                  const SizedBox(height: 16),
                  Text.rich(
                    TextSpan(
                      style: TextStyle(color: suiteTextOf(context), fontSize: 14),
                      children: [
                        const TextSpan(text: kDeviceOnlyRetentionPrefix),
                        TextSpan(
                          text: _typed ? kDeviceOnlyRetentionTypewriter : '',
                          style: TextStyle(
                            color: suitePrimaryOf(context),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: Container(
              key: kAuditRightPaneKey,
              padding: const EdgeInsets.all(16),
              child: ListView(
                children: [
                  Text(
                    kRightPaneLabel,
                    style: TextStyle(
                      color: suitePrimaryOf(context),
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'catalog ${right['catalog_version'] ?? ''} overall ${right['catalog_overall'] ?? ''}',
                    style: TextStyle(color: suiteTextMutedOf(context)),
                  ),
                  const SizedBox(height: 8),
                  ...files.map(
                    (n) => Text(n, style: TextStyle(color: suiteTextOf(context))),
                  ),
                  const SizedBox(height: 12),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton(
                      key: kAuditRightRefreshKey,
                      onPressed: _refreshRight,
                      child: const Text('Refresh project files'),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    (right['audit_excerpt'] ?? '').toString(),
                    style: TextStyle(
                      color: suiteTextMutedOf(context),
                      fontFamily: 'monospace',
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
