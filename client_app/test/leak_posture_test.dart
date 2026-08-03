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
}
