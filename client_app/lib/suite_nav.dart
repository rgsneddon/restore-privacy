/// Flat Suite main-bar destinations: VPN + promoted %/Evolve surfaces + rpAI.
///
/// % and Evolve share one product family — their child tabs (Wallet / Backup /
/// Credit / Analysis / Voting) appear on the **main** bottom bar, not as nested
/// bars inside embedded shells.
library;

import 'suite_parts.dart';
import 'suite_version.dart';

/// One slot on the Suite main [NavigationBar] / [PageView].
enum SuiteNavDest {
  vpn,
  /// Evolve analysis (only when Evolve installed **and** hasAppAccess).
  analysis,
  /// Shared % / Evolve wallet surface (one link for both products).
  wallet,
  security,
  /// Evolve FCG voting (only when Evolve installed **and** hasAppAccess).
  voting,
  credit,
  rpai,
}

/// User-visible labels for main-bar destinations.
String suiteNavLabel(SuiteNavDest dest) {
  switch (dest) {
    case SuiteNavDest.vpn:
      return kSuiteTabVpn;
    case SuiteNavDest.analysis:
      return 'Analysis';
    case SuiteNavDest.wallet:
      return 'Wallet';
    case SuiteNavDest.security:
      // User-facing product name; enum stays [SuiteNavDest.security] for stability.
      return 'Backup';
    case SuiteNavDest.voting:
      return 'Voting';
    case SuiteNavDest.credit:
      return 'Credit';
    case SuiteNavDest.rpai:
      return kSuiteTabRpai;
  }
}

/// True when this destination is a promoted % / Evolve family surface.
bool suiteNavIsPercentEvolveFamily(SuiteNavDest dest) {
  switch (dest) {
    case SuiteNavDest.analysis:
    case SuiteNavDest.wallet:
    case SuiteNavDest.security:
    case SuiteNavDest.voting:
    case SuiteNavDest.credit:
      return true;
    case SuiteNavDest.vpn:
    case SuiteNavDest.rpai:
      return false;
  }
}

/// Ordered main-bar destinations — **VPN only** for the dedicated residual app.
///
/// Evolve / wallet / Backup / Voting / Credit / rpAI are not product chrome.
/// [parts] / [hasAppAccess] are ignored so install flags cannot re-expand the bar.
List<SuiteNavDest> suiteNavDestinations(
  SuitePartsState parts, {
  bool hasAppAccess = true,
}) {
  final _ = parts;
  final __ = hasAppAccess;
  return List<SuiteNavDest>.unmodifiable(const [SuiteNavDest.vpn]);
}

/// Clamp index into [suiteNavDestinations].
int clampSuiteNavIndex(
  int index,
  SuitePartsState parts, {
  bool hasAppAccess = true,
}) {
  final n = suiteNavDestinations(parts, hasAppAccess: hasAppAccess).length;
  if (n <= 0) return 0;
  if (index < 0) return 0;
  if (index >= n) return n - 1;
  return index;
}

/// Map a family destination to wallet shell tab index (0 Wallet, 1 Security, 2 Credit).
int? suiteNavWalletShellTabIndex(SuiteNavDest dest) {
  switch (dest) {
    case SuiteNavDest.wallet:
      return 0;
    case SuiteNavDest.security:
      return 1;
    case SuiteNavDest.credit:
      return 2;
    default:
      return null;
  }
}

/// Full-access evolve shell: 0 Analysis, 1 Wallet, 2 Security, 3 Voting, 4 Credit.
int? suiteNavEvolveFullShellTabIndex(SuiteNavDest dest) {
  switch (dest) {
    case SuiteNavDest.analysis:
      return 0;
    case SuiteNavDest.wallet:
      return 1;
    case SuiteNavDest.security:
      return 2;
    case SuiteNavDest.voting:
      return 3;
    case SuiteNavDest.credit:
      return 4;
    default:
      return null;
  }
}

/// Limited evolve shell (no app access): Wallet=0, Security=1, Credit=2.
int? suiteNavEvolveLimitedShellTabIndex(SuiteNavDest dest) {
  switch (dest) {
    case SuiteNavDest.wallet:
      return 0;
    case SuiteNavDest.security:
      return 1;
    case SuiteNavDest.credit:
      return 2;
    default:
      return null;
  }
}

/// Evolve shell tab index for [dest], respecting [hasAppAccess].
int? suiteNavEvolveShellTabIndex(
  SuiteNavDest dest, {
  required bool hasAppAccess,
}) {
  if (hasAppAccess) {
    return suiteNavEvolveFullShellTabIndex(dest);
  }
  return suiteNavEvolveLimitedShellTabIndex(dest);
}
