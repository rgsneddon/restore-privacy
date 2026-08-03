/// Residual leak posture, watchdog, kill-switch default-off, honest copy.
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/leak_posture.dart';
import 'package:restore_privacy_client/leak_test.dart';
import 'package:restore_privacy_client/settings_store.dart';

void main() {
  group('evaluateResidualLeakPosture', () {
    test('unprotected when residual capture off', () {
      final p = evaluateResidualLeakPosture(
        residualCaptureActive: false,
        ipv6Protected: true,
        dnsTunnelOnly: true,
        lastLeakVerdict: kVerdictPass,
        lastLeakAtMs: 1,
        nowMs: 2,
      );
      expect(p.level, ResidualLeakPostureLevel.unprotected);
      expect(p.headline, contains(kLeakPostureLabelUnprotected));
      expect(leakPostureCopyIsHonest(p.headline), isTrue);
      expect(leakPostureCopyIsHonest(p.detail), isTrue);
    });

    test('minimal only with capture + ipv6 + dns + fresh PASS', () {
      final now = 1000000;
      final p = evaluateResidualLeakPosture(
        residualCaptureActive: true,
        ipv6Protected: true,
        dnsTunnelOnly: true,
        lastLeakVerdict: kVerdictPass,
        lastLeakAtMs: now - 60000,
        nowMs: now,
      );
      expect(p.level, ResidualLeakPostureLevel.minimal);
      expect(p.headline, contains(kLeakPostureLabelMinimal));
      expect(leakPostureCopyIsHonest(kLeakPostureHonestyFootnote), isTrue);
    });

    test('stale PASS is not minimal', () {
      final now = 1000000;
      final p = evaluateResidualLeakPosture(
        residualCaptureActive: true,
        ipv6Protected: true,
        dnsTunnelOnly: true,
        lastLeakVerdict: kVerdictPass,
        lastLeakAtMs: now - 60 * 60 * 1000,
        nowMs: now,
        lastLeakPassMaxAgeMs: 30 * 60 * 1000,
      );
      expect(p.level, isNot(ResidualLeakPostureLevel.minimal));
    });

    test('partial when capture up but ipv6 missing', () {
      final p = evaluateResidualLeakPosture(
        residualCaptureActive: true,
        ipv6Protected: false,
        dnsTunnelOnly: true,
      );
      expect(p.level, ResidualLeakPostureLevel.partial);
    });
  });

  group('watchdog + private DNS + kill-switch', () {
    test('watchdog fails when capture drops while Connected', () {
      final s = evaluateResidualWatchdog(
        expectResidualConnected: true,
        residualCaptureActive: false,
        ipv6Protected: true,
        dnsTunnelOnly: true,
      );
      expect(s.ok, isFalse);
      expect(s.reason, contains('capture dropped'));
    });

    test('watchdog ok when residual session holds', () {
      final s = evaluateResidualWatchdog(
        expectResidualConnected: true,
        residualCaptureActive: true,
        ipv6Protected: true,
        dnsTunnelOnly: true,
      );
      expect(s.ok, isTrue);
    });

    test('private DNS warning when public resolvers present', () {
      expect(
        shouldWarnPrivateDnsConflict(
          residualCaptureActive: true,
          dnsTunnelOnly: true,
          publicDnsViolations: ['8.8.8.8'],
        ),
        isTrue,
      );
      expect(
        shouldWarnPrivateDnsConflict(
          residualCaptureActive: true,
          dnsTunnelOnly: true,
          publicDnsViolations: const [],
          osPrivateDnsLikely: true,
        ),
        isTrue,
      );
      expect(
        shouldWarnPrivateDnsConflict(
          residualCaptureActive: true,
          dnsTunnelOnly: true,
          publicDnsViolations: const [],
        ),
        isFalse,
      );
    });

    test('kill-switch product default off unless opt-in', () {
      expect(productKillSwitchEnabled(), isFalse);
      expect(productKillSwitchEnabled(userOptIn: false), isFalse);
      expect(productKillSwitchEnabled(userOptIn: true), isTrue);
    });
  });

  group('last leak-test persistence', () {
    test('SettingsStore saves and loads last leak test', () async {
      final backend = MemorySettingsBackend();
      final store = SettingsStore(backend);
      await store.saveLastLeakTest(verdict: kVerdictPass, atMs: 42);
      final loaded = await store.loadLastLeakTest();
      expect(loaded.verdict, kVerdictPass);
      expect(loaded.atMs, 42);
      final s = await store.load();
      expect(s.killSwitchOptIn, isFalse);
      await store.save(s.copyWith(killSwitchOptIn: true));
      expect((await store.load()).killSwitchOptIn, isTrue);
    });
  });

  group('copy honesty structural', () {
    test('posture strings avoid forbidden absolute-zero phrases', () {
      expect(leakPostureCopyIsHonest(kLeakPostureHonestyFootnote), isTrue);
      expect(leakPostureCopyIsHonest(kLeakPostureLabelMinimal), isTrue);
      expect(leakPostureCopyIsHonest(kWebRtcStunGuidanceBody), isTrue);
      expect(leakPostureCopyIsHonest(kPrivateDnsWarningBody), isTrue);
      expect(leakPostureCopyIsHonest(kKillSwitchSettingsBody), isTrue);
      expect(
        leakPostureCopyIsHonest('Zero leakage guaranteed forever'),
        isFalse,
      );
    });
  });

  group('live status parse + DNS resolve (no hardcoded true)', () {
    test('parseNativeResidualStatus reads residualCapture and dns flags', () {
      final f = parseNativeResidualStatus({
        'connected': true,
        'fullTunnelActive': true,
        'residualCapture': true,
        'ipv6Protected': true,
        'dnsTunnelOnly': true,
        'dnsServers': ['10.88.0.1'],
      });
      expect(f.residualCaptureActive, isTrue);
      expect(f.ipv6Protected, isTrue);
      expect(f.dnsTunnelOnly, isTrue);
      expect(resolveDnsTunnelOnly(flags: f), isTrue);
    });

    test('dnsTunnelOnly false when native reports false', () {
      final f = parseNativeResidualStatus({
        'connected': true,
        'fullTunnelActive': true,
        'residualCapture': true,
        'dnsTunnelOnly': false,
      });
      expect(resolveDnsTunnelOnly(flags: f), isFalse);
    });

    test('dnsTunnelOnly false when residual capture inactive', () {
      final f = parseNativeResidualStatus({
        'connected': false,
        'fullTunnelActive': false,
      });
      expect(f.residualCaptureActive, isFalse);
      expect(resolveDnsTunnelOnly(flags: f), isFalse);
    });

    test('public DNS servers fail product DNS plan', () {
      final plan = productDnsLeakPlan(observedServers: ['8.8.8.8']);
      expect(plan.ok, isFalse);
      expect(plan.publicFallbackViolations, isNotEmpty);
    });

    test('collectProductLeakTestInputs does not invent PASS match', () async {
      final inputs = await collectProductLeakTestInputs(
        nativeStatus: {
          'connected': true,
          'fullTunnelActive': true,
          'residualCapture': true,
          'ipv6Protected': true,
          'dnsTunnelOnly': true,
        },
        runPublicIpProbe: true,
        publicIpLookup: () async => '203.0.113.9', // not a residual peer
      );
      expect(inputs.publicIpProbeRan, isTrue);
      expect(inputs.publicIpMatchesExpectedNode, isFalse);
      final r = runProductLeakTest(
        residualCaptureActive: inputs.residualCaptureActive,
        ipv6Protected: inputs.ipv6Protected,
        dnsTunnelGatewayOnly: inputs.dnsTunnelGatewayOnly,
        publicDnsViolations: inputs.publicDnsViolations,
        publicIpProbeRan: inputs.publicIpProbeRan,
        publicIpMatchesExpectedNode: inputs.publicIpMatchesExpectedNode,
      );
      expect(r.verdict, isNot(kVerdictPass));
    });

    test('collectProductLeakTestInputs PASS only with peer IP match', () async {
      final peer = productResidualPeerPublicIps().first;
      final inputs = await collectProductLeakTestInputs(
        nativeStatus: {
          'connected': true,
          'fullTunnelActive': true,
          'residualCapture': true,
          'ipv6Protected': true,
          'dnsTunnelOnly': true,
        },
        runPublicIpProbe: true,
        publicIpLookup: () async => peer,
      );
      expect(inputs.publicIpMatchesExpectedNode, isTrue);
      final r = runProductLeakTest(
        residualCaptureActive: inputs.residualCaptureActive,
        ipv6Protected: inputs.ipv6Protected,
        dnsTunnelGatewayOnly: inputs.dnsTunnelGatewayOnly,
        publicDnsViolations: inputs.publicDnsViolations,
        publicIpProbeRan: inputs.publicIpProbeRan,
        publicIpMatchesExpectedNode: inputs.publicIpMatchesExpectedNode,
      );
      expect(r.verdict, kVerdictPass);
    });

    test('watchdog fails when dns tunnel posture lost', () {
      final s = evaluateResidualWatchdog(
        expectResidualConnected: true,
        residualCaptureActive: true,
        ipv6Protected: true,
        dnsTunnelOnly: false,
      );
      expect(s.ok, isFalse);
      expect(s.reason, contains('tunnel DNS'));
    });
  });
}
