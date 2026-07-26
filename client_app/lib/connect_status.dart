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

/// macOS window policy after Connect: **stay open** (do not auto-hide to tray).
///
/// Tray icon may still exist for manual restore/disconnect; Connect success must
/// not call hide-to-tray / minimize. Host-only HELLO / failures never hide either.
bool shouldHideToTrayAfterConnect(dynamic result) {
  // Product policy (override prior hide-on-success): keep main window visible.
  return false;
}

/// Same gate when Flutter already reduced the channel map to a bool (e.g. `_vpn.connect()`).
/// Always false — window stays open after product Connect success.
bool shouldHideToTrayAfterConnectSuccess(bool productConnectOk) {
  // Ignore [productConnectOk]; never auto-hide solely because Connect succeeded.
  return false;
}

/// Whether the keygen unlock sheet should dismiss after verify.
///
/// True when payment unlock allows Connect (valid active keygen path), or when
/// the just-completed verify returned an active entitlement status (belt-and-
/// suspenders if a secondary [paymentAllowsConnect] read races).
/// Invalid / inactive keygen must leave the sheet open with failure feedback.
bool shouldDismissKeygenSheetAfterUnlock({
  required bool paymentAllowsConnect,
  String? paymentStatus,
}) {
  if (paymentAllowsConnect) return true;
  final st = (paymentStatus ?? '').trim().toLowerCase();
  return st == 'active';
}

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
  if (message.isNotEmpty) {
    final low = message.toLowerCase();
    // Parity with desktop format_connect_failure: residual reset/timeout → keygen guidance
    if (low.contains('10054') ||
        low.contains('forcibly closed') ||
        low.contains('connection reset') ||
        low.contains('timed out') ||
        low.contains('no reply') ||
        low.contains('timeout')) {
      if (!low.contains('keygen')) {
        return '$message — If you just paid: enter the keygen from your '
            'fulfilment email (unlock dialog or Settings → Payment entitlement / keygen), '
            'then Connect again so this device can be admitted by the node.';
      }
    }
    return message;
  }
  return 'Connect failed — enter your keygen from the fulfilment email if Connect is blocked.';
}

/// Known failure substrings used by native Android path (for tests / docs).
const String kMissingSecretsMessage =
    'Missing node_elgamal.pub — packages ship the public node key; '
    'a unique device Ed25519 key is generated on first run';
const String kVpnPermissionDeniedMessage =
    'VPN permission denied — grant once for full tunnel';

/// Honest full-tunnel failure: system VPN never came up (residual ISP IP expected).
/// End-user path first (System Settings Allow); Team residual re-sign is operator/dev.
const String kPacketTunnelNotActiveMessage =
    'System VPN (Packet Tunnel) did not become active — residual public IP will not '
    'change. Allow VPN for Restore Privacy in System Settings → Network → VPN & Filters '
    '(and Login Items & Extensions if prompted). Settings opens when possible — then '
    'press Connect again. Residual Packet Tunnel needs a Team-signed host + appex with '
    'Network Extension (developers: scripts/sign_macos_residual_team.py).';

/// Host-only RPT2 HELLO diagnostic (node reachable, but not a full-tunnel success).
const String kHostOnlyHelloNotFullTunnelMessage =
    'Node session was assigned but the system Packet Tunnel is not carrying traffic — '
    'residual public IP is unchanged. Full-tunnel requires an active OS VPN extension. '
    'Approve VPN configuration in System Settings → Network → VPN & Filters, then Connect again.';

/// Button / channel label when the user must Allow the OS VPN configuration.
const String kOpenVpnSettingsLabel = 'Open VPN settings';

/// Product macOS residual tunnel type — Packet Tunnel Network Extension only.
/// Never L2TP, Cisco IPsec, or IKEv2 (those are System Settings manual types).
const String kProductVpnTunnelType = 'packet-tunnel';

/// Packet Tunnel provider bundle id registered in OS VPN preferences.
const String kProductVpnProviderBundleId =
    'com.restoreprivacy.restorePrivacyClient.PacketTunnel';

/// Localized name of the system VPN configuration (matches native save).
const String kProductVpnLocalizedDescription = 'Restore Privacy';

/// Pre-Connect status when Packet Tunnel profile is registered (not yet connected).
const String kPacketTunnelPreparedMessage =
    'Restore Privacy Packet Tunnel registered in System VPN preferences. '
    'If macOS asks to Allow VPN configuration, choose Allow — '
    'do not add L2TP, Cisco IPsec, or IKEv2. Then press Connect.';

/// True when a native prepare map describes the product Packet Tunnel (not legacy VPN).
bool isProductPacketTunnelPrepareResult(dynamic result) {
  if (result is! Map) return false;
  final type = result['tunnelType']?.toString().toLowerCase() ?? '';
  final bid = result['providerBundleId']?.toString() ?? '';
  if (type == kProductVpnTunnelType) return true;
  if (bid == kProductVpnProviderBundleId) return true;
  return false;
}

