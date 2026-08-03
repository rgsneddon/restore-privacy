/// Durable Suite part install flags (optional surfaces only).
///
/// Product path is residual VPN only: [load] always resolves to
/// [SuitePartsState.vpnOnly]. Optional Suite family install flags are not
/// product chrome (write path retained for migration / pure unit tests).
library;

import 'settings_store.dart';
import 'suite_parts.dart';

/// Loads/saves [SuitePartsState] via [SettingsBackend].
class SuitePartsStore {
  SuitePartsStore(this.backend);

  final SettingsBackend backend;

  /// Product: residual VPN only — optional Suite family parts never on.
  Future<SuitePartsState> load() async {
    // Still touch keys so migration/uninstall paths can clear legacy values.
    final _ = await backend.getBool(kKeySuitePartWallet);
    final __ = await backend.getBool(kKeySuitePartEvolve);
    final ___ = await backend.getBool(kKeySuitePartRpai);
    return SuitePartsState.vpnOnly;
  }

  Future<void> save(SuitePartsState state) async {
    // Persist VPN-only product posture (optional parts always off).
    await backend.setBool(kKeySuitePartWallet, false);
    await backend.setBool(kKeySuitePartEvolve, false);
    await backend.setBool(kKeySuitePartRpai, false);
    final _ = state;
  }

  /// Set one optional part; product always stays VPN-only after save.
  ///
  /// Uninstall requires [confirmPhrase] matching the part label exactly for
  /// pure apply path; load still returns [SuitePartsState.vpnOnly].
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
    await save(SuitePartsState.vpnOnly);
    final _ = next;
    return SuitePartsState.vpnOnly;
  }
}
