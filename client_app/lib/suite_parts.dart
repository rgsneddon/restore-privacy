/// Suite installable parts: VPN always-in; optional % / EVOLVE / rpAI removable.
///
/// Pure policy — unit-tested without widgets. Residual Connect never depends on
/// optional-part install state.
library;

import 'suite_version.dart';

/// Stable identity for each Suite surface.
enum SuitePartId {
  vpn,
  wallet,
  evolve,
  rpai,
}

/// One product part for Settings manage UI and shell destinations.
class SuitePartSpec {
  const SuitePartSpec({
    required this.id,
    required this.label,
    required this.removable,
  });

  final SuitePartId id;
  final String label;

  /// When false, Settings must not offer uninstall (VPN).
  final bool removable;
}

const SuitePartSpec kSuitePartVpn = SuitePartSpec(
  id: SuitePartId.vpn,
  label: kSuiteTabVpn,
  removable: false,
);

const SuitePartSpec kSuitePartWallet = SuitePartSpec(
  id: SuitePartId.wallet,
  label: kSuiteTabWallet,
  removable: true,
);

const SuitePartSpec kSuitePartEvolve = SuitePartSpec(
  id: SuitePartId.evolve,
  label: kSuiteTabEvolve,
  removable: true,
);

const SuitePartSpec kSuitePartRpai = SuitePartSpec(
  id: SuitePartId.rpai,
  label: kSuiteTabRpai,
  removable: true,
);

/// Catalog order: VPN first, then optional parts.
const List<SuitePartSpec> kSuitePartCatalog = [
  kSuitePartVpn,
  kSuitePartWallet,
  kSuitePartEvolve,
  kSuitePartRpai,
];

/// Optional parts only (never includes VPN).
List<SuitePartSpec> suiteOptionalPartSpecs() =>
    kSuitePartCatalog.where((p) => p.removable).toList(growable: false);

bool suitePartIsRemovable(SuitePartId id) {
  for (final p in kSuitePartCatalog) {
    if (p.id == id) return p.removable;
  }
  return false;
}

/// Durable install flags for optional parts. VPN is always installed.
class SuitePartsState {
  const SuitePartsState({
    this.walletInstalled = true,
    this.evolveInstalled = true,
    this.rpaiInstalled = true,
  });

  final bool walletInstalled;
  final bool evolveInstalled;
  final bool rpaiInstalled;

  static const SuitePartsState allInstalled = SuitePartsState();

  /// VPN is always true — never stored as removable.
  bool get vpnInstalled => true;

  bool isInstalled(SuitePartId id) {
    switch (id) {
      case SuitePartId.vpn:
        return true;
      case SuitePartId.wallet:
        return walletInstalled;
      case SuitePartId.evolve:
        return evolveInstalled;
      case SuitePartId.rpai:
        return rpaiInstalled;
    }
  }

  SuitePartsState copyWith({
    bool? walletInstalled,
    bool? evolveInstalled,
    bool? rpaiInstalled,
  }) {
    return SuitePartsState(
      walletInstalled: walletInstalled ?? this.walletInstalled,
      evolveInstalled: evolveInstalled ?? this.evolveInstalled,
      rpaiInstalled: rpaiInstalled ?? this.rpaiInstalled,
    );
  }

  Map<String, bool> toJson() => {
        kKeySuitePartWallet: walletInstalled,
        kKeySuitePartEvolve: evolveInstalled,
        kKeySuitePartRpai: rpaiInstalled,
      };

  factory SuitePartsState.fromJson(Map<String, dynamic>? data) {
    if (data == null) return allInstalled;
    // Missing key → installed (upgrade path keeps prior full Suite).
    bool on(Object? v) => v != false;
    return SuitePartsState(
      walletInstalled: on(data[kKeySuitePartWallet]),
      evolveInstalled: on(data[kKeySuitePartEvolve]),
      rpaiInstalled: on(data[kKeySuitePartRpai]),
    );
  }

  @override
  bool operator ==(Object other) =>
      other is SuitePartsState &&
      other.walletInstalled == walletInstalled &&
      other.evolveInstalled == evolveInstalled &&
      other.rpaiInstalled == rpaiInstalled;

  @override
  int get hashCode =>
      Object.hash(walletInstalled, evolveInstalled, rpaiInstalled);
}

const String kKeySuitePartWallet = 'suite_part_wallet_installed';
const String kKeySuitePartEvolve = 'suite_part_evolve_installed';
const String kKeySuitePartRpai = 'suite_part_rpai_installed';

const String kSuitePartsSettingsTitle = 'Suite parts';
const String kSuitePartsSettingsSubtitle =
    'Remove surfaces you do not use. Residual VPN always stays installed.';
const String kSuitePartVpnRequiredLabel = 'Required — always installed';
const String kSuitePartInstalledLabel = 'Installed';
const String kSuitePartRemovedLabel = 'Removed';
const String kSuitePartUninstallLabel = 'Remove';
const String kSuitePartRetainLabel = 'Keep installed';
const String kSuitePartReinstallLabel = 'Reinstall';

/// Apply remove/retain. VPN requests are ignored (always installed).
SuitePartsState applySuitePartInstall(
  SuitePartsState current, {
  required SuitePartId id,
  required bool installed,
}) {
  if (id == SuitePartId.vpn || !suitePartIsRemovable(id)) {
    return current;
  }
  switch (id) {
    case SuitePartId.vpn:
      return current;
    case SuitePartId.wallet:
      return current.copyWith(walletInstalled: installed);
    case SuitePartId.evolve:
      return current.copyWith(evolveInstalled: installed);
    case SuitePartId.rpai:
      return current.copyWith(rpaiInstalled: installed);
  }
}

/// Ordered list of parts that should appear in the shell navigation.
List<SuitePartId> visibleSuitePartIds(SuitePartsState state) {
  final out = <SuitePartId>[SuitePartId.vpn];
  if (state.walletInstalled) out.add(SuitePartId.wallet);
  if (state.evolveInstalled) out.add(SuitePartId.evolve);
  if (state.rpaiInstalled) out.add(SuitePartId.rpai);
  return out;
}

String suitePartLabel(SuitePartId id) {
  for (final p in kSuitePartCatalog) {
    if (p.id == id) return p.label;
  }
  return id.name;
}

/// Clamp tab index into the visible destinations list.
int clampSuiteTabIndex(int index, SuitePartsState state) {
  final n = visibleSuitePartIds(state).length;
  if (n <= 0) return 0;
  if (index < 0) return 0;
  if (index >= n) return n - 1;
  return index;
}