/// True when [message] wrongly steers users to manual L2TP / Cisco IPsec / IKEv2 as product.
bool productCopyDirectsToLegacyVpnTypes(String message) {
  final m = message.toLowerCase();
  // Contrast/negation is OK ("do not add L2TP"); positive "add L2TP" style is not.
  if (m.contains('do not add l2tp') ||
      m.contains('not l2tp') ||
      m.contains('— not l2tp') ||
      m.contains('- not l2tp') ||
      m.contains('never l2tp') ||
      m.contains('not configure l2tp')) {
    return false;
  }
  final positiveLegacy = RegExp(
    r'\b(add|choose|select|use|configure)\b.{0,40}\b(l2tp|ikev2|cisco\s*ipsec)\b',
    caseSensitive: false,
  );
  return positiveLegacy.hasMatch(message);
}

/// Human status from prepareVpn / preparePacketTunnel channel map.
String mapPrepareVpnStatusMessage(dynamic result) {
  if (result is! Map) {
    return 'Could not pre-register Packet Tunnel VPN configuration.';
  }
  final message = result['message']?.toString().trim() ?? '';
  if (isPrepareVpnSuccess(result)) {
    if (message.isNotEmpty) return message;
    return kPacketTunnelPreparedMessage;
  }
  if (message.isNotEmpty) return message;
  return 'Could not pre-register Packet Tunnel VPN configuration. '
      'Allow Restore Privacy under System Settings → Network → VPN & Filters '
      '(Packet Tunnel — not L2TP / Cisco IPsec / IKEv2).';
}

/// Honest prepare success: both [ok] and [prepared] true (saved NE manager).
///
/// A failed NE save must report prepared:false. Debounce may return prepared:true
/// only after a prior successful save (native lastSuccessfulPrepareAt).
bool isPrepareVpnSuccess(dynamic result) {
  if (result is! Map) return false;
  if (result['ok'] != true) return false;
  if (result['prepared'] != true) return false;
  return true;
}

/// Contract used by UI/tests: after a failed prepare, a follow-up must not treat
/// the prior failure as success. [priorResult] is the first prepare map;
/// [nextResult] is the second (e.g. keygen unlock then launch).
///
/// When prior failed, next must either succeed from a real re-attempt or fail
/// again — never claim prepared:true via [debounced] after a failed save
/// (native must only set lastSuccessfulPrepareAt after manager save OK).
bool prepareFollowUpIsHonest({
  required dynamic priorResult,
  required dynamic nextResult,
}) {
  if (priorResult is! Map || nextResult is! Map) return false;

  if (isPrepareVpnSuccess(priorResult)) {
    // Prior success: debounce prepared:true is allowed.
    return true;
  }

  // Prior failed — debounced prepared:true is always residual-dishonest.
  if (nextResult['debounced'] == true && nextResult['prepared'] == true) {
    return false;
  }
  // Real re-attempt success (user Allowed between attempts) is fine.
  if (isPrepareVpnSuccess(nextResult)) {
    return true;
  }
  // Retry still failing is honest.
  return nextResult['prepared'] != true;
}

/// Log-only feedback after attempting to open System Settings (must not replace residual failure status).
const String kOpenVpnSettingsOpenedFeedback =
    'Opened System Settings (Network / VPN). Allow Restore Privacy, then Connect again.';

/// Log-only when automatic open failed — user still needs the retry control.
const String kOpenVpnSettingsFailedFeedback =
    'Could not open System Settings automatically — use System Settings → Network → VPN & Filters.';

/// True when a connect failure message is residual / Packet Tunnel failure class
/// (for sticky **Open VPN settings** control — not necessarily auto-open).
bool isNeVpnPermissionFailureMessage(String message) {
  final m = message.toLowerCase();
  if (m.isEmpty) return false;
  return m.contains('nevpnerrordomain') ||
      m.contains('permission denied') ||
      m.contains('not authorized') ||
      m.contains('ne preferences failed') ||
      m.contains('approve vpn configuration') ||
      m.contains('packet tunnel is not carrying') ||
      m.contains('did not become active') ||
      m.contains('did not become connected') ||
      m.contains('allow vpn') ||
      m.contains('team residual') ||
      m.contains('packet-tunnel-provider') ||
      (m.contains('vpn configuration') &&
          (m.contains('system settings') || m.contains('allow')));
}

