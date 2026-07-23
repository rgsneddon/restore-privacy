/// Free-tier product flavor — permanent version label **3.3.3**.
///
/// Enable with `--dart-define=RPT_FREE_TIER=true` at build time.
/// Free clients lock Settings (no privacy-scale / multi-hop amendments) and
/// force Iceland single-hop lean residual (no shape/obfs).
library;

/// Permanent free-tier pin — never inherit paid 0.x catalog bumps.
const String kFreeTierVersion = '3.3.3';

/// Iceland product entry (parity with [RptConfig.entryHost]).
const String kFreeTierEntryHost = '82.221.101.241';
const int kFreeTierEntryPort = 44044;

/// Compile-time free tier (`--dart-define=RPT_FREE_TIER=true`).
const bool kFreeTierFromEnvironment = bool.fromEnvironment(
  'RPT_FREE_TIER',
  defaultValue: false,
);

/// True when this binary is the free 3.3.3 flavor.
bool get freeTierEnabled => kFreeTierFromEnvironment;

/// UI / about version string for free builds is always 3.3.3.
String freeAwareProductVersion(String paidPin) =>
    freeTierEnabled ? kFreeTierVersion : paidPin;

/// Settings privacy-scale / multi-hop must not be user-amendable on free.
bool get freeTierSettingsLocked => freeTierEnabled;

/// Forced residual policy when free: shape/obfs/multihop all off.
class FreeTierLockedPrivacy {
  final bool trafficShape;
  final bool outerObfuscation;
  final bool multihop;
  final String residualHost;

  const FreeTierLockedPrivacy({
    required this.trafficShape,
    required this.outerObfuscation,
    required this.multihop,
    required this.residualHost,
  });

  /// Product free defaults (lean Iceland single-hop).
  static const FreeTierLockedPrivacy defaults = FreeTierLockedPrivacy(
    trafficShape: false,
    outerObfuscation: false,
    multihop: false,
    residualHost: kFreeTierEntryHost,
  );
}

/// Resolve locked free privacy (or null when not free — caller uses Settings).
FreeTierLockedPrivacy? resolveFreeTierPrivacy() {
  if (!freeTierEnabled) return null;
  return FreeTierLockedPrivacy.defaults;
}
