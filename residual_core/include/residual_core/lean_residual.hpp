// Product lean residual policy — pure defaults for low-ping / low-CPU path.
//
// Aligns with client ProductSettings / product_policy: traffic shape, outer
// obfuscation, and multi-hop residual are **default-off**. Privacy-scale layers
// remain opt-in tradeoffs (latency/CPU for harder fingerprinting).
//
// Residual confidentiality (PFS + ChaCha20-Poly1305) is never “off for speed”.
#pragma once

#include <cstdint>

namespace residual_core {

// Residual UDP port (catalog peers). Prefer this for residual RTT honesty.
inline constexpr int kResidualUdpPort = 44044;

// Product lean defaults (must match Flutter ProductSettings.defaults and
// client.product_policy.PrivacyScalePrefs).
struct LeanResidualDefaults {
  bool traffic_shape = false;
  bool outer_obfuscation = false;
  bool multihop = false;
  // Residual crypto always on for product residual Connect.
  bool require_pfs = true;
  bool require_session_aead = true;
};

// Shipped product defaults for the common residual path.
inline constexpr LeanResidualDefaults kLeanResidualDefaults{};

// True when all privacy-scale residual layers are off (lowest practical
// client residual CPU / hop cost for product default Connect).
inline constexpr bool lean_residual_path_active(
    bool traffic_shape, bool outer_obfuscation, bool multihop) {
  return !traffic_shape && !outer_obfuscation && !multihop;
}

inline constexpr bool lean_residual_path_active(
    const LeanResidualDefaults& d = kLeanResidualDefaults) {
  return lean_residual_path_active(d.traffic_shape, d.outer_obfuscation,
                                   d.multihop);
}

// Product residual rule: packet AEAD must not live on a Dart isolate.
// Documented for hosts; enforced by monorepo structure (see architecture doc).
inline constexpr const char* kNoDartDataplaneRule =
    "Residual IP seal/open belongs in native residual process / residual_core; "
    "Flutter MethodChannel is bridge-only (no Dart UDP AEAD dataplane).";

}  // namespace residual_core
