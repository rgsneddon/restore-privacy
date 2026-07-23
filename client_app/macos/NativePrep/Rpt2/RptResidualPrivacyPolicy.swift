// Residual privacy-scale policy — mirrors Flutter residual_privacy_policy.dart
// and Windows client/product_policy.py defaults.
//
// Keys (App Group + standard UserDefaults):
//   privacy_traffic_shape      (default true)
//   privacy_outer_obfuscation  (default true)
//   privacy_multihop           (default false)
//
// Packet Tunnel calls applyToProductFlags() so residual DATA respects Settings.

import Foundation

public struct RptResidualPrivacyPolicy: Equatable {
  public let trafficShape: Bool
  public let outerObfuscation: Bool
  public let multihop: Bool

  public init(trafficShape: Bool = true, outerObfuscation: Bool = true, multihop: Bool = false) {
    self.trafficShape = trafficShape
    self.outerObfuscation = outerObfuscation
    self.multihop = multihop
  }

  public static let productDefaults = RptResidualPrivacyPolicy()

  /// Pure resolution: optional stored values (nil = product default).
  public static func resolve(
    trafficShape: Bool?,
    outerObfuscation: Bool?,
    multihop: Bool?
  ) -> RptResidualPrivacyPolicy {
    RptResidualPrivacyPolicy(
      trafficShape: trafficShape ?? true,
      outerObfuscation: outerObfuscation ?? true,
      multihop: multihop ?? false
    )
  }

  /// Load from UserDefaults (App Group preferred for Packet Tunnel).
  public static func load(from defaults: UserDefaults) -> RptResidualPrivacyPolicy {
    func optBool(_ key: String) -> Bool? {
      if defaults.object(forKey: key) == nil { return nil }
      return defaults.bool(forKey: key)
    }
    return resolve(
      trafficShape: optBool("privacy_traffic_shape"),
      outerObfuscation: optBool("privacy_outer_obfuscation"),
      multihop: optBool("privacy_multihop")
    )
  }

  public static func loadFromAppGroup(
    appGroupId: String = "group.com.restoreprivacy.shared"
  ) -> RptResidualPrivacyPolicy {
    if let suite = UserDefaults(suiteName: appGroupId) {
      // Prefer suite when any privacy key was written there.
      if suite.object(forKey: "privacy_traffic_shape") != nil
        || suite.object(forKey: "privacy_outer_obfuscation") != nil
        || suite.object(forKey: "privacy_multihop") != nil
      {
        return load(from: suite)
      }
    }
    return load(from: .standard)
  }

  /// Apply to residual product flags used by RptTrafficShape / RptObfuscation.
  public func applyToProductFlags() {
    RptTrafficShape.productPadding = trafficShape
    RptTrafficShape.productCover = trafficShape
    // Jitter only when shaping is on (same product_policy coupling as Windows).
    RptTrafficShape.productJitterMsMax = trafficShape ? 40 : 0
    RptObfuscation.productObfsEnabled = outerObfuscation
  }
}
