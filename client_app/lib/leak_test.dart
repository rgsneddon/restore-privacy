/// Product-honest leak test evaluation (mirrors client/leak_test.py).
///
/// Pure function of residual/DNS inputs. Does not claim multi-hop residual.
/// Live Settings path: [collectProductLeakTestInputs] + [runProductLeakTest].
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'rpt_config.dart';
import 'suite_network_config.dart';

const String kVerdictPass = 'pass';
const String kVerdictFail = 'fail';
const String kVerdictPartial = 'partial';
const String kVerdictInconclusive = 'inconclusive';

/// Product residual tunnel DNS gateway (mirrors client/full_tunnel.py).
const String kProductTunnelDnsGateway = '10.88.0.1';

/// Public resolvers that must never appear as product residual DNS defaults.
const List<String> kPublicDnsBlocklist = [
  '1.1.1.1',
  '1.0.0.1',
  '8.8.8.8',
  '8.8.4.4',
  '9.9.9.9',
  '149.112.112.112',
  '208.67.222.222',
  '208.67.220.220',
  '8.26.56.26',
];

/// Shipped residual DNS servers — tunnel gateway only.
List<String> productDnsServers() => [kProductTunnelDnsGateway];

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
  var probeMatch = false;
  var probeInconclusive = false;
  if (inputs.publicIpProbeRan) {
    if (inputs.publicIpMatchesExpectedNode == true) {
      details.add('Public egress probe matches expected VPN/node path.');
      probeMatch = true;
    } else if (inputs.publicIpMatchesExpectedNode == false) {
      details.add(
        'Public egress probe did not match expected VPN/node path '
        '(possible residual leak).',
      );
      probeFail = true;
    } else {
      details.add('Public egress probe ran but result was inconclusive.');
      probeInconclusive = true;
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

  // PASS only when residual + DNS + IPv6 + definitive matching egress probe.
  // Inconclusive probe (ran but matches=null) must never claim pass / "matched".
  if (inputs.ipv6Protected &&
      inputs.publicIpProbeRan &&
      probeMatch &&
      !probeInconclusive) {
    return LeakTestResult(
      verdict: kVerdictPass,
      summary:
          'Residual capture active, tunnel DNS only, IPv6 protected, '
          'and egress probe matched the node path.',
      details: details,
      claimsMultihopResidual: claimsMh,
    );
  }

  final reasons = <String>[];
  if (!inputs.ipv6Protected) {
    reasons.add('IPv6 protection not confirmed');
  }
  if (!inputs.publicIpProbeRan) {
    reasons.add('live egress probe not run');
  } else if (probeInconclusive) {
    reasons.add('egress probe result was inconclusive');
  }
  final summaryTail =
      reasons.isEmpty ? 'checks incomplete' : reasons.join('; ');
  return LeakTestResult(
    verdict: kVerdictPartial,
    summary: 'Residual IPv4 capture looks good; $summaryTail.',
    details: details,
    claimsMultihopResidual: claimsMh,
  );
}

/// Entry point Settings UI calls. Prefer [collectProductLeakTestInputs] so
/// DNS/IP are not invented constants.
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

/// Structural product DNS leak plan (mirrors client/leak_protection.dns_leak_check_plan).
class ProductDnsLeakPlan {
  const ProductDnsLeakPlan({
    required this.dnsServers,
    required this.tunnelGatewayOnly,
    required this.publicFallbackViolations,
  });

  final List<String> dnsServers;
  final bool tunnelGatewayOnly;
  final List<String> publicFallbackViolations;

  bool get ok =>
      tunnelGatewayOnly && publicFallbackViolations.isEmpty;
}

/// Evaluate observed (or product-default) DNS servers for tunnel-gateway-only.
ProductDnsLeakPlan productDnsLeakPlan({List<String>? observedServers}) {
  final servers = (observedServers == null || observedServers.isEmpty)
      ? productDnsServers()
      : List<String>.from(observedServers);
  final violations = <String>[];
  for (final s in servers) {
    final ip = s.trim().split('%').first;
    if (kPublicDnsBlocklist.contains(ip)) {
      violations.add('public DNS fallback not allowed: $ip');
    }
  }
  final tunnelOnly = servers.length == 1 &&
      servers.first.trim() == kProductTunnelDnsGateway;
  return ProductDnsLeakPlan(
    dnsServers: servers,
    tunnelGatewayOnly: tunnelOnly,
    publicFallbackViolations: violations,
  );
}

/// Live residual / DNS flags parsed from a native `status` channel map.
class NativeResidualStatusFlags {
  const NativeResidualStatusFlags({
    required this.connected,
    required this.residualCaptureActive,
    required this.ipv6Protected,
    required this.fullTunnelActive,
    this.dnsTunnelOnly,
    this.dnsServers = const [],
    this.vpnIp,
    this.rawMessage,
  });

  final bool connected;
  final bool residualCaptureActive;
  final bool ipv6Protected;
  final bool fullTunnelActive;

  /// Explicit native DNS tunnel-only flag when present; null if not reported.
  final bool? dnsTunnelOnly;
  final List<String> dnsServers;
  final String? vpnIp;
  final String? rawMessage;
}

/// Parse residual capture / IPv6 / DNS posture from a native status map.
NativeResidualStatusFlags parseNativeResidualStatus(dynamic result) {
  if (result is! Map) {
    return const NativeResidualStatusFlags(
      connected: false,
      residualCaptureActive: false,
      ipv6Protected: false,
      fullTunnelActive: false,
    );
  }
  final map = Map<Object?, Object?>.from(result);
  final connected = map['connected'] == true ||
      (map['ok'] == true && map['fullTunnelActive'] == true);
  final fullTunnel = map['fullTunnelActive'] == true ||
      map['routesApplied'] == true ||
      map['systemCapture'] == true;
  final residualCapture = map['residualCapture'] == true ||
      map['systemCapture'] == true ||
      map['routesApplied'] == true ||
      (connected && fullTunnel) ||
      (connected && map['ipv4Residual'] != false && fullTunnel) ||
      (connected && map['fullTunnelActive'] == true);
  // Connected product residual path implies capture when full tunnel is active.
  final residualCaptureActive = residualCapture ||
      (connected && (fullTunnel || map['fullTunnelActive'] == true));

  bool ipv6 = false;
  if (map['ipv6Protected'] is bool) {
    ipv6 = map['ipv6Protected'] as bool;
  }

  bool? dnsFlag;
  if (map['dnsTunnelOnly'] is bool) {
    dnsFlag = map['dnsTunnelOnly'] as bool;
  } else if (map['dnsTunnelGatewayOnly'] is bool) {
    dnsFlag = map['dnsTunnelGatewayOnly'] as bool;
  }

  final dnsServers = <String>[];
  final rawDns = map['dnsServers'] ?? map['dns'];
  if (rawDns is List) {
    for (final e in rawDns) {
      final s = e?.toString().trim() ?? '';
      if (s.isNotEmpty) dnsServers.add(s);
    }
  }

  final ip = map['vpnIp']?.toString().trim();
  final msg = map['message']?.toString().trim();
  return NativeResidualStatusFlags(
    connected: connected,
    residualCaptureActive: residualCaptureActive,
    ipv6Protected: ipv6,
    fullTunnelActive: fullTunnel || residualCaptureActive,
    dnsTunnelOnly: dnsFlag,
    dnsServers: dnsServers,
    vpnIp: (ip == null || ip.isEmpty) ? null : ip,
    rawMessage: (msg == null || msg.isEmpty) ? null : msg,
  );
}

/// Resolve tunnel-DNS-only from native flags + product DNS plan (never a bare true).
///
/// - Explicit native flag wins.
/// - Observed DNS server list is checked against the product plan.
/// - When residual capture is inactive, returns false (ISP DNS may be in use).
/// - When residual is up and native omits DNS fields, product residual DNS plan
///   (tunnel gateway only) is evaluated — not a Settings hardcode.
bool resolveDnsTunnelOnly({
  required NativeResidualStatusFlags flags,
  List<String>? observedDnsServers,
}) {
  if (flags.dnsTunnelOnly != null) {
    return flags.dnsTunnelOnly!;
  }
  final servers = observedDnsServers ??
      (flags.dnsServers.isNotEmpty ? flags.dnsServers : null);
  if (servers != null) {
    final plan = productDnsLeakPlan(observedServers: servers);
    return plan.ok;
  }
  if (!flags.residualCaptureActive) {
    return false;
  }
  // Residual capture up, no OS DNS report: product residual DNS plan holds.
  return productDnsLeakPlan().ok;
}

/// Residual peer public IPs expected when egress is through product nodes.
List<String> productResidualPeerPublicIps() {
  final hosts = <String>{
    RptConfig.entryHost,
    RptConfig.icelandHost,
    RptConfig.host,
    ...RptConfig.alternateHosts,
  };
  // exitHost may equal entryHost (DE default); set already de-dupes.
  final exit = RptConfig.exitHost.trim();
  if (exit.isNotEmpty) hosts.add(exit);
  return hosts.where((h) => h.trim().isNotEmpty).toList();
}

/// True if [publicIp] matches a known residual peer public IP.
bool publicIpMatchesResidualPeer(
  String? publicIp, {
  List<String>? expectedIps,
}) {
  final ip = (publicIp ?? '').trim();
  if (ip.isEmpty) return false;
  final expected = expectedIps ?? productResidualPeerPublicIps();
  return expected.any((e) => e.trim() == ip);
}

/// Lookup public egress IP via product publicIp lookup URLs (injectable).
Future<String?> lookupPublicEgressIp({
  Future<String?> Function()? injector,
  List<String>? urls,
  Duration timeout = const Duration(seconds: 8),
}) async {
  if (injector != null) {
    return injector();
  }
  final candidates = urls ??
      const [
        'https://api.ipify.org',
        'https://ifconfig.me/ip',
      ];
  // Prefer suite config URLs when available.
  final fromSuite = suitePercNetworkJson()['publicIpLookupUrls'];
  final list = <String>[
    if (fromSuite is List)
      for (final u in fromSuite)
        if (u != null && u.toString().trim().isNotEmpty) u.toString().trim(),
    ...candidates,
  ];
  final seen = <String>{};
  final client = HttpClient();
  try {
    for (final url in list) {
      if (!seen.add(url)) continue;
      try {
        final req = await client.getUrl(Uri.parse(url)).timeout(timeout);
        req.headers.set(HttpHeaders.userAgentHeader, 'rpt-leak-test/1.1.2');
        final resp = await req.close().timeout(timeout);
        if (resp.statusCode < 200 || resp.statusCode >= 300) continue;
        final body = (await resp.transform(utf8.decoder).join()).trim();
        // First token / line that looks like an IPv4.
        final m = RegExp(r'\b(\d{1,3}(?:\.\d{1,3}){3})\b').firstMatch(body);
        if (m != null) return m.group(1);
        if (body.isNotEmpty && !body.contains(' ')) return body;
      } catch (_) {
        continue;
      }
    }
  } finally {
    client.close(force: true);
  }
  return null;
}

/// Collect real leak-test inputs (native status + DNS plan + optional IP probe).
///
/// Does **not** invent PASS: public IP match is only true when the live probe
/// returns a known residual peer IP (or injectable match). DNS comes from
/// native flags / observed servers / product DNS plan evaluation.
Future<LeakTestInputs> collectProductLeakTestInputs({
  dynamic nativeStatus,
  bool parentResidualCapture = false,
  bool parentIpv6Protected = false,
  bool runPublicIpProbe = true,
  Future<String?> Function()? publicIpLookup,
  List<String>? expectedResidualPublicIps,
  List<String>? observedDnsServers,
}) async {
  final flags = parseNativeResidualStatus(nativeStatus);
  final residual = flags.residualCaptureActive || parentResidualCapture;
  final ipv6 = flags.ipv6Protected ||
      (nativeStatus == null && parentIpv6Protected);
  final dnsOnly = resolveDnsTunnelOnly(
    flags: NativeResidualStatusFlags(
      connected: flags.connected || residual,
      residualCaptureActive: residual,
      ipv6Protected: ipv6,
      fullTunnelActive: flags.fullTunnelActive || residual,
      dnsTunnelOnly: flags.dnsTunnelOnly,
      dnsServers: flags.dnsServers,
      vpnIp: flags.vpnIp,
      rawMessage: flags.rawMessage,
    ),
    observedDnsServers: observedDnsServers,
  );
  final plan = productDnsLeakPlan(
    observedServers: observedDnsServers ??
        (flags.dnsServers.isNotEmpty ? flags.dnsServers : null),
  );
  final violations = List<String>.from(plan.publicFallbackViolations);

  var probeRan = false;
  bool? matches;
  if (runPublicIpProbe && residual) {
    probeRan = true;
    try {
      final ip = await lookupPublicEgressIp(injector: publicIpLookup);
      if (ip == null || ip.isEmpty) {
        matches = null;
      } else {
        matches = publicIpMatchesResidualPeer(
          ip,
          expectedIps: expectedResidualPublicIps,
        );
      }
    } catch (_) {
      matches = null;
    }
  }

  return LeakTestInputs(
    residualCaptureActive: residual,
    ipv6Protected: ipv6,
    dnsTunnelGatewayOnly: dnsOnly,
    publicDnsViolations: violations,
    publicIpProbeRan: probeRan,
    publicIpMatchesExpectedNode: matches,
    multihopResidualRouted: false,
  );
}

