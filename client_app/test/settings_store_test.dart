import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/settings_store.dart';

void main() {
  test('defaults: startup off, privacy-scale lean off, dual-stack ON, US entry', () {
    const s = ProductSettings.defaults;
    expect(s.runAtStartup, isFalse);
    expect(s.autoconnectOnLaunch, isFalse);
    expect(s.privacyTrafficShape, isFalse);
    expect(s.privacyOuterObfuscation, isFalse);
    expect(s.privacyMultihop, isFalse);
    expect(s.residualIpv4, isTrue);
    expect(s.residualIpv6, isTrue);
    expect(s.entryCountry, 'US');
  });

  test('save and load roundtrip via real SettingsStore API', () async {
    final shared = <String, dynamic>{};
    final store = SettingsStore(MemorySettingsBackend(shared));

    await store.save(
      const ProductSettings(runAtStartup: true, autoconnectOnLaunch: true),
    );
    final loaded = await store.load();
    expect(loaded.runAtStartup, isTrue);
    expect(loaded.autoconnectOnLaunch, isTrue);
    // Privacy lean-off defaults when never written for shape/obfs/multihop
    // (save writes explicit false for those fields from ProductSettings ctor defaults)
    expect(loaded.privacyTrafficShape, isFalse);
    expect(loaded.privacyOuterObfuscation, isFalse);
    expect(loaded.privacyMultihop, isFalse);

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

  test('missing keys load as lean-off privacy + dual-stack ON', () async {
    final empty = SettingsStore(MemorySettingsBackend({}));
    final loaded = await empty.load();
    expect(loaded.runAtStartup, isFalse);
    expect(loaded.autoconnectOnLaunch, isFalse);
    expect(loaded.privacyTrafficShape, isFalse);
    expect(loaded.privacyOuterObfuscation, isFalse);
    expect(loaded.privacyMultihop, isFalse);
    expect(loaded.residualIpv4, isTrue);
    expect(loaded.residualIpv6, isTrue);
    expect(loaded.entryCountry, 'US');
  });

  test('residual IPv4/IPv6 dual-stack prefs roundtrip independently', () async {
    final shared = <String, dynamic>{};
    final store = SettingsStore(MemorySettingsBackend(shared));
    await store.save(
      const ProductSettings(residualIpv4: false, residualIpv6: true),
    );
    final loaded = await store.load();
    expect(loaded.residualIpv4, isFalse);
    expect(loaded.residualIpv6, isTrue);
    expect(shared[kKeyResidualIpv4], isFalse);
    expect(shared[kKeyResidualIpv6], isTrue);
    await store.save(
      const ProductSettings(residualIpv4: true, residualIpv6: false),
    );
    final again = await SettingsStore(MemorySettingsBackend(shared)).load();
    expect(again.residualIpv4, isTrue);
    expect(again.residualIpv6, isFalse);
  });

  test('privacy-scale prefs roundtrip (Windows parity keys)', () async {
    final shared = <String, dynamic>{};
    final store = SettingsStore(MemorySettingsBackend(shared));
    await store.save(
      const ProductSettings(
        privacyTrafficShape: true,
        privacyOuterObfuscation: true,
        privacyMultihop: true,
        entryCountry: 'RO',
      ),
    );
    final loaded = await store.load();
    expect(loaded.privacyTrafficShape, isTrue);
    expect(loaded.privacyOuterObfuscation, isTrue);
    expect(loaded.privacyMultihop, isTrue);
    expect(loaded.entryCountry, 'RO');
    expect(shared[kKeyPrivacyTrafficShape], isTrue);
    expect(shared[kKeyPrivacyOuterObfuscation], isTrue);
    expect(shared[kKeyPrivacyMultihop], isTrue);
    expect(shared[kKeyEntryCountry], 'RO');
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
