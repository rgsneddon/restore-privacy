/// RPT node endpoint and full-tunnel intent (shared with platform VPN).
class RptConfig {
  static const String host = '104.156.224.47';
  static const int port = 44044;
  static const String protocolMagic = 'RPT2';
  static const String sessionName = 'Privacy Restored';

  /// Full tunnel: all device traffic (0.0.0.0/0).
  static const bool fullTunnel = true;
  static const String defaultRoute = '0.0.0.0/0';

  /// Product policy: never auto-connect on cold launch (manual Connect only).
  static const bool autoConnectOnLaunch = false;
}
