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
          auditText: '# Restore Privacy — Code & Policy Audit\n',
          leftPoll: const Stream<void>.empty(),
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
  });
}
