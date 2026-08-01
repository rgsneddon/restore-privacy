/// Durable Suite part install flags (optional surfaces only).
library;

import 'settings_store.dart';
import 'suite_parts.dart';

/// Loads/saves [SuitePartsState] via [SettingsBackend].
class SuitePartsStore {
  SuitePartsStore(this.backend);

  final SettingsBackend backend;

  Future<SuitePartsState> load() async {
    final w = await backend.getBool(kKeySuitePartWallet);
    final e = await backend.getBool(kKeySuitePartEvolve);
    final r = await backend.getBool(kKeySuitePartRpai);
    return SuitePartsState(
      walletInstalled: w != false,
      evolveInstalled: e != false,
      rpaiInstalled: r != false,
    );
  }

  Future<void> save(SuitePartsState state) async {
    // Never persist a "vpn off" flag — VPN is not optional.
    await backend.setBool(kKeySuitePartWallet, state.walletInstalled);
    await backend.setBool(kKeySuitePartEvolve, state.evolveInstalled);
    await backend.setBool(kKeySuitePartRpai, state.rpaiInstalled);
  }

  /// Set one optional part; VPN is a no-op. Returns the new state.
  ///
  /// Uninstall requires [confirmPhrase] matching the part label exactly.
  /// Reinstall does not require confirmation or a new KEYGEN/register wall.
  Future<SuitePartsState> setInstalled(
    SuitePartId id,
    bool installed, {
    String? confirmPhrase,
  }) async {
    final cur = await load();
    final next = applySuitePartInstall(
      cur,
      id: id,
      installed: installed,
      confirmPhrase: confirmPhrase,
    );
    if (next != cur) {
      await save(next);
    }
    return next;
  }
}
