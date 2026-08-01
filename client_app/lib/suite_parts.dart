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
    'Uninstall optional surfaces you do not use — tabs stay with a reinstall '
    'link. Residual VPN always stays installed. Type the part name to confirm.';
const String kSuitePartVpnRequiredLabel = 'Required — always installed';
const String kSuitePartInstalledLabel = 'Installed';
const String kSuitePartRemovedLabel = 'Uninstalled — tab shows reinstall';
const String kSuitePartUninstallLabel = 'Uninstall…';
const String kSuitePartRetainLabel = 'Keep installed';
const String kSuitePartReinstallLabel = 'Reinstall this section';
const String kSuitePartReinstallTitle = 'Section uninstalled';
const String kSuitePartReinstallBody =
    'This Suite section is uninstalled on this device. Your residual VPN licence '
    '(KEYGEN) and any Suite account registration stay on device — reinstalling '
    'does not require a second KEYGEN unlock or a second full register solely '
    'because this section was removed.';
const String kSuitePartConfirmDialogTitle = 'Confirm uninstall';
const String kSuitePartConfirmHintPrefix =
    'Type the exact part name to confirm deletion:';
const String kSuitePartConfirmAbortNote =
    'Wrong or empty confirmation aborts — nothing is uninstalled.';
const String kSuitePartConfirmCancelLabel = 'Cancel';
const String kSuitePartConfirmProceedLabel = 'Uninstall';

/// Exact confirmation phrase for a part (rpOS RESTORE-style gate).
///
/// User must type this string exactly (after trim). VPN has no phrase.
String suitePartConfirmPhrase(SuitePartId id) => suitePartLabel(id);

/// Pure gate: uninstall may proceed only when typed phrase matches part name.
bool suitePartUninstallConfirmationAccepted({
  required SuitePartId id,
  required String? userInput,
}) {
  if (!suitePartIsRemovable(id)) return false;
  final expected = suitePartConfirmPhrase(id);
  final phrase = (userInput ?? '').trim();
  if (phrase.isEmpty) return false;
  return phrase == expected;
}

/// Result of evaluating uninstall confirmation (mirrors rpOS gate shape).
class SuitePartUninstallGateResult {
  const SuitePartUninstallGateResult({
    required this.allowed,
    required this.reason,
  });

  final bool allowed;
  final String reason;

  static const rejectedNotRemovable = SuitePartUninstallGateResult(
    allowed: false,
    reason: 'part_not_removable',
  );
  static const rejectedEmpty = SuitePartUninstallGateResult(
    allowed: false,
    reason: 'confirmation_empty',
  );
  static const rejectedMismatch = SuitePartUninstallGateResult(
    allowed: false,
    reason: 'confirmation_rejected',
  );
  static const accepted = SuitePartUninstallGateResult(
    allowed: true,
    reason: 'confirmation_accepted',
  );
}

SuitePartUninstallGateResult evaluateSuitePartUninstallConfirmation({
  required SuitePartId id,
  required String? userInput,
}) {
  if (!suitePartIsRemovable(id)) {
    return SuitePartUninstallGateResult.rejectedNotRemovable;
  }
  final phrase = (userInput ?? '').trim();
  if (phrase.isEmpty) return SuitePartUninstallGateResult.rejectedEmpty;
  if (phrase != suitePartConfirmPhrase(id)) {
    return SuitePartUninstallGateResult.rejectedMismatch;
  }
  return SuitePartUninstallGateResult.accepted;
}

/// Apply remove/retain. VPN requests are ignored (always installed).
///
/// Uninstall (`installed: false`) requires [confirmPhrase] to pass the typed
/// part-name gate; mismatch leaves state unchanged.
SuitePartsState applySuitePartInstall(
  SuitePartsState current, {
  required SuitePartId id,
  required bool installed,
  String? confirmPhrase,
}) {
  if (id == SuitePartId.vpn || !suitePartIsRemovable(id)) {
    return current;
  }
  if (!installed) {
    final gate = evaluateSuitePartUninstallConfirmation(
      id: id,
      userInput: confirmPhrase,
    );
    if (!gate.allowed) return current;
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

/// Shell always retains every Suite tab (including uninstalled optionals).
///
/// Uninstalled optionals show a reinstall placeholder body — not a missing tab.
List<SuitePartId> visibleSuitePartIds(SuitePartsState state) {
  // state is unused: tabs always retained. Signature kept for call-site stability.
  assert(state.vpnInstalled);
  return const [
    SuitePartId.vpn,
    SuitePartId.wallet,
    SuitePartId.evolve,
    SuitePartId.rpai,
  ];
}

/// True when the shell should mount the full feature surface (not placeholder).
bool suitePartShowsFullSurface(SuitePartsState state, SuitePartId id) {
  return state.isInstalled(id);
}

String suitePartLabel(SuitePartId id) {
  for (final p in kSuitePartCatalog) {
    if (p.id == id) return p.label;
  }
  return id.name;
}

/// Clamp tab index into the (always full) destinations list.
int clampSuiteTabIndex(int index, SuitePartsState state) {
  final n = visibleSuitePartIds(state).length;
  if (n <= 0) return 0;
  if (index < 0) return 0;
  if (index >= n) return n - 1;
  return index;
}
