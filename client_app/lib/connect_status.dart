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

/// UK public-IP security gate (must match native [UkIpGate] / Python uk_gate).
const String kUkGateDeniedMessage =
    'Access denied: Restore Privacy is only available when your public IP '
    'is located in the United Kingdom. Your current network location is not UK.';
const String kUkGateLookupFailedMessage =
    'Access denied: could not verify that your public IP is in the United Kingdom. '
    'Check your network connection and try again.';

/// True when a channel failure message is the UK location gate.
bool isUkGateFailureMessage(String message) {
  final m = message.toLowerCase();
  return m.contains('access denied') &&
      (m.contains('united kingdom') || m.contains('uk'));
}
