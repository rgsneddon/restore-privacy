import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/settings_store.dart';

void main() {
  test('defaults are both off', () {
    const s = ProductSettings.defaults;
    expect(s.runAtStartup, isFalse);
    expect(s.autoconnectOnLaunch, isFalse);
  });

  test('save and load roundtrip via real SettingsStore API', () async {
    final shared = <String, bool>{};
    final store = SettingsStore(MemorySettingsBackend(shared));

    await store.save(
      const ProductSettings(runAtStartup: true, autoconnectOnLaunch: true),
    );
    final loaded = await store.load();
    expect(loaded.runAtStartup, isTrue);
    expect(loaded.autoconnectOnLaunch, isTrue);

    // Simulate process restart: new store, same backend map
    final store2 = SettingsStore(MemorySettingsBackend(shared));
    final again = await store2.load();
    expect(again.runAtStartup, isTrue);
    expect(again.autoconnectOnLaunch, isTrue);

    await store2.save(
      const ProductSettings(runAtStartup: false, autoconnectOnLaunch: true),
    );
    final third = await SettingsStore(MemorySettingsBackend(shared)).load();
    expect(third.runAtStartup, isFalse);
    expect(third.autoconnectOnLaunch, isTrue);
  });

  test('shouldAutoconnect helpers', () {
    final store = SettingsStore(MemorySettingsBackend());
    expect(
      store.shouldAutoconnectOnLaunch(
        const ProductSettings(autoconnectOnLaunch: true),
      ),
      isTrue,
    );
    expect(
      store.shouldAutoconnectOnLaunch(ProductSettings.defaults),
      isFalse,
    );
    expect(
      store.shouldRunAtStartup(const ProductSettings(runAtStartup: true)),
      isTrue,
    );
  });
}
