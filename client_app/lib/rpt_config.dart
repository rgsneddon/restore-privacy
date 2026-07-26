import 'dart:io' show Platform;

import 'free_tier.dart';

import 'country_select.dart';

/// RPT node endpoint and full-tunnel intent (shared with platform VPN).
///
/// Multi-hop residual is **opt-in**: when [multiHopEnabled] is true, residual
/// Connect dials a non-entry catalog peer. Default remains single-hop **Iceland**
/// entry (`node_elgamal.pub` / [kDefaultEntryCountry]). Residual-via-exit
/// selection is not full intermediate encapsulation.
///
/// Free tier ([freeTierEnabled]): multi-hop is forced off; host is always entry.
class RptConfig {
  /// Product entry node (must match [client/endpoint.py] PRODUCT_NODE_HOST).
  static const String entryHost = '82.221.101.241';

  /// Product exit hop (Romania FlokiNET) for multi-hop residual when enabled.
  static const String exitHost = '185.146.232.107';

  static const int port = 44044;
  static const String protocolMagic = 'RPT2';
  static const String sessionName = 'Privacy Restored';

  /// Paid catalog pin — must match monorepo ``client/VERSION`` and pubspec.
  /// Free builds report [kFreeTierVersion] via [displayProductVersion].
  static const String productVersion = '0.4.8';

  /// UI / about version (free tier always ``3.3.3``).
  static String get displayProductVersion =>
      freeAwareProductVersion(productVersion);

  /// Full tunnel: all device traffic (0.0.0.0/0).
  static const bool fullTunnel = true;
  static const String defaultRoute = '0.0.0.0/0';

  /// Product policy: never auto-connect on cold launch (manual Connect only).
  static const bool autoConnectOnLaunch = false;

  /// Compile-time multi-hop enable (`--dart-define=RPT_MULTIHOP_ENABLED=true`).
  static const bool multiHopFromEnvironment = bool.fromEnvironment(
    'RPT_MULTIHOP_ENABLED',
    defaultValue: false,
  );

  /// Runtime override from Settings privacy-scale (null = use env/compile only).
  static bool? runtimeMultiHopOverride;

  /// Main-shell entry country (IS product default); drives residual dial host.
  static String runtimeEntryCountry = kDefaultEntryCountry;

  /// Apply Settings multi-hop toggle (Windows/Apple parity).
  /// No-op when free tier locks multi-hop off.
  static void setRuntimeMultiHop(bool? enabled) {
    if (freeTierEnabled) {
      runtimeMultiHopOverride = false;
      return;
    }
    runtimeMultiHopOverride = enabled;
  }

  /// Apply main-shell entry-country selection (United States/US product default).
  static void setRuntimeEntryCountry(String? code) {
    runtimeEntryCountry = normalizeEntryCountry(code);
  }

  /// True when residual multi-hop (exit dial) is selected.
  ///
  /// Free tier: always false. Else: Settings ? dart-define ? env.
  static bool get multiHopEnabled {
    if (freeTierEnabled) return false;
    final o = runtimeMultiHopOverride;
    if (o != null) return o;
    if (multiHopFromEnvironment) return true;
    final v = (Platform.environment['RPT_MULTIHOP_ENABLED'] ?? '')
        .trim()
        .toLowerCase();
    return v == '1' || v == 'true' || v == 'yes' || v == 'on';
  }

  /// Residual dial host from entry-country selection (+ multi-hop when on).
  static String get host => residualHostForEntryCountry(
        runtimeEntryCountry,
        multiHop: multiHopEnabled,
      );

  /// Bundled ElGamal public key basename for residual HELLO.
  ///
  /// Always derived from the residual dial [host] so multi-hop / DE entry
  /// cannot pair the wrong peer pin (e.g. DE multi-hop dials IS → node pub).
  static String get residualNodePubName => residualNodePubNameForHost(host);
}
