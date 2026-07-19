/// Durable product settings for seamless power-up preferences.
///
/// Defaults: both **off**. Uses an injectable [SettingsBackend] so unit tests
/// drive the real [SettingsStore.load]/[SettingsStore.save] path.
library;

const String kKeyRunAtStartup = 'run_at_startup';
const String kKeyAutoconnectOnLaunch = 'autoconnect_on_launch';

class ProductSettings {
  final bool runAtStartup;
  final bool autoconnectOnLaunch;

  const ProductSettings({
    this.runAtStartup = false,
    this.autoconnectOnLaunch = false,
  });

  static const ProductSettings defaults = ProductSettings();

  ProductSettings copyWith({
    bool? runAtStartup,
    bool? autoconnectOnLaunch,
  }) {
    return ProductSettings(
      runAtStartup: runAtStartup ?? this.runAtStartup,
      autoconnectOnLaunch: autoconnectOnLaunch ?? this.autoconnectOnLaunch,
    );
  }

  Map<String, dynamic> toJson() => {
        kKeyRunAtStartup: runAtStartup,
        kKeyAutoconnectOnLaunch: autoconnectOnLaunch,
      };

  factory ProductSettings.fromJson(Map<String, dynamic>? data) {
    if (data == null) return defaults;
    return ProductSettings(
      runAtStartup: data[kKeyRunAtStartup] == true,
      autoconnectOnLaunch: data[kKeyAutoconnectOnLaunch] == true,
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
  Future<bool?> getBool(String key) async => data.containsKey(key) ? data[key] : null;

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
    return ProductSettings(
      runAtStartup: run == true,
      autoconnectOnLaunch: auto == true,
    );
  }

  Future<void> save(ProductSettings settings) async {
    await backend.setBool(kKeyRunAtStartup, settings.runAtStartup);
    await backend.setBool(kKeyAutoconnectOnLaunch, settings.autoconnectOnLaunch);
  }

  bool shouldAutoconnectOnLaunch(ProductSettings s) => s.autoconnectOnLaunch;

  bool shouldRunAtStartup(ProductSettings s) => s.runAtStartup;
}
