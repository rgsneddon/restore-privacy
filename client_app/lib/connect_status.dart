/// Pure connect-status mapping for RPT channel results (Android/Windows/Apple).
/// Unit-tested without a device — drives honest UI status strings.
///
/// Full-tunnel product rule: residual public IP only changes when the OS VPN
/// (Packet Tunnel / platform VPN service) is active. A host-only RPT2 HELLO
/// that assigns a tunnel IP is **not** a product connect success.

/// True only when native side reports a real successful **full-tunnel** session.
/// Rejects host-only HELLO maps even if they carry `ok: true` / `vpnIp`.
bool isConnectSuccess(dynamic result) {
  if (result is! Map) return false;
  if (result['ok'] != true) return false;
  // Explicit host-only / no-system-VPN markers from Apple (and shared helpers).
  if (result['hostOnlySession'] == true) return false;
  if (result['fullTunnelActive'] == false) return false;
  return true;
}

/// Human-readable status from the method-channel map (never invent "Connected"
/// for host-only HELLO or failed Packet Tunnel).
String mapConnectStatusMessage(dynamic result) {
  if (result is! Map) {
    return 'Connect failed — unexpected response from VPN layer';
  }
  final message = result['message']?.toString().trim() ?? '';
  final ok = isConnectSuccess(result);
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
    'Missing node_elgamal.pub — packages ship the public node key; '
    'a unique device Ed25519 key is generated on first run';
const String kVpnPermissionDeniedMessage =
    'VPN permission denied — grant once for full tunnel';

/// UK public-IP security gate (must match native [UkIpGate] / Python uk_gate).
const String kUkGateDeniedMessage =
    'Access denied: Restore Privacy is only available when your public IP '
    'is located in the United Kingdom. Your current network location is not UK.';
const String kUkGateLookupFailedMessage =
    'Access denied: could not verify that your public IP is in the United Kingdom. '
    'Check your network connection and try again.';

/// Honest full-tunnel failure: system VPN never came up (residual ISP IP expected).
const String kPacketTunnelNotActiveMessage =
    'System VPN (Packet Tunnel) did not become active — your residual public IP '
    'will not change. Enable Network Extension signing/entitlements and approve '
    'the VPN configuration, then try again.';

/// Host-only RPT2 HELLO diagnostic (node reachable, but not a full-tunnel success).
const String kHostOnlyHelloNotFullTunnelMessage =
    'Node session was assigned but the system Packet Tunnel is not carrying traffic — '
    'residual public IP is unchanged. Full-tunnel requires an active OS VPN extension.';

/// Build a product connect result map for full-tunnel honesty rules.
/// Pure helper — used by tests and documents the contract native channels must match.
Map<String, dynamic> buildFullTunnelConnectResult({
  required bool packetTunnelActive,
  String? vpnIp,
  String? detailMessage,
  bool hostOnlyHello = false,
  String? nodeDiagnostic,
}) {
  if (packetTunnelActive && !hostOnlyHello) {
    final ip = (vpnIp ?? '').trim();
    final base = (detailMessage ?? '').trim().isNotEmpty
        ? detailMessage!.trim()
        : (ip.isNotEmpty
            ? 'Connected — tunnel IP $ip'
            : 'Connected — Packet Tunnel active');
    return {
      'ok': true,
      'message': base,
      'fullTunnelActive': true,
      'hostOnlySession': false,
      if (ip.isNotEmpty) 'vpnIp': ip,
    };
  }

  // Host-only HELLO or NE failure — never product success.
  final buf = StringBuffer();
  if (hostOnlyHello) {
    buf.write(kHostOnlyHelloNotFullTunnelMessage);
    final ip = (vpnIp ?? '').trim();
    if (ip.isNotEmpty) {
      buf.write(' (node assigned $ip)');
    }
  } else {
    buf.write(kPacketTunnelNotActiveMessage);
  }
  if (detailMessage != null && detailMessage.trim().isNotEmpty) {
    buf.write(' ');
    buf.write(detailMessage.trim());
  }
  if (nodeDiagnostic != null && nodeDiagnostic.trim().isNotEmpty) {
    buf.write(' ');
    buf.write(nodeDiagnostic.trim());
  }
  final ip = (vpnIp ?? '').trim();
  return {
    'ok': false,
    'message': buf.toString(),
    'fullTunnelActive': false,
    'hostOnlySession': hostOnlyHello,
    if (ip.isNotEmpty) 'vpnIp': ip,
  };
}

/// True when a channel failure message is the UK location gate.
bool isUkGateFailureMessage(String message) {
  final m = message.toLowerCase();
  return m.contains('access denied') &&
      (m.contains('united kingdom') || m.contains('uk'));
}

/// Product policy: app close / background / detach must **not** auto-stop the tunnel.
/// The user stops the VPN only via the explicit Disconnect button.
///
/// Always returns false so lifecycle hooks do not tear down the tunnel.
bool shouldStopTunnelOnAppLifecycle(String lifecycleStateName) {
  // Intentionally ignore lifecycleStateName — close/background must not disconnect.
  return false;
}

/// Human message after intentional tunnel stop (channel or quit).
const String kDisconnectedResidualIpMessage =
    'Disconnected — system VPN stopped; residual public IP restored';
