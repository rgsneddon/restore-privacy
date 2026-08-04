/// Restore Privacy residual VPN product identity and monopin.
///
/// Catalog monopin **1.1.8** — dedicated residual VPN client (no multi-product
/// Suite chrome). Paid catalog / client [productVersion] pins must match.
library;

/// Catalog / pubspec monopin for the suite product.
const String kSuiteVersion = '1.1.8';

/// User-visible product family name.
const String kSuiteProductName = 'Restore Privacy residual VPN';

/// Canonical chrome / about / startup string: "Restore Privacy residual VPN v 1.1.8".
const String kSuiteDisplayVersion = 'Restore Privacy residual VPN v 1.1.8';

/// Top-level suite tab labels (exact product copy).
const String kSuiteTabVpn = 'VPN';
const String kSuiteTabWallet = '%';
const String kSuiteTabEvolve = 'EVOLVE';
const String kSuiteTabRpai = 'rpAI';

/// Ordered tab labels for NavigationBar / tests.
const List<String> kSuiteTabLabels = [
  kSuiteTabVpn,
  kSuiteTabWallet,
  kSuiteTabEvolve,
  kSuiteTabRpai,
];