/// Strict permission-denial class for **auto-opening** System Settings.
///
/// Ordinary tunnel start failures, host-only HELLO diagnostics, and missing host
/// NE entitlement (Team residual re-sign) must **not** auto-open Network Settings.
bool isStrictVpnPermissionDenialMessage(String message) {
  final m = message.toLowerCase();
  if (m.isEmpty) return false;
  // Residual re-sign / missing host NE — Settings cannot fix this alone.
  if (m.contains('team residual') ||
      m.contains('sign_macos_residual') ||
      m.contains('missing the packet-tunnel-provider') ||
      (m.contains('host is missing') && m.contains('network extension'))) {
    return false;
  }
  return m.contains('nevpnerrordomain') ||
      m.contains('permission denied') ||
      m.contains('not authorized') ||
      m.contains('ne preferences failed') ||
      (m.contains('approve vpn configuration') &&
          (m.contains('system settings') ||
              m.contains('vpn & filters') ||
              m.contains('allow')));
}

/// True when [message] is only open-settings feedback (not residual failure truth).
bool isOpenVpnSettingsFeedbackMessage(String message) {
  final m = message.trim();
  if (m.isEmpty) return false;
  if (m == kOpenVpnSettingsOpenedFeedback || m == kOpenVpnSettingsFailedFeedback) {
    return true;
  }
  final low = m.toLowerCase();
  return low.startsWith('opened system settings') ||
      low.startsWith('could not open system settings') ||
      (low.contains('could not open') && low.contains('system settings'));
}

/// True when the channel map is a failed connect that should **auto-open**
/// System Settings (permission-class only). Never true on product success.
///
/// Sticky UI / manual **Open VPN settings** uses [shouldShowOpenVpnSettingsControl]
/// + [isNeVpnPermissionFailureMessage] — broader than auto-open.
bool shouldPromptOpenVpnSystemSettings(dynamic result) {
  return shouldAutoOpenVpnSystemSettings(result);
}

/// Auto-open Network / VPN Settings only on real NE/VPN authorization denial.
///
/// Does **not** auto-open for: host-only HELLO, generic tunnel start failure,
/// missing host `packet-tunnel-provider` (needs Team residual re-sign), or when
/// native already opened Settings (`openedVpnSettings`).
bool shouldAutoOpenVpnSystemSettings(dynamic result) {
  if (isConnectSuccess(result)) return false;
  if (result is! Map) return false;
  if (result['needsTeamResidualSign'] == true) return false;
  if (result['hostHasPacketTunnelEntitlement'] == false) return false;
  // Native already opened — do not open again from Flutter.
  if (result['openedVpnSettings'] == true) return false;
  final msg = result['message']?.toString() ?? '';
  if (isStrictVpnPermissionDenialMessage(msg)) return true;
  // Flag alone is insufficient without permission-class message (avoids opening
  // Settings on every residual-honest fullTunnelActive:false map).
  if (result['needsVpnSystemSettingsApproval'] == true &&
      isStrictVpnPermissionDenialMessage(msg)) {
    return true;
  }
  return false;
}

/// Whether the **Open VPN settings** control should stay visible.
///
/// [needsVpnSystemSettingsApproval] is sticky until product Connect succeeds so
/// open-settings feedback (which must not replace residual failure status) cannot
/// hide the retry button when the OS open fails or only logs feedback.
bool shouldShowOpenVpnSettingsControl({
  required bool connected,
  required bool needsVpnSystemSettingsApproval,
  required String statusMessage,
}) {
  if (connected) return false;
  if (needsVpnSystemSettingsApproval) return true;
  // Without sticky flag, only show for real NE residual failure status.
  if (isOpenVpnSettingsFeedbackMessage(statusMessage)) return false;
  return isNeVpnPermissionFailureMessage(statusMessage);
}

/// Build a product connect result map for full-tunnel honesty rules.
/// Pure helper — used by tests and documents the contract native channels must match.
Map<String, dynamic> buildFullTunnelConnectResult({
  required bool packetTunnelActive,
  String? vpnIp,
  String? detailMessage,
  bool hostOnlyHello = false,
  String? nodeDiagnostic,
  /// Apple residual is IPv4-only (no IPv6 kill-switch). Default false for honesty.
  /// Platforms that install real IPv6 protection may pass true.
  bool ipv6Protected = false,
}) {
  if (packetTunnelActive && !hostOnlyHello) {
    final ip = (vpnIp ?? '').trim();
    final detail = (detailMessage ?? '').trim();
    final String base;
    if (detail.isNotEmpty && detail.toLowerCase().contains('ipv6')) {
      base = detail;
    } else if (!ipv6Protected) {
      base = ip.isNotEmpty
          ? 'Connected — IPv4 via VPN; IPv6 not protected ($ip)'
          : 'Connected — IPv4 via VPN; IPv6 not protected';
    } else if (detail.isNotEmpty) {
      base = detail;
    } else {
      base = ip.isNotEmpty
          ? 'Connected — tunnel IP $ip'
          : 'Connected — Packet Tunnel active';
    }
    return {
      'ok': true,
      'message': base,
      'fullTunnelActive': true,
      'hostOnlySession': false,
      'ipv6Protected': ipv6Protected,
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
