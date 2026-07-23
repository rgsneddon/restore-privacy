/// Durable product settings for seamless power-up + privacy-scale prefs.
///
/// Defaults: startup prefs **off**. Privacy-scale: traffic shaping + outer
/// obfuscation **on**; multi-hop **off** (matches Windows product policy).
library;

const String kKeyRunAtStartup = 'run_at_startup';
const String kKeyAutoconnectOnLaunch = 'autoconnect_on_launch';
const String kKeyPrivacyTrafficShape = 'privacy_traffic_shape';
const String kKeyPrivacyOuterObfuscation = 'privacy_outer_obfuscation';
const String kKeyPrivacyMultihop = 'privacy_multihop';

class ProductSettings {
  final bool runAtStartup;
  final bool autoconnectOnLaunch;
  final bool privacyTrafficShape;
  final bool privacyOuterObfuscation;
  final bool privacyMultihop;

  const ProductSettings({
    this.runAtStartup = false,
    this.autoconnectOnLaunch = false,
    this.privacyTrafficShape = true,
    this.privacyOuterObfuscation = true,
    this.privacyMultihop = false,
  });

  static const ProductSettings defaults = ProductSettings();

  ProductSettings copyWith({
    bool? runAtStartup,
    bool? autoconnectOnLaunch,
    bool? privacyTrafficShape,
    bool? privacyOuterObfuscation,
    bool? privacyMultihop,
  }) {
    return ProductSettings(
      runAtStartup: runAtStartup ?? this.runAtStartup,
      autoconnectOnLaunch: autoconnectOnLaunch ?? this.autoconnectOnLaunch,
      privacyTrafficShape: privacyTrafficShape ?? this.privacyTrafficShape,
      privacyOuterObfuscation:
          privacyOuterObfuscation ?? this.privacyOuterObfuscation,
      privacyMultihop: privacyMultihop ?? this.privacyMultihop,
    );
  }

  Map<String, dynamic> toJson() => {
        kKeyRunAtStartup: runAtStartup,
        kKeyAutoconnectOnLaunch: autoconnectOnLaunch,
        kKeyPrivacyTrafficShape: privacyTrafficShape,
        kKeyPrivacyOuterObfuscation: privacyOuterObfuscation,
        kKeyPrivacyMultihop: privacyMultihop,
      };

  factory ProductSettings.fromJson(Map<String, dynamic>? data) {
    if (data == null) return defaults;
    return ProductSettings(
      runAtStartup: data[kKeyRunAtStartup] == true,
      autoconnectOnLaunch: data[kKeyAutoconnectOnLaunch] == true,
      privacyTrafficShape: data[kKeyPrivacyTrafficShape] != false,
      privacyOuterObfuscation: data[kKeyPrivacyOuterObfuscation] != false,
      privacyMultihop: data[kKeyPrivacyMultihop] == true,
    );
  }
}

abstract class SettingsBackend {
  Future<bool?> getBool(String key);
  Future<void> setBool(String key, bool value);
}

/// In-memory backend — tests pass a shared map to simulate process restart.
class MemorySettingsBackend implements SettingsBackend {
  MemorySettingsBackend([Map<String, bool>? seed]) : data = seed ?? {};

  final Map<String, bool> data;

  @override
  Future<bool?> getBool(String key) async =>
      data.containsKey(key) ? data[key] : null;

  @override
  Future<void> setBool(String key, bool value) async {
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
    return ProductSettings(
      runAtStartup: run == true,
      autoconnectOnLaunch: auto == true,
      // Defaults ON when never set (null) — product privacy-max for shape/obfs.
      privacyTrafficShape: shape != false,
      privacyOuterObfuscation: obfs != false,
      privacyMultihop: mh == true,
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
  }

  bool shouldAutoconnectOnLaunch(ProductSettings s) => s.autoconnectOnLaunch;

  bool shouldRunAtStartup(ProductSettings s) => s.runAtStartup;
}
