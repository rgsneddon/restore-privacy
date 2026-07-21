/// Pure connect-status mapping for RPT channel results (Android/Windows/Apple).
/// Unit-tested without a device — drives honest UI status strings.
///
/// Full-tunnel product rule: residual public IP only changes when the OS VPN
/// (Packet Tunnel / platform VPN service) is active. A host-only RPT2 HELLO
/// that assigns a tunnel IP is **not** a product connect success.
///
/// While [busyConnecting] is true, the UI must keep a **Connecting** title
/// until full-tunnel success is reported (Android handshake can take 30–60s).

import 'theme.dart';

/// True only when native side reports a real successful **full-tunnel** session.
/// Rejects host-only HELLO maps even if they carry `ok: true` / `vpnIp`.
/// Also rejects explicit in-progress / connecting maps (`connecting: true`).
bool isConnectSuccess(dynamic result) {
  if (result is! Map) return false;
  if (result['ok'] != true) return false;
  // Still handshaking — not residual success (Android may take many seconds).
  if (result['connecting'] == true) return false;
  // Explicit host-only / no-system-VPN markers from Apple (and shared helpers).
  if (result['hostOnlySession'] == true) return false;
  if (result['fullTunnelActive'] == false) return false;
  return true;
}

/// Primary status-card title: Connected / Connecting / Disconnected.
///
/// [busyConnecting] keeps **Connecting…** until full residual success so the
/// UI does not flash Disconnected while Android finishes HELLO + TUN.
String statusCardTitle({
  required bool connected,
  required bool busyConnecting,
  String? vpnIp,
  bool residual = true,
  bool? ipv6Protected,
}) {
  if (connected) {
    return plainConnectedStatus(
      vpnIp: vpnIp,
      residual: residual,
      ipv6Protected: ipv6Protected,
    );
  }
  if (busyConnecting) {
    return kConnectingTitle;
  }
  return 'Disconnected';
}

/// Short card title while the native VPN is still coming up.
const String kConnectingTitle = 'Connecting…';

/// Status line while waiting for full-tunnel residual (RPT2 + OS VPN).
String connectingStatusMessage({
  String host = '82.221.101.241',
  int port = 44044,
  int? elapsedSeconds,
}) {
  final base =
      'Connecting to $host:$port (RPT2) — waiting for full tunnel…';
  if (elapsedSeconds == null || elapsedSeconds <= 0) {
    return base;
  }
  return '$base (${elapsedSeconds}s)';
}

/// True when a channel map means handshake/TUN is still in progress.
bool isConnectingInProgress(dynamic result) {
  if (result is! Map) return false;
  if (result['connecting'] == true) return true;
  final msg = (result['message']?.toString() ?? '').toLowerCase();
  return msg.contains('already connecting') ||
      msg.contains('still connecting') ||
      msg.contains('waiting for full tunnel');
}

/// macOS: hide main window to menu-bar tray only after **product** full-tunnel success.
///
/// Must match [isConnectSuccess] — host-only HELLO / failed Packet Tunnel must not hide.
bool shouldHideToTrayAfterConnect(dynamic result) => isConnectSuccess(result);

/// Same gate when Flutter already reduced the channel map to a bool (e.g. `_vpn.connect()`).
bool shouldHideToTrayAfterConnectSuccess(bool productConnectOk) => productConnectOk;

/// Human-readable status from the method-channel map (never invent "Connected"
/// for host-only HELLO or failed Packet Tunnel).
String mapConnectStatusMessage(dynamic result) {
  if (result is! Map) {
    return 'Connect failed — unexpected response from VPN layer';
  }
  final message = result['message']?.toString().trim() ?? '';
  if (isConnectingInProgress(result) && !isConnectSuccess(result)) {
    return message.isNotEmpty
        ? message
        : connectingStatusMessage();
  }
  final ok = isConnectSuccess(result);
  if (ok) {
    final ip = result['vpnIp']?.toString().trim() ?? '';
    // Prefer explicit native honesty about IPv6 when present
    final v6 = result['ipv6Protected'];
    if (v6 == false) {
      if (message.toLowerCase().contains('ipv6 not protected')) {
        return message;
      }
      return ip.isNotEmpty
          ? 'Connected — IPv4 via VPN; IPv6 not protected ($ip)'
          : 'Connected — IPv4 via VPN; IPv6 not protected';
    }
    if (v6 == true) {
      if (message.toLowerCase().contains('ipv6 isp path blocked') ||
          message.toLowerCase().contains('ipv6')) {
        return message.isNotEmpty ? message : 'Connected — VPN active; IPv6 ISP path blocked';
      }
      return ip.isNotEmpty
          ? 'Connected — VPN active; IPv6 ISP path blocked ($ip)'
          : 'Connected — VPN active; IPv6 ISP path blocked';
    }
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

/// Honest full-tunnel failure: system VPN never came up (residual ISP IP expected).
const String kPacketTunnelNotActiveMessage =
    'System VPN (Packet Tunnel) did not become active — your residual public IP '
    'will not change. Use a Team-signed residual build with Network Extension '
    'on host + Packet Tunnel (scripts/sign_macos_residual_team.py), approve the '
    'VPN configuration in System Settings → Network → VPN & Filters, then try again.';

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
