/// Restore Privacy Suite product identity and monopin.
///
/// Suite v1.0.9 unifies residual VPN, Perccent wallet (%), and Evolve under one
/// shell. Paid catalog / client [productVersion] pins must match this monopin.
library;

/// Catalog / pubspec monopin for the suite product.
const String kSuiteVersion = '1.0.9';

/// User-visible product family name.
const String kSuiteProductName = 'Restore Privacy Suite';

/// Canonical chrome / about / startup string: "Restore Privacy Suite v 1.0.9".
const String kSuiteDisplayVersion = 'Restore Privacy Suite v 1.0.9';

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
