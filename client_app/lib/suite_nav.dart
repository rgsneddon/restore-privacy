/// Flat Suite main-bar destinations: VPN + promoted %/Evolve surfaces + rpAI.
///
/// % and Evolve share one product family — their child tabs (Wallet / Security /
/// Credit / Analysis / Voting) appear on the **main** bottom bar, not as nested
/// bars inside embedded shells.
library;

import 'suite_parts.dart';
import 'suite_version.dart';

/// One slot on the Suite main [NavigationBar] / [PageView].
enum SuiteNavDest {
  vpn,
  /// Evolve analysis (only when Evolve part is installed).
  analysis,
  /// Shared % / Evolve wallet surface (one link for both products).
  wallet,
  security,
  /// Evolve FCG voting (only when Evolve part is installed).
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
      // Shared % / Evolve wallet surface (child label; not dual product slots).
      return 'Wallet';
    case SuiteNavDest.security:
      return 'Security';
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

/// Ordered main-bar destinations for the current install flags.
///
/// - VPN always first; rpAI last when installed.
/// - % and Evolve are **one family**: no dual top-level "%" + "EVOLVE" slots.
/// - Shared Wallet / Security / Credit appear once.
/// - Analysis / Voting appear when Evolve is installed.
/// - When neither wallet nor evolve is installed, family destinations are omitted
///   (reinstall from Settings).
List<SuiteNavDest> suiteNavDestinations(SuitePartsState parts) {
  final out = <SuiteNavDest>[SuiteNavDest.vpn];
  final family = parts.walletInstalled || parts.evolveInstalled;
  if (family) {
    if (parts.evolveInstalled) {
      out.add(SuiteNavDest.analysis);
    }
    out.add(SuiteNavDest.wallet);
    out.add(SuiteNavDest.security);
    if (parts.evolveInstalled) {
      out.add(SuiteNavDest.voting);
    }
    out.add(SuiteNavDest.credit);
  }
  if (parts.rpaiInstalled) {
    out.add(SuiteNavDest.rpai);
  }
  return List<SuiteNavDest>.unmodifiable(out);
}

/// Clamp index into [suiteNavDestinations].
int clampSuiteNavIndex(int index, SuitePartsState parts) {
  final n = suiteNavDestinations(parts).length;
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

/// Map a family destination to evolve shell tab index when hasAppAccess
/// (0 Analysis, 1 Wallet, 2 Security, 3 Voting, 4 Credit).
int? suiteNavEvolveShellTabIndex(SuiteNavDest dest) {
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
