import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/connect_status.dart';
import 'package:restore_privacy_client/settings_store.dart';

void main() {
  test('defaults: startup off, privacy-scale lean off, IPv4 always on, IPv6 ON, DE entry',
      () {
    const s = ProductSettings.defaults;
    expect(s.runAtStartup, isFalse);
    expect(s.autoconnectOnLaunch, isFalse);
    expect(s.privacyTrafficShape, isFalse);
    expect(s.privacyOuterObfuscation, isFalse);
    expect(s.privacyMultihop, isFalse);
    expect(s.residualIpv4, isTrue);
    expect(s.residualIpv4, kResidualIpv4AlwaysOn);
    expect(s.residualIpv6, isTrue);
    expect(s.entryCountry, 'DE');
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
    expect(loaded.privacyTrafficShape, isFalse);
    expect(loaded.privacyOuterObfuscation, isFalse);
    expect(loaded.privacyMultihop, isFalse);
    expect(loaded.residualIpv4, isTrue);

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

  test('missing keys load as lean-off privacy + IPv4 always on + IPv6 ON',
      () async {
    final empty = SettingsStore(MemorySettingsBackend({}));
    final loaded = await empty.load();
    expect(loaded.runAtStartup, isFalse);
    expect(loaded.autoconnectOnLaunch, isFalse);
    expect(loaded.privacyTrafficShape, isFalse);
    expect(loaded.privacyOuterObfuscation, isFalse);
    expect(loaded.privacyMultihop, isFalse);
    expect(loaded.residualIpv4, isTrue);
    expect(loaded.residualIpv6, isTrue);
    expect(loaded.entryCountry, 'DE');
  });

  test('residual IPv4 always ON even when stale false key is stored', () async {
    final shared = <String, dynamic>{
      kKeyResidualIpv4: false,
      kKeyResidualIpv6: true,
    };
    final store = SettingsStore(MemorySettingsBackend(shared));
    final loaded = await store.load();
    expect(loaded.residualIpv4, isTrue);
    expect(loaded.residualIpv6, isTrue);

    // copyWith cannot turn IPv4 off.
    final forced = loaded.copyWith(residualIpv4: false, residualIpv6: false);
    expect(forced.residualIpv4, isTrue);
    expect(forced.residualIpv6, isFalse);

    await store.save(forced);
    expect(shared[kKeyResidualIpv4], isTrue);
    expect(shared[kKeyResidualIpv6], isFalse);
    final again = await store.load();
    expect(again.residualIpv4, isTrue);
    expect(again.residualIpv6, isFalse);
  });

  test('residual IPv6 toggle roundtrip while IPv4 stays always on', () async {
    final shared = <String, dynamic>{};
    final store = SettingsStore(MemorySettingsBackend(shared));
    await store.save(
      const ProductSettings(residualIpv6: false),
    );
    final loaded = await store.load();
    expect(loaded.residualIpv4, isTrue);
    expect(loaded.residualIpv6, isFalse);
    expect(shared[kKeyResidualIpv4], isTrue);
    expect(shared[kKeyResidualIpv6], isFalse);
    await store.save(
      const ProductSettings(residualIpv6: true),
    );
    final again = await SettingsStore(MemorySettingsBackend(shared)).load();
    expect(again.residualIpv4, isTrue);
    expect(again.residualIpv6, isTrue);
  });

  test('privacy-scale prefs roundtrip (Windows parity keys)', () async {
    final shared = <String, dynamic>{};
    final store = SettingsStore(MemorySettingsBackend(shared));
    await store.save(
      const ProductSettings(
        privacyTrafficShape: true,
        privacyOuterObfuscation: true,
        privacyMultihop: true,
        entryCountry: 'IS',
      ),
    );
    final loaded = await store.load();
    expect(loaded.privacyTrafficShape, isTrue);
    expect(loaded.privacyOuterObfuscation, isTrue);
    expect(loaded.privacyMultihop, isTrue);
    // Catalog is IS/DE only (stale US normalizes to DE).
    expect(loaded.entryCountry, 'IS');
    expect(shared[kKeyPrivacyTrafficShape], isTrue);
    expect(shared[kKeyPrivacyOuterObfuscation], isTrue);
    expect(shared[kKeyPrivacyMultihop], isTrue);
    expect(shared[kKeyEntryCountry], 'IS');
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

  test('product Settings path: IPv4 always on + residual IPv6 ON/OFF honesty',
      () async {
    final shared = <String, dynamic>{};
    final store = SettingsStore(MemorySettingsBackend(shared));
    await store.save(
      const ProductSettings(residualIpv6: false),
    );
    final s = await store.load();
    expect(s.residualIpv4, isTrue);
    expect(s.residualIpv6, isFalse);
    final map = buildFullTunnelConnectResult(
      packetTunnelActive: true,
      vpnIp: '10.88.0.40',
      ipv6Protected: s.residualIpv6,
      ipv4Residual: s.residualIpv4,
    );
    final msg = mapConnectStatusMessage(map);
    expect(msg.toLowerCase(), contains('ipv6 not protected'));
    expect(msg.toLowerCase(), isNot(contains('path blocked')));
    expect(msg.toLowerCase(), isNot(contains('ipv4 residual off')));
    expect(msg.toLowerCase(), isNot(contains('dual-stack off')));

    await store.save(const ProductSettings(residualIpv6: true));
    final on = await store.load();
    final mapOn = buildFullTunnelConnectResult(
      packetTunnelActive: true,
      vpnIp: '10.88.0.41',
      ipv6Protected: on.residualIpv6,
      ipv4Residual: on.residualIpv4,
    );
    final msgOn = mapConnectStatusMessage(mapOn);
    expect(msgOn.toLowerCase(), contains('ipv6 isp path blocked'));
    expect(msgOn.toLowerCase(), isNot(contains('ipv6 not protected')));

    // Connect UI path uses always-on IPv4.
    final ui = resolveConnectedStatusAfterSuccess(
      nativeStatus: msg,
      vpnIp: '10.88.0.40',
      residualIpv4: kResidualIpv4AlwaysOn,
      residualIpv6: s.residualIpv6,
    );
    expect(ui.toLowerCase(), contains('ipv6 not protected'));
    expect(ui.toLowerCase(), isNot(contains('ipv4 residual off')));
  });
}
