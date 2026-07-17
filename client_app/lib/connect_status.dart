/// Pure connect-status mapping for RPT Android/Windows channel results.
/// Unit-tested without a device — drives honest UI status strings.

/// True only when native side reports a real successful session.
bool isConnectSuccess(dynamic result) {
  if (result is! Map) return false;
  return result['ok'] == true;
}

/// Human-readable status from the method-channel map (never invent "Connected").
String mapConnectStatusMessage(dynamic result) {
  if (result is! Map) {
    return 'Connect failed — unexpected response from VPN layer';
  }
  final message = result['message']?.toString().trim() ?? '';
  final ok = result['ok'] == true;
  if (ok) {
    final ip = result['vpnIp']?.toString().trim() ?? '';
    if (message.isNotEmpty && ip.isNotEmpty) {
      return message.contains(ip) ? message : '$message (VPN IP $ip)';
    }
    if (message.isNotEmpty) return message;
    if (ip.isNotEmpty) return 'Connected — tunnel IP $ip';
    return 'Connected';
  }
  if (message.isNotEmpty) return message;
  return 'Connect failed';
}

/// Known failure substrings used by native Android path (for tests / docs).
const String kMissingSecretsMessage =
    'Missing admission secrets — place client_ed25519.priv and node_elgamal.pub under app secrets';
const String kVpnPermissionDeniedMessage =
    'VPN permission denied — grant once for full tunnel';
