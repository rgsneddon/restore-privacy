/// Durable product settings for seamless power-up + privacy-scale prefs.
///
/// Defaults: startup prefs **off**. Privacy-scale lean residual: traffic
/// shaping, outer obfuscation, and multi-hop all **off** until the user opts
/// in (matches Windows/Linux product policy). Residual VPN core stays always-on.
/// Residual **IPv4** is always ON (not user-adjustable). Residual **IPv6**
/// defaults ON and remains adjustable.
/// Entry country defaults to United States (`US`) on every client.
library;

import 'country_select.dart';

const String kKeyRunAtStartup = 'run_at_startup';
const String kKeyAutoconnectOnLaunch = 'autoconnect_on_launch';
const String kKeyPrivacyTrafficShape = 'privacy_traffic_shape';
const String kKeyPrivacyOuterObfuscation = 'privacy_outer_obfuscation';
const String kKeyPrivacyMultihop = 'privacy_multihop';
/// Residual IPv4 full-tunnel capture (dual /1). Always ON (product policy).
const String kKeyResidualIpv4 = 'residual_ipv4';
/// Residual IPv6 ISP-leak protection while residual is up. Default ON when unset.
const String kKeyResidualIpv6 = 'residual_ipv6';
const String kKeyEntryCountry = 'entry_country';

class ProductSettings {
  final bool runAtStartup;
  final bool autoconnectOnLaunch;
  final bool privacyTrafficShape;
  final bool privacyOuterObfuscation;
  final bool privacyMultihop;
  /// Residual IPv4 capture path (full-tunnel dual /1). Always ON (product policy).
  final bool residualIpv4;
  /// Residual IPv6 ISP path block while residual is up. Product default ON.
  final bool residualIpv6;
  /// Catalog entry country code (US / IS / RO); default United States/US.
  final String entryCountry;

  const ProductSettings({
    this.runAtStartup = false,
    this.autoconnectOnLaunch = false,
    this.privacyTrafficShape = false,
    this.privacyOuterObfuscation = false,
    this.privacyMultihop = false,
    // residualIpv4 ignored for policy — always treated as true by load/save.
    this.residualIpv4 = true,
    this.residualIpv6 = true,
    this.entryCountry = kDefaultEntryCountry,
  });

  static const ProductSettings defaults = ProductSettings();

  ProductSettings copyWith({
    bool? runAtStartup,
    bool? autoconnectOnLaunch,
    bool? privacyTrafficShape,
    bool? privacyOuterObfuscation,
    bool? privacyMultihop,
    bool? residualIpv4,
    bool? residualIpv6,
    String? entryCountry,
  }) {
    return ProductSettings(
      runAtStartup: runAtStartup ?? this.runAtStartup,
      autoconnectOnLaunch: autoconnectOnLaunch ?? this.autoconnectOnLaunch,
      privacyTrafficShape: privacyTrafficShape ?? this.privacyTrafficShape,
      privacyOuterObfuscation:
          privacyOuterObfuscation ?? this.privacyOuterObfuscation,
      privacyMultihop: privacyMultihop ?? this.privacyMultihop,
      // IPv4 residual is product-forced ON (ignore residualIpv4: false).
      residualIpv4: true,
      residualIpv6: residualIpv6 ?? this.residualIpv6,
      entryCountry: entryCountry != null
          ? normalizeEntryCountry(entryCountry)
          : this.entryCountry,
    );
  }

  Map<String, dynamic> toJson() => {
        kKeyRunAtStartup: runAtStartup,
        kKeyAutoconnectOnLaunch: autoconnectOnLaunch,
        kKeyPrivacyTrafficShape: privacyTrafficShape,
        kKeyPrivacyOuterObfuscation: privacyOuterObfuscation,
        kKeyPrivacyMultihop: privacyMultihop,
        kKeyResidualIpv4: true,
        kKeyResidualIpv6: residualIpv6,
        kKeyEntryCountry: normalizeEntryCountry(entryCountry),
      };

