/// RPT node endpoint and full-tunnel intent (shared with platform VPN).
class RptConfig {
  /// Product default node (must match [client/endpoint.py] PRODUCT_NODE_HOST).
  static const String host = '82.221.101.241';
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
}
