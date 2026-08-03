/// Residual leak posture for Settings / Home — product-honest "minimal risk".
///
/// Never claims absolute zero leakage. Minimal only when residual capture,
/// tunnel DNS, IPv6 residual protection, and a PASS leak-test evaluation hold.
/// Design: docs/LEAK_HARDENING_EXPLORATION.md
library;

import 'leak_test.dart';

/// Forbidden absolute-zero marketing claims (must not appear as product promises).
/// Checked as whole-phrase claims; honesty footnotes may negate risk language.
const List<String> kLeakPostureForbiddenPhrases = [
  'zero leakage guaranteed',
  '100% leak-proof',
  'zero data leakage',
  'invisible to all networks',
  'dpi-undetectable',
  'guarantees perfect anonymity',
];

const String kLeakPostureSectionTitle = 'Residual leak posture';
const String kLeakPostureHonestyFootnote =
    'Minimal means ordinary residual IP and DNS leaks are mitigated for this '
    'session under product residual rules. It does not mean perfect anonymity, '
    'traffic-analysis resistance, or protection before Connect / after Disconnect. '
    'Optional privacy-scale layers (shape, outer obfuscation, multihop) trade '
    'speed for harder fingerprinting — not zero risk.';

const String kLeakPostureLabelMinimal = 'Minimal (this session)';
const String kLeakPostureLabelUnverified = 'Unverified';
const String kLeakPostureLabelUnprotected = 'Unprotected';
const String kLeakPostureLabelPartial = 'Partial';

const String kWebRtcStunGuidanceTitle = 'Browser WebRTC / STUN';
const String kWebRtcStunGuidanceBody =
    'Some browsers can learn your path via WebRTC/STUN even while residual is '
    'up. Residual full-tunnel capture is the primary defence. For extra care, '
    'disable WebRTC in the browser or use a hardened browser profile. Product '
    'does not claim WebRTC-proof residual on every browser.';

const String kPrivateDnsWarningTitle = 'Private DNS / public DoH risk';
const String kPrivateDnsWarningBody =
    'If the OS uses Private DNS or app-hardcoded public DoH (e.g. 8.8.8.8 / '
    '1.1.1.1), queries may bypass tunnel DNS. Prefer automatic/off Private DNS '
    'while residual is Connected. Tunnel-gateway-only DNS is required for leak '
    'test PASS.';

const String kKillSwitchSettingsLabel = 'KILL SWITCH';
const String kKillSwitchWarningTitle = 'WARNING';
const String kKillSwitchSettingsBody =
    'When ON, the product attempts fail-closed egress if residual dies '
    '(may break captive portals, updates, or local networks). Default OFF — '
    'lean residual uses scoped allows only. Never claimed perfect.';
/// Marker for tests: kill-switch user chrome is a WARNING block with bold red text.
const String kKillSwitchUiWarningMarker = 'kill_switch_warning_bold_red';

/// Posture level for UI chrome.
enum ResidualLeakPostureLevel {
  /// Residual capture + DNS + IPv6 + last leak test PASS.
  minimal,
  /// Residual capture up but leak test incomplete / PARTIAL.
  partial,
  /// Connected-ish flags incomplete; run leak test.
  unverified,
  /// Residual capture not active.
  unprotected,
}

class ResidualLeakPosture {
  const ResidualLeakPosture({
    required this.level,
    required this.headline,
    required this.detail,
    required this.residualCaptureActive,
    required this.ipv6Protected,
    required this.dnsTunnelOnly,
    required this.lastLeakVerdict,
    this.lastLeakAtMs,
  });

  final ResidualLeakPostureLevel level;
  final String headline;
  final String detail;
  final bool residualCaptureActive;
  final bool ipv6Protected;
  final bool dnsTunnelOnly;
  final String? lastLeakVerdict;
  final int? lastLeakAtMs;

  String get levelLabel {
    switch (level) {
      case ResidualLeakPostureLevel.minimal:
        return kLeakPostureLabelMinimal;
      case ResidualLeakPostureLevel.partial:
        return kLeakPostureLabelPartial;
      case ResidualLeakPostureLevel.unverified:
        return kLeakPostureLabelUnverified;
      case ResidualLeakPostureLevel.unprotected:
        return kLeakPostureLabelUnprotected;
    }
  }
}

