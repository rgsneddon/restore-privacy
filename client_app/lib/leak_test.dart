/// Product-honest leak test evaluation (mirrors client/leak_test.py).
///
/// Pure function of residual/DNS inputs. Does not claim multi-hop residual.
library;

const String kVerdictPass = 'pass';
const String kVerdictFail = 'fail';
const String kVerdictPartial = 'partial';
const String kVerdictInconclusive = 'inconclusive';

class LeakTestInputs {
  final bool residualCaptureActive;
  final bool ipv6Protected;
  final bool dnsTunnelGatewayOnly;
  final List<String> publicDnsViolations;
  final bool publicIpProbeRan;
  final bool? publicIpMatchesExpectedNode;
  final bool multihopResidualRouted;

  const LeakTestInputs({
    required this.residualCaptureActive,
    this.ipv6Protected = false,
    this.dnsTunnelGatewayOnly = true,
    this.publicDnsViolations = const [],
    this.publicIpProbeRan = false,
    this.publicIpMatchesExpectedNode,
    this.multihopResidualRouted = false,
  });
}

class LeakTestResult {
  final String verdict;
  final String summary;
  final List<String> details;
  final bool claimsMultihopResidual;

  const LeakTestResult({
    required this.verdict,
    required this.summary,
    this.details = const [],
    this.claimsMultihopResidual = false,
  });

  String formatUserMessage() {
    final lines = <String>['Leak test: ${verdict.toUpperCase()} — $summary'];
    for (final d in details) {
      lines.add('• $d');
    }
    if (!claimsMultihopResidual) {
      lines.add(
        '• Multi-hop residual routing is not claimed (entry/config only).',
      );
    }
    return lines.join('\n');
  }
}

/// Pure decision function — Settings button should call [runProductLeakTest]
/// or this with collected inputs.
LeakTestResult evaluateLeakTest(LeakTestInputs inputs) {
  final details = <String>[];
  const claimsMh = false;

  if (inputs.multihopResidualRouted) {
    details.add(
      'Multi-hop residual flag was set; product does not route multi-hop residual.',
    );
  }

  final dnsOk =
      inputs.dnsTunnelGatewayOnly && inputs.publicDnsViolations.isEmpty;
  if (inputs.publicDnsViolations.isNotEmpty) {
    details.add(
      'Public DNS fallbacks present: ${inputs.publicDnsViolations.take(4).join('; ')}',
    );
  } else if (inputs.dnsTunnelGatewayOnly) {
    details.add('DNS plan: tunnel gateway only (no public resolver fallback).');
  } else {
    details.add('DNS plan is not tunnel-gateway-only.');
  }

  if (!inputs.residualCaptureActive) {
    details.add(
      'Residual public-IP capture is not active '
      '(full tunnel dual /1 + system capture required).',
    );
    if (!dnsOk) {
      return LeakTestResult(
        verdict: kVerdictFail,
        summary: 'Not residual-protected; DNS posture also failed.',
        details: details,
        claimsMultihopResidual: claimsMh,
      );
    }
    return LeakTestResult(
      verdict: kVerdictInconclusive,
      summary:
          'Connect with full residual tunnel first, then re-run Leak test. '
          'No residual capture is active right now.',
      details: details,
      claimsMultihopResidual: claimsMh,
    );
  }

  details.add('Residual public-IP capture is active (system tunnel path).');
  if (inputs.ipv6Protected) {
    details.add('IPv6 ISP egress mitigation applied for this session.');
  } else {
    details.add(
      'IPv6 residual protection not confirmed for this session '
      '(IPv4 residual may still be active).',
    );
  }

  var probeFail = false;
  if (inputs.publicIpProbeRan) {
    if (inputs.publicIpMatchesExpectedNode == true) {
      details.add('Public egress probe matches expected VPN/node path.');
    } else if (inputs.publicIpMatchesExpectedNode == false) {
      details.add(
        'Public egress probe did not match expected VPN/node path '
        '(possible residual leak).',
      );
      probeFail = true;
    } else {
      details.add('Public egress probe ran but result was inconclusive.');
    }
  } else {
    details.add(
      'Live public-IP probe not run (offline-safe path or user skipped).',
    );
  }

  if (!dnsOk || probeFail) {
    return LeakTestResult(
      verdict: kVerdictFail,
      summary: 'Residual capture is up, but DNS or egress check failed.',
      details: details,
      claimsMultihopResidual: claimsMh,
    );
  }

  if (!inputs.ipv6Protected || !inputs.publicIpProbeRan) {
    return LeakTestResult(
      verdict: kVerdictPartial,
      summary: !inputs.ipv6Protected
          ? 'Residual IPv4 capture looks good; IPv6 protection not confirmed.'
          : 'Residual IPv4 capture looks good; live egress probe not run.',
      details: details,
      claimsMultihopResidual: claimsMh,
    );
  }

  return LeakTestResult(
    verdict: kVerdictPass,
    summary:
        'Residual capture active, tunnel DNS only, IPv6 protected, '
        'and egress probe matched the node path.',
    details: details,
    claimsMultihopResidual: claimsMh,
  );
}

/// Entry point Settings UI calls. DNS defaults match product tunnel-gateway plan.
LeakTestResult runProductLeakTest({
  required bool residualCaptureActive,
  bool ipv6Protected = false,
  bool dnsTunnelGatewayOnly = true,
  List<String> publicDnsViolations = const [],
  bool publicIpProbeRan = false,
  bool? publicIpMatchesExpectedNode,
}) {
  return evaluateLeakTest(
    LeakTestInputs(
      residualCaptureActive: residualCaptureActive,
      ipv6Protected: ipv6Protected,
      dnsTunnelGatewayOnly: dnsTunnelGatewayOnly,
      publicDnsViolations: publicDnsViolations,
      publicIpProbeRan: publicIpProbeRan,
      publicIpMatchesExpectedNode: publicIpMatchesExpectedNode,
      multihopResidualRouted: false,
    ),
  );
}
