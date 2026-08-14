import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/audit_split_view.dart';
import 'package:restore_privacy_client/connection_log.dart';
import 'package:restore_privacy_client/legal_links.dart';
import 'package:restore_privacy_client/node_ping.dart';

void main() {
  test('pane policy: left auto-updates; right only on explicit refresh', () {
    expect(paneMayAutoUpdate(kLeftPaneId), isTrue);
    expect(paneMayAutoUpdate(kRightPaneId), isFalse);
    var state = <String, dynamic>{
      'left_generation': 0,
      'right_generation': 0,
    };
    state = applyPaneRefresh(
      state,
      kRightPaneId,
      {'stamp': 'a'},
      explicit: true,
    );
    state = applyPaneRefresh(state, kLeftPaneId, {'ping_ms': 12, 'stamp': 'l1'});
    expect(state['left_generation'], 1);
    expect((state['right_snapshot'] as Map)['stamp'], 'a');
    state = applyPaneRefresh(state, kLeftPaneId, {'ping_ms': 18, 'stamp': 'l2'});
    expect((state['left_sample'] as Map)['stamp'], 'l2');
    expect((state['right_snapshot'] as Map)['stamp'], 'a');
    state = applyPaneRefresh(state, kRightPaneId, {'stamp': 'b'});
    expect((state['right_snapshot'] as Map)['stamp'], 'a');
    state = applyPaneRefresh(
      state,
      kRightPaneId,
      {'stamp': 'b'},
      explicit: true,
    );
    expect((state['right_snapshot'] as Map)['stamp'], 'b');
    expect(state['right_generation'], 2);
  });

  test('connected visit shows ping/session and writes those stats to the device log',
      () async {
    final log = ConnectionLog(MemoryConnectionLogBackend());
    final ping = const PingResult(
      host: 'de',
      port: kStatusTcpPort,
      ok: true,
      rttMs: 41,
    );
    final out = await recordConnectedAuditVisit(
      log,
      residualConnected: true,
      ping: ping,
      platform: 'macos',
    );
    expect(out['visible_session'], kConnectedSessionLine);
    expect(out['device_only'], isTrue);
    final ev = out['event'] as ConnectionLogEvent;
    expect(ev.kind, kAuditVisitKind);
    expect(ev.detail['residual_connected'], 'true');
    expect(ev.detail['ping_ms'], '41.0');
    final export = await log.formatExport();
    expect(export.toLowerCase(), contains('local only'));
    expect(export, contains('AUDIT.md visit'));
    expect(export, contains('residual_connected=true'));
  });

  test('AUDIT visit is appended to the device connection log', () async {
    final log = ConnectionLog(MemoryConnectionLogBackend());
    final ev = await appendAuditVisitToDeviceLog(
      log,
      platform: 'macos',
      pingMs: 21,
    );
    expect(ev.kind, kAuditVisitKind);
    expect(ev.message, kAuditVisitMessage);
    expect(ev.detail['device_only'], 'true');
    expect(ev.detail['uploaded'], 'false');
    final events = await log.readEvents();
    expect(events, hasLength(1));
    expect(events.first.kind, kAuditVisitKind);
    final export = await log.formatExport();
    expect(export.toLowerCase(), contains('local only'));
    expect(export, contains('AUDIT.md visit'));
    expect(export.toLowerCase(), contains('not uploaded'));
  });

  test('single installed platform does not inherit other-OS Red', () {
    final packages = [
      {'platform': 'windows', 'state': 'Red'},
      {'platform': 'macos', 'state': 'Green'},
      {'platform': 'linux', 'state': 'Red'},
    ];
    expect(catalogOverallForInstalled(packages, ['macos']), 'Green');
    expect(catalogOverallForInstalled(packages, ['windows']), 'Red');
    expect(catalogOverallForInstalled(packages, []), 'Green');
  });

  test('legal AUDIT link is intercepted as in-client view', () {
    expect(isAuditDoc(kLegalDocLinks.first), isTrue);
    expect(isAuditUrl(kLegalDocLinks.first.url), isTrue);
    expect(isAuditDoc(kLegalDocLinks[1]), isFalse);
  });

  testWidgets('opening the split view records a visit on the device log',
      (tester) async {
    final log = ConnectionLog(MemoryConnectionLogBackend());
    await tester.pumpWidget(
      MaterialApp(
        home: AuditSplitView(
          connectionLog: log,
          platformLabel: 'macos',
          leftPoll: const Stream<void>.empty(),
          fetchAuditText: () async => '# Restore Privacy — Code & Policy Audit\n',
          pingProbe: (host) async => PingResult(
            host: host,
            port: kStatusTcpPort,
            ok: true,
            rttMs: 15,
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 120));
    final events = await log.readEvents();
    expect(events, isNotEmpty);
    expect(events.first.kind, kAuditVisitKind);
    expect(find.text(kLeftPaneLabel), findsOneWidget);
    expect(find.text(kRightPaneLabel), findsOneWidget);
    expect(find.textContaining('own device'), findsOneWidget);
    expect(find.textContaining('Code & Policy Audit'), findsOneWidget);
  });

  testWidgets('right pane reloads project snapshot only on explicit refresh',
      (tester) async {
    final log = ConnectionLog(MemoryConnectionLogBackend());
    var loads = 0;
    final leftTick = StreamController<void>.broadcast();
    addTearDown(leftTick.close);
    await tester.pumpWidget(
      MaterialApp(
        home: AuditSplitView(
          connectionLog: log,
          platformLabel: 'macos',
          leftPoll: leftTick.stream,
          pingProbe: (host) async => PingResult(
            host: host,
            port: kStatusTcpPort,
            ok: true,
            rttMs: 15.0 + loads,
          ),
          projectSnapshotLoader: () async {
            loads += 1;
            return buildProjectFilesSnapshot(
              auditText: 'PROJECT SNAPSHOT $loads',
              fileNames: ['AUDIT.md', 'snap-$loads.md'],
              catalogVersion: '1.2.7',
            );
          },
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 120));
    expect(loads, 1);
    expect(find.textContaining('PROJECT SNAPSHOT 1'), findsOneWidget);
    expect(find.textContaining('snap-1.md'), findsOneWidget);
    leftTick.add(null);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(loads, 1);
    expect(find.textContaining('PROJECT SNAPSHOT 1'), findsOneWidget);
    await tester.tap(find.byKey(kAuditRightRefreshKey));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(loads, 2);
    expect(find.textContaining('PROJECT SNAPSHOT 2'), findsOneWidget);
    expect(find.textContaining('snap-2.md'), findsOneWidget);
  });

  test('loadProjectAuditSnapshot uses fetchAuditText on each call', () async {
    var n = 0;
    final first = await loadProjectAuditSnapshot(
      platform: 'ios',
      fetchAuditText: () async {
        n += 1;
        return 'PUBLIC AUDIT $n';
      },
    );
    final second = await loadProjectAuditSnapshot(
      platform: 'ios',
      fetchAuditText: () async {
        n += 1;
        return 'PUBLIC AUDIT $n';
      },
    );
    expect(first['audit_excerpt'], 'PUBLIC AUDIT 1');
    expect(second['audit_excerpt'], 'PUBLIC AUDIT 2');
    expect(first['files'], contains('AUDIT.md'));
  });
}
