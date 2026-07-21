import 'dart:io' show Platform;

/// RPT node endpoint and full-tunnel intent (shared with platform VPN).
///
/// Multi-hop residual is **opt-in**: when [multiHopEnabled] is true, residual
/// Connect dials the **exit** hop (Romania) with `exit_node_elgamal.pub`.
/// Default remains single-hop Iceland entry (`node_elgamal.pub`).
/// This is residual-via-exit selection, not full intermediate encapsulation.
class RptConfig {
  /// Product entry node (must match [client/endpoint.py] PRODUCT_NODE_HOST).
  static const String entryHost = '82.221.101.241';

  /// Product exit hop (Romania FlokiNET) for multi-hop residual when enabled.
  static const String exitHost = '185.146.232.107';

  static const int port = 44044;
  static const String protocolMagic = 'RPT2';
  static const String sessionName = 'Privacy Restored';

  /// Product pin — must match monorepo ``client/VERSION`` and pubspec version.
  static const String productVersion = '0.3.6';

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

  /// True when residual multi-hop (exit dial) is selected.
  ///
  /// Enabled via `--dart-define=RPT_MULTIHOP_ENABLED=true` at build, or at
  /// runtime with process env ``RPT_MULTIHOP_ENABLED=1`` (desktop / shell).
  static bool get multiHopEnabled {
    if (multiHopFromEnvironment) return true;
    final v = (Platform.environment['RPT_MULTIHOP_ENABLED'] ?? '')
        .trim()
        .toLowerCase();
    return v == '1' || v == 'true' || v == 'yes' || v == 'on';
  }

  /// Residual dial host: exit when multi-hop active, else entry.
  static String get host => multiHopEnabled ? exitHost : entryHost;

  /// Bundled ElGamal public key basename for residual HELLO.
  static String get residualNodePubName =>
      multiHopEnabled ? 'exit_node_elgamal.pub' : 'node_elgamal.pub';
}