/// Pure: evaluate residual leak posture from live flags + last leak-test store.
///
/// [lastLeakPassMaxAgeMs] — PASS older than this is ignored for Minimal
/// (default 30 minutes). Null = any age accepted if verdict is pass.
ResidualLeakPosture evaluateResidualLeakPosture({
  required bool residualCaptureActive,
  required bool ipv6Protected,
  required bool dnsTunnelOnly,
  String? lastLeakVerdict,
  int? lastLeakAtMs,
  int? nowMs,
  int? lastLeakPassMaxAgeMs = 30 * 60 * 1000,
}) {
  final now = nowMs ?? DateTime.now().millisecondsSinceEpoch;
  final verdict = (lastLeakVerdict ?? '').trim().toLowerCase();
  final passFresh = verdict == kVerdictPass &&
      lastLeakAtMs != null &&
      (lastLeakPassMaxAgeMs == null ||
          (now - lastLeakAtMs) <= lastLeakPassMaxAgeMs);

  if (!residualCaptureActive) {
    return ResidualLeakPosture(
      level: ResidualLeakPostureLevel.unprotected,
      headline: 'Residual leak risk: $kLeakPostureLabelUnprotected',
      detail:
          'Residual capture is not active — ISP path may be used. Connect with '
          'full residual tunnel, then run Leak test.',
      residualCaptureActive: false,
      ipv6Protected: ipv6Protected,
      dnsTunnelOnly: dnsTunnelOnly,
      lastLeakVerdict: lastLeakVerdict,
      lastLeakAtMs: lastLeakAtMs,
    );
  }

  // Minimal only when all live flags + fresh PASS hold.
  if (residualCaptureActive &&
      ipv6Protected &&
      dnsTunnelOnly &&
      passFresh) {
    return ResidualLeakPosture(
      level: ResidualLeakPostureLevel.minimal,
      headline: 'Residual leak risk: $kLeakPostureLabelMinimal',
      detail:
          'Residual IP capture, tunnel DNS, and IPv6 residual protection are '
          'active. Last leak test: PASS.',
      residualCaptureActive: true,
      ipv6Protected: true,
      dnsTunnelOnly: true,
      lastLeakVerdict: lastLeakVerdict,
      lastLeakAtMs: lastLeakAtMs,
    );
  }

  if (verdict == kVerdictPartial ||
      (residualCaptureActive && (!ipv6Protected || !dnsTunnelOnly))) {
    return ResidualLeakPosture(
      level: ResidualLeakPostureLevel.partial,
      headline: 'Residual leak risk: $kLeakPostureLabelPartial',
      detail:
          'Residual IPv4 capture looks active, but IPv6 residual, tunnel DNS, '
          'or leak test is incomplete. Run Leak test while Connected.',
      residualCaptureActive: residualCaptureActive,
      ipv6Protected: ipv6Protected,
      dnsTunnelOnly: dnsTunnelOnly,
      lastLeakVerdict: lastLeakVerdict,
      lastLeakAtMs: lastLeakAtMs,
    );
  }

  return ResidualLeakPosture(
    level: ResidualLeakPostureLevel.unverified,
    headline: 'Residual leak risk: $kLeakPostureLabelUnverified',
    detail:
        'Connect is residual-capable; run Leak test to confirm residual IP '
        'and DNS for this session.',
    residualCaptureActive: residualCaptureActive,
    ipv6Protected: ipv6Protected,
    dnsTunnelOnly: dnsTunnelOnly,
    lastLeakVerdict: lastLeakVerdict,
    lastLeakAtMs: lastLeakAtMs,
  );
}

/// Pure: copy is free of forbidden absolute-zero marketing.
bool leakPostureCopyIsHonest(String text) {
  final lower = text.toLowerCase();
  for (final p in kLeakPostureForbiddenPhrases) {
    if (lower.contains(p)) return false;
  }
  return true;
}

/// Watchdog pure decision: residual session integrity while Connected.
class ResidualWatchdogSnapshot {
  const ResidualWatchdogSnapshot({
    required this.ok,
    required this.reason,
    required this.residualCaptureActive,
    required this.ipv6Protected,
    required this.dnsTunnelOnly,
  });

  final bool ok;
  final String reason;
  final bool residualCaptureActive;
  final bool ipv6Protected;
  final bool dnsTunnelOnly;
}

/// Pure: while residual Connected is expected, drop is not OK if capture dies.
ResidualWatchdogSnapshot evaluateResidualWatchdog({
  required bool expectResidualConnected,
  required bool residualCaptureActive,
  required bool ipv6Protected,
  required bool dnsTunnelOnly,
  bool residualIpv6SettingOn = true,
}) {
  if (!expectResidualConnected) {
    return ResidualWatchdogSnapshot(
      ok: true,
      reason: 'residual not expected up',
      residualCaptureActive: residualCaptureActive,
      ipv6Protected: ipv6Protected,
      dnsTunnelOnly: dnsTunnelOnly,
    );
  }
  if (!residualCaptureActive) {
    return ResidualWatchdogSnapshot(
      ok: false,
      reason: 'residual capture dropped while Connected',
      residualCaptureActive: false,
      ipv6Protected: ipv6Protected,
      dnsTunnelOnly: dnsTunnelOnly,
    );
  }
  if (residualIpv6SettingOn && !ipv6Protected) {
    return ResidualWatchdogSnapshot(
      ok: false,
      reason: 'IPv6 residual protection lost while Connected',
      residualCaptureActive: true,
      ipv6Protected: false,
      dnsTunnelOnly: dnsTunnelOnly,
    );
  }
  if (!dnsTunnelOnly) {
    return ResidualWatchdogSnapshot(
      ok: false,
      reason: 'tunnel DNS posture lost while Connected',
      residualCaptureActive: true,
      ipv6Protected: ipv6Protected,
      dnsTunnelOnly: false,
    );
  }
  return ResidualWatchdogSnapshot(
    ok: true,
    reason: 'residual capture, DNS, and IPv6 posture hold',
    residualCaptureActive: true,
    ipv6Protected: ipv6Protected,
    dnsTunnelOnly: true,
  );
}

/// Pure: warn when public DoH/Private DNS risk is indicated.
bool shouldWarnPrivateDnsConflict({
  required bool residualCaptureActive,
  required bool dnsTunnelOnly,
  required List<String> publicDnsViolations,
  bool osPrivateDnsLikely = false,
}) {
  if (!residualCaptureActive) return false;
  if (publicDnsViolations.isNotEmpty) return true;
  if (!dnsTunnelOnly) return true;
  if (osPrivateDnsLikely) return true;
  return false;
}

/// Kill-switch product default is always off unless user opt-in stored true.
bool productKillSwitchEnabled({bool userOptIn = false}) => userOptIn == true;
