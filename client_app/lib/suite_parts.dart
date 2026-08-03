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
///
/// Product dedicated VPN app: optional Suite family parts are **never** on for
/// product chrome. Stored prefs may still record values for migration, but
/// [fromJson] and defaults resolve to [vpnOnly].
class SuitePartsState {
  const SuitePartsState({
    this.walletInstalled = false,
    this.evolveInstalled = false,
    this.rpaiInstalled = false,
  });

  final bool walletInstalled;
  final bool evolveInstalled;
  final bool rpaiInstalled;

  /// Historical full-Suite snapshot (tests / migration fixtures only).
  /// Product chrome never mounts these — see [suiteNavDestinations].
  static const SuitePartsState allInstalled = SuitePartsState(
    walletInstalled: true,
    evolveInstalled: true,
    rpaiInstalled: true,
  );

  /// Historical VPN+rpAI snapshot (tests only — not product default).
  static const SuitePartsState vpnAndRpai = SuitePartsState(
    walletInstalled: false,
    evolveInstalled: false,
    rpaiInstalled: true,
  );

  /// Product default: residual VPN only.
  static const SuitePartsState vpnOnly = SuitePartsState(
    walletInstalled: false,
    evolveInstalled: false,
    rpaiInstalled: false,
  );

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

  /// Parse durable map — product always resolves to [vpnOnly].
  factory SuitePartsState.fromJson(Map<String, dynamic>? data) {
    final _ = data;
    return vpnOnly;
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

const String kSuitePartsSettingsTitle = 'Product';
const String kSuitePartsSettingsSubtitle =
    'This app is Restore Privacy residual VPN only. Optional Suite family '
    'parts (%, EVOLVE, rpAI, Backup) are not product chrome and cannot be '
    'installed from this build. Residual VPN is always available after '
    'licence + KEYGEN or free trial.';
const String kSuitePartVpnRequiredLabel = 'Required — always installed';
const String kSuitePartInstalledLabel = 'Installed';
const String kSuitePartRemovedLabel = 'Not installed — use Install to add to the main bar';
const String kSuitePartUninstallLabel = 'Uninstall…';
const String kSuitePartRetainLabel = 'Keep installed';
const String kSuitePartInstallLabel = 'Install';
const String kSuitePartReinstallLabel = 'Install this section';
const String kSuitePartReinstallTitle = 'Section not installed';
const String kSuitePartReinstallBody =
    'This Suite section is not installed on this device. Your residual VPN '
    'licence (KEYGEN) and any Suite account registration stay on device — '
    'installing does not require a second KEYGEN unlock or a second full '
    'register solely because this section was not installed yet.';
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

/// Product-part ids that are installed (VPN always; optionals only when on).
///
/// Main-bar chrome uses [suiteNavDestinations] (flat family promotion). This
/// list is the coarse install set for Settings / placeholder paths.
List<SuitePartId> visibleSuitePartIds(SuitePartsState state) {
  assert(state.vpnInstalled);
  final out = <SuitePartId>[SuitePartId.vpn];
  if (state.walletInstalled) out.add(SuitePartId.wallet);
  if (state.evolveInstalled) out.add(SuitePartId.evolve);
  if (state.rpaiInstalled) out.add(SuitePartId.rpai);
  return List<SuitePartId>.unmodifiable(out);
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

/// Ordered swipe destinations: **VPN → % → EVOLVE → rpAI** (end blocks).
///
/// [destinationCount] is the number of visible shell pages (normally 4).
/// End blocks: cannot go before VPN (0) or past the last page (rpAI).
int suiteSwipeNextIndex(int current, int destinationCount) {
  if (destinationCount <= 0) return 0;
  final c = current < 0 ? 0 : current;
  if (c >= destinationCount - 1) return destinationCount - 1;
  return c + 1;
}

/// Previous page toward VPN; stays at 0 (VPN end block).
int suiteSwipePrevIndex(int current, int destinationCount) {
  if (destinationCount <= 0) return 0;
  final c = current < 0 ? 0 : current;
  if (c <= 0) return 0;
  if (c >= destinationCount) return destinationCount - 1;
  return c - 1;
}

/// Map a completed horizontal swipe to the next index.
///
/// Product (reversed from prior reverse:true pager): **right-to-left** finger
/// motion (negative [dx], standard [PageView]) advances toward higher indices;
/// **left-to-right** (positive [dx]) walks back. End blocks at first/last.
int suiteIndexAfterHorizontalSwipe({
  required int current,
  required int destinationCount,
  required double dx,
  double threshold = 8.0,
}) {
  final n = destinationCount <= 0 ? 0 : destinationCount;
  // Clamp with raw destination length (may be < 4 when tests pass a custom count).
  final clamped = n <= 0
      ? 0
      : (current < 0
          ? 0
          : (current >= n ? n - 1 : current));
  if (dx.abs() < threshold) return clamped;
  // Reversed vs prior product: positive dx retreats, negative advances.
  if (dx < 0) return suiteSwipeNextIndex(clamped, n);
  return suiteSwipePrevIndex(clamped, n);
}