  factory ProductSettings.fromJson(Map<String, dynamic>? data) {
    if (data == null) return defaults;
    // IPv6: missing key → ON; IPv4 always ON (legacy false ignored).
    bool dualOn(Object? v) => v != false;
    return ProductSettings(
      runAtStartup: data[kKeyRunAtStartup] == true,
      autoconnectOnLaunch: data[kKeyAutoconnectOnLaunch] == true,
      privacyTrafficShape: data[kKeyPrivacyTrafficShape] == true,
      privacyOuterObfuscation: data[kKeyPrivacyOuterObfuscation] == true,
      privacyMultihop: data[kKeyPrivacyMultihop] == true,
      residualIpv4: true,
      residualIpv6: !data.containsKey(kKeyResidualIpv6) || dualOn(data[kKeyResidualIpv6]),
      entryCountry: normalizeEntryCountry(
        data[kKeyEntryCountry]?.toString(),
      ),
    );
  }
}

abstract class SettingsBackend {
  Future<bool?> getBool(String key);
  Future<void> setBool(String key, bool value);
  Future<String?> getString(String key);
  Future<void> setString(String key, String value);
}

/// In-memory backend — tests pass a shared map to simulate process restart.
class MemorySettingsBackend implements SettingsBackend {
  MemorySettingsBackend([Map<String, dynamic>? seed])
      : data = seed ?? <String, Object?>{};

  /// Shared map (same instance when [seed] is passed — process-restart tests).
  final Map<String, dynamic> data;

  @override
  Future<bool?> getBool(String key) async {
    final v = data[key];
    if (v is bool) return v;
    return null;
  }

  @override
  Future<void> setBool(String key, bool value) async {
    data[key] = value;
  }

  @override
  Future<String?> getString(String key) async {
    final v = data[key];
    if (v is String) return v;
    return null;
  }

  @override
  Future<void> setString(String key, String value) async {
    data[key] = value;
  }
}

class SettingsStore {
  SettingsStore(this.backend);

  final SettingsBackend backend;

  Future<ProductSettings> load() async {
    final run = await backend.getBool(kKeyRunAtStartup);
    final auto = await backend.getBool(kKeyAutoconnectOnLaunch);
    final shape = await backend.getBool(kKeyPrivacyTrafficShape);
    final obfs = await backend.getBool(kKeyPrivacyOuterObfuscation);
    final mh = await backend.getBool(kKeyPrivacyMultihop);
    // residual_ipv4 key may still exist in storage; product policy always ON.
    final ipv6 = await backend.getBool(kKeyResidualIpv6);
    final entry = await backend.getString(kKeyEntryCountry);
    return ProductSettings(
      runAtStartup: run == true,
      autoconnectOnLaunch: auto == true,
      privacyTrafficShape: shape == true,
      privacyOuterObfuscation: obfs == true,
      privacyMultihop: mh == true,
      // Product policy: residual IPv4 always ON (legacy false ignored).
      residualIpv4: true,
      // null (missing) → product default ON for IPv6
      residualIpv6: ipv6 != false,
      entryCountry: normalizeEntryCountry(entry),
    );
  }

  Future<void> save(ProductSettings settings) async {
    await backend.setBool(kKeyRunAtStartup, settings.runAtStartup);
    await backend.setBool(kKeyAutoconnectOnLaunch, settings.autoconnectOnLaunch);
    await backend.setBool(kKeyPrivacyTrafficShape, settings.privacyTrafficShape);
    await backend.setBool(
      kKeyPrivacyOuterObfuscation,
      settings.privacyOuterObfuscation,
    );
    await backend.setBool(kKeyPrivacyMultihop, settings.privacyMultihop);
    // Always persist residual IPv4 ON (product policy).
    await backend.setBool(kKeyResidualIpv4, true);
    await backend.setBool(kKeyResidualIpv6, settings.residualIpv6);
    await backend.setString(
      kKeyEntryCountry,
      normalizeEntryCountry(settings.entryCountry),
    );
  }

  bool shouldAutoconnectOnLaunch(ProductSettings s) => s.autoconnectOnLaunch;

  bool shouldRunAtStartup(ProductSettings s) => s.runAtStartup;
}
