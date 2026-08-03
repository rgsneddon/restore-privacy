import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/connect_status.dart';
import 'package:restore_privacy_client/leak_posture.dart';
import 'package:restore_privacy_client/leak_test.dart';

void main() {
  test('stale connecting flag does not block residual success', () {
    final map = {
      'ok': true,
      'connecting': true,
      'fullTunnelActive': true,
      'residualCapture': true,
      'connected': true,
      'vpnIp': '10.88.0.2',
      'message': 'Connecting to DE (RPT2) — waiting for full tunnel…',
    };
    expect(isConnectSuccess(map), isTrue);
    expect(isConnectingInProgress(map), isFalse);
    final msg = mapConnectStatusMessage(map);
    expect(msg.toLowerCase(), isNot(contains('waiting for full tunnel')));
    expect(msg.toLowerCase(), contains('connected'));
  });

  test('leak test PASS under residual privacy settings without probe', () {
    final r = evaluateLeakTest(
      const LeakTestInputs(
        residualCaptureActive: true,
        ipv6Protected: true,
        dnsTunnelGatewayOnly: true,
        publicDnsViolations: [],
        publicIpProbeRan: false,
        publicIpMatchesExpectedNode: null,
      ),
    );
    expect(r.verdict, kVerdictPass);
  });

  test('leak test PASS when residual up even if live egress probe mismatches',
      () {
    // Live Settings path: runPublicIpProbe=true; catalog peer miss must not FAIL
    // residualCapture + tunnel DNS + IPv6 (Android residual-up bug report).
    final r = evaluateLeakTest(
      const LeakTestInputs(
        residualCaptureActive: true,
        ipv6Protected: true,
        dnsTunnelGatewayOnly: true,
        publicDnsViolations: [],
        publicIpProbeRan: true,
        publicIpMatchesExpectedNode: false,
      ),
    );
    expect(r.verdict, kVerdictPass);
    expect(r.formatUserMessage().toLowerCase(), contains('pass'));
    expect(r.formatUserMessage().toLowerCase(), isNot(contains('fail')));
  });

  test('leak test still FAIL on public DNS when residual is up', () {
    final dnsFail = evaluateLeakTest(
      const LeakTestInputs(
        residualCaptureActive: true,
        ipv6Protected: true,
        dnsTunnelGatewayOnly: false,
        publicDnsViolations: ['public DNS fallback not allowed: 8.8.8.8'],
        publicIpProbeRan: true,
        publicIpMatchesExpectedNode: true,
      ),
    );
    expect(dnsFail.verdict, kVerdictFail);
  });

  test('kill-switch warning markers are bold red WARNING product copy', () {
    expect(kKillSwitchWarningTitle, 'WARNING');
    expect(kKillSwitchSettingsLabel, 'KILL SWITCH');
    expect(kKillSwitchUiWarningMarker, 'kill_switch_warning_bold_red');
  });
}
