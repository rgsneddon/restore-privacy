/// Residual privacy-scale policy for Apple/desktop Settings parity.
///
/// Maps customer toggles to residual DATA flags used on the wire:
/// - traffic shaping ON → RPTP padding + cover + send jitter
/// - outer obfuscation ON → QUIC-mimic wrap
///
/// Pre-adjustment defaults match Windows [client.product_policy.PrivacyScalePrefs]
/// and Swift [RptResidualPrivacyPolicy]: shape/obfs/multihop all OFF (lean residual).
/// Residual VPN core (HELLO/session/tunnel) is never disabled here.
///
/// Flutter Settings persists the same keys that Packet Tunnel reads from the
/// App Group (`privacy_traffic_shape`, `privacy_outer_obfuscation`,
/// `privacy_multihop`).
library;

import 'free_tier.dart';

const String kResidualKeyTrafficShape = 'privacy_traffic_shape';
const String kResidualKeyOuterObfuscation = 'privacy_outer_obfuscation';
const String kResidualKeyMultihop = 'privacy_multihop';

/// Observable residual DATA flags (not cosmetic).
class ResidualPrivacyFlags {
  final bool padding;
  final bool cover;
  final bool sendJitter;
  final bool outerObfuscation;
  final bool multihop;

  const ResidualPrivacyFlags({
    required this.padding,
    required this.cover,
    required this.sendJitter,
    required this.outerObfuscation,
    required this.multihop,
  });

  /// Product lean residual defaults (optional layers off until user opts in).
  static const ResidualPrivacyFlags productDefaults = ResidualPrivacyFlags(
    padding: false,
    cover: false,
    sendJitter: false,
    outerObfuscation: false,
    multihop: false,
  );

  /// Free 3.3.3 lean residual (Iceland single-hop, no extras).
  static const ResidualPrivacyFlags freeTierLean = ResidualPrivacyFlags(
    padding: false,
    cover: false,
    sendJitter: false,
    outerObfuscation: false,
    multihop: false,
  );
}

/// Resolve residual wire flags from customer privacy-scale toggles.
///
/// When [trafficShape] is false, padding, cover, and send jitter are all off
/// (lean residual). When [outerObfuscation] is false, outer wrap is off.
/// Core residual VPN (HELLO/session/tunnel) is never disabled here.
/// Free tier forces [ResidualPrivacyFlags.freeTierLean] regardless of toggles.
ResidualPrivacyFlags resolveResidualPrivacy({
  bool trafficShape = false,
  bool outerObfuscation = false,
  bool multihop = false,
}) {
  if (freeTierEnabled) {
    return ResidualPrivacyFlags.freeTierLean;
  }
  final shape = trafficShape;
  return ResidualPrivacyFlags(
    padding: shape,
    cover: shape,
    sendJitter: shape,
    outerObfuscation: outerObfuscation,
    multihop: multihop,
  );
}

/// Load from a key/value map (SharedPreferences / App Group snapshot).
///
/// Missing keys use product defaults (shape/obfs/multihop all OFF).
/// Free tier ignores stored prefs for residual DATA flags.
ResidualPrivacyFlags residualPrivacyFromStoredPrefs(Map<String, bool?> stored) {
  if (freeTierEnabled) {
    return ResidualPrivacyFlags.freeTierLean;
  }
  final shape = stored[kResidualKeyTrafficShape];
  final obfs = stored[kResidualKeyOuterObfuscation];
  final mh = stored[kResidualKeyMultihop];
  return resolveResidualPrivacy(
    trafficShape: shape == true,
    outerObfuscation: obfs == true,
    multihop: mh == true,
  );
}
