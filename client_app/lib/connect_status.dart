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
///
/// When residual capture / full tunnel is already active (or a session VPN IP
/// is present with residual flags), treat as success even if a stale
/// `connecting: true` flag races — otherwise the UI loops "waiting for full
/// tunnel" every few seconds after residual is up.
bool isConnectSuccess(dynamic result) {
  if (result is! Map) return false;
  // Explicit host-only / no-system-VPN markers from Apple (and shared helpers).
  if (result['hostOnlySession'] == true) return false;
  if (result['fullTunnelActive'] == false &&
      result['residualCapture'] != true &&
      result['systemCapture'] != true &&
      result['routesApplied'] != true) {
    // Still handshaking without residual flags — not success.
    if (result['connecting'] == true) return false;
  }
  // Residual already up (Android/iOS status rehydrate).
  if (result['fullTunnelActive'] == true ||
      result['residualCapture'] == true ||
      result['systemCapture'] == true ||
      result['routesApplied'] == true) {
    if (result['connected'] == true || result['ok'] == true) return true;
    // Session IP with residual flags is enough (stale connecting flag ignored).
    final ip = result['vpnIp']?.toString().trim() ?? '';
    if (ip.isNotEmpty) return true;
  }
  if (result['ok'] != true && result['connected'] != true) return false;
  // Still handshaking — not residual success (Android may take many seconds).
  if (result['connecting'] == true &&
      result['fullTunnelActive'] != true &&
      result['residualCapture'] != true) {
    return false;
  }
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
  bool? ipv4Residual,
}) {
  if (connected) {
    return plainConnectedStatus(
      vpnIp: vpnIp,
      residual: residual,
      ipv6Protected: ipv6Protected,
      ipv4Residual: ipv4Residual,
    );
  }
  if (busyConnecting) {
    return kConnectingTitle;
  }
  return 'Disconnected';
}

/// True when a status line already encodes dual-stack residual honesty
/// (IPv6 path blocked / not protected, IPv4 residual off, dual-stack off).
bool isDualStackHonestConnectedMessage(String message) {
  final low = message.toLowerCase();
  if (low.isEmpty) return false;
  return low.contains('ipv6') ||
      low.contains('dual-stack') ||
      low.contains('residual off');
}

/// Resolve Connected card status after product Connect success (UI path).
///
/// Prefer an already-honest native channel message (from
/// [mapConnectStatusMessage]); otherwise build dual-stack honesty from the
/// product Settings residual switches used for that session.
String resolveConnectedStatusAfterSuccess({
  required String nativeStatus,
  String? vpnIp,
  required bool residualIpv4,
  required bool residualIpv6,
}) {
  final ipMatch = RegExp(r'10\.\d+\.\d+\.\d+').firstMatch(nativeStatus);
  final ip = (vpnIp ?? ipMatch?.group(0) ?? '').trim();
  if (isDualStackHonestConnectedMessage(nativeStatus)) {
    return nativeStatus;
  }
  return connectedHonestyMessage(
    vpnIp: ip.isEmpty ? null : ip,
    ipv4Residual: residualIpv4,
    ipv6Protected: residualIpv6,
  );
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
///
/// Never true once residual full-tunnel success is established — stale
/// `connecting` / "waiting for full tunnel" strings must not keep the UI looping.
bool isConnectingInProgress(dynamic result) {
  if (result is! Map) return false;
  if (isConnectSuccess(result)) return false;
  if (result['fullTunnelActive'] == true ||
      result['residualCapture'] == true ||
      result['connected'] == true) {
    return false;
  }
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

/// Whether the forced keygen unlock sheet should be presented.
///
/// False when a sheet is already open (re-entrancy / double launch+accept race)
/// or when keygen is no longer required (after a successful unlock).
bool shouldPresentKeygenUnlockSheet({
  required bool needsKeygenUnlock,
  required bool keygenSheetAlreadyOpen,
}) {
  if (keygenSheetAlreadyOpen) return false;
  return needsKeygenUnlock;
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
    final low = message.toLowerCase();
    // Never keep a stale "waiting for full tunnel" / connecting line once residual is up.
    final waitNoise = low.contains('waiting for full tunnel') ||
        low.contains('still connecting') ||
        low.contains('already connecting') ||
        (low.startsWith('connecting') && !low.contains('connected'));
    // Prefer explicit native honesty about dual-stack residual when present.
    final v6 = result['ipv6Protected'];
    final v4 = result['ipv4Residual'];
    if (v6 is bool || v4 is bool) {
      final ipv6On = v6 is bool ? v6 : true;
      final ipv4On = v4 is bool ? v4 : true;
      // Keep an already-honest dual-stack message from native.
      if (message.isNotEmpty &&
          !waitNoise &&
          (low.contains('ipv6') ||
              low.contains('dual-stack') ||
              low.contains('residual off'))) {
        return message;
      }
      return connectedHonestyMessage(
        vpnIp: ip.isEmpty ? null : ip,
        ipv4Residual: ipv4On,
        ipv6Protected: ipv6On,
      );
    }
    if (message.isNotEmpty && !waitNoise && ip.isNotEmpty) {
      return message.contains(ip) ? message : '$message (VPN IP $ip)';
    }
    if (message.isNotEmpty && !waitNoise) return message;
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
///
/// Free monopin residual-capable path: end-user Allow / System Settings first.
/// Developer Team residual re-sign is **not** the primary story here (see
/// [kMissingHostNeEntitlementMessage] for true missing-host-NE builds only).
const String kPacketTunnelNotActiveMessage =
    'System VPN (Packet Tunnel) did not become active — residual public IP will not '
    'change. Open System Settings → Network → VPN & Filters, enable Restore Privacy, '
    'choose Allow if macOS asks (also check Login Items & Extensions), then press '
    'Connect again in the app. Do not add L2TP, Cisco IPsec, or IKEv2.';

/// Host-only RPT2 HELLO diagnostic (node reachable, but not a full-tunnel success).
/// Node assigned IP proves residual entitlement (trial/KEYGEN) — not trial expiry.
const String kHostOnlyHelloNotFullTunnelMessage =
    'Node session was assigned but the system Packet Tunnel is not carrying traffic — '
    'residual public IP is unchanged. Full-tunnel requires an active OS VPN extension. '
    'Open System Settings → Network → VPN & Filters, enable Restore Privacy, Allow if '
    'prompted, then Connect again. This is not a trial or KEYGEN failure when a node '
    'IP was assigned.';

/// True missing-host-NE / non-residual-capable build (not free monopin residual path).
const String kMissingHostNeEntitlementMessage =
    'This app build cannot register or activate Packet Tunnel: the host is missing the '
    'packet-tunnel-provider Network Extension entitlement. Re-download the latest free '
    'macOS package, or on a developer Mac re-sign with scripts/sign_macos_residual_team.py.';
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
///
/// When [hostHasPacketTunnelEntitlement] is explicitly false (catalog DevID),
/// prepared must not be treated as success — System Settings will not apply
/// residual Packet Tunnel without host NE.
bool isPrepareVpnSuccess(dynamic result) {
  if (result is! Map) return false;
  if (result['ok'] != true) return false;
  if (result['prepared'] != true) return false;
  if (result['hostHasPacketTunnelEntitlement'] == false) return false;
  if (result['needsTeamResidualSign'] == true) return false;
  return true;
}

/// Pure: whether a prepare channel map may stamp prepared/debounce success.
///
/// Used by tests to lock the residual-honest contract without NE I/O.
bool prepareMapAllowsPreparedSuccess({
  required bool saveSucceeded,
  required bool hostHasPacketTunnelEntitlement,
  bool needsTeamResidualSign = false,
}) {
  if (!saveSucceeded) return false;
  if (!hostHasPacketTunnelEntitlement) return false;
  if (needsTeamResidualSign) return false;
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
      m.contains('packet-tunnel-provider') ||
      (m.contains('host is missing') && m.contains('network extension')) ||
      m.contains('public developer id')) {
    return false;
  }
  // Explicit auth denial
  if (m.contains('permission denied') ||
      m.contains('not authorized') ||
      m.contains('user denied')) {
    return true;
  }
  // NEVPNErrorDomain code 5 only (configuration read/write / typical Allow denial)
  if (m.contains('nevpnerrordomain')) {
    if (m.contains(' 5)') ||
        m.contains(' 5:') ||
        m.contains('code 5') ||
        m.contains('errordomain 5')) {
      return true;
    }
    return m.contains('permission') || m.contains('denied');
  }
  // Approve guidance with System Settings / VPN & Filters
  if (m.contains('approve vpn configuration') &&
      (m.contains('system settings') || m.contains('vpn & filters'))) {
    return true;
  }
  // Do not match bare "allow vpn", generic "ne preferences failed", or other NE codes.
  return false;
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

/// Honest Connected card line from session dual-stack residual flags.
/// Never claims "IPv6 ISP path blocked" when residual IPv6 protection is off.
String connectedHonestyMessage({
  String? vpnIp,
  bool ipv4Residual = true,
  bool ipv6Protected = true,
}) {
  final ip = (vpnIp ?? '').trim();
  final suffix = ip.isEmpty ? '' : ' ($ip)';
  if (ipv4Residual && ipv6Protected) {
    return 'Connected — VPN active; IPv6 ISP path blocked$suffix';
  }
  if (ipv4Residual && !ipv6Protected) {
    return 'Connected — IPv4 via VPN; IPv6 not protected$suffix';
  }
  if (!ipv4Residual && ipv6Protected) {
    return 'Connected — IPv4 residual off; IPv6 ISP path blocked$suffix';
  }
  return 'Connected — residual dual-stack off$suffix';
}

/// Build a product connect result map for full-tunnel honesty rules.
/// Pure helper — used by tests and documents the contract native channels must match.
Map<String, dynamic> buildFullTunnelConnectResult({
  required bool packetTunnelActive,
  String? vpnIp,
  String? detailMessage,
  bool hostOnlyHello = false,
  String? nodeDiagnostic,
  /// Product residual installs IPv6 ISP leak mitigation in Packet Tunnel.
  /// Default true matches Apple residual success after protection is applied.
  /// Pass false only when protection was not installed.
  bool ipv6Protected = true,
  /// Full IPv4 residual capture. Default true; false = session/tunnel IP only.
  bool ipv4Residual = true,
}) {
  if (packetTunnelActive && !hostOnlyHello) {
    final ip = (vpnIp ?? '').trim();
    final detail = (detailMessage ?? '').trim();
    final detailLow = detail.toLowerCase();
    final String base;
    if (detail.isNotEmpty &&
        (detailLow.contains('ipv6') ||
            detailLow.contains('dual-stack') ||
            detailLow.contains('residual off'))) {
      base = detail;
    } else {
      base = connectedHonestyMessage(
        vpnIp: ip.isEmpty ? null : ip,
        ipv4Residual: ipv4Residual,
        ipv6Protected: ipv6Protected,
      );
    }
    return {
      'ok': true,
      'message': base,
      'fullTunnelActive': true,
      'hostOnlySession': false,
      'ipv6Protected': ipv6Protected,
      'ipv4Residual': ipv4Residual,
      if (ip.isNotEmpty) 'vpnIp': ip,
    };
  }

  // Host-only HELLO or NE failure — never product success.
  // Single primary root cause (no NE + Settings + UDP wall of text).
  final ip = (vpnIp ?? '').trim();
  final message = composeConnectFailurePrimaryMessage(
    hostOnlyHello: hostOnlyHello,
    vpnIp: ip.isEmpty ? null : ip,
    detailMessage: detailMessage,
    nodeDiagnostic: nodeDiagnostic,
  );
  return {
    'ok': false,
    'message': message,
    'fullTunnelActive': false,
    'hostOnlySession': hostOnlyHello,
    if (ip.isNotEmpty) 'vpnIp': ip,
  };
}

/// True only for **actual** missing-host-NE / public DevID product dual-path copy.
///
/// Must **not** match residual-capable Packet Tunnel boilerplate that merely
/// *mentions* `sign_macos_residual_team` or `packet-tunnel-provider` as a tip
/// ([kPacketTunnelNotActiveMessage], residual-team startTunnel tips). Those are
/// residual-capable failures — UDP/keygen/entitlement may still be primary.
bool isMissingHostNeDetail(String text) {
  final m = text.toLowerCase();
  if (m.isEmpty) return false;
  // Explicit host-cannot-register / host-missing entitlement (public DevID).
  if (m.contains('this app build cannot register or activate packet tunnel')) {
    return true;
  }
  if (m.contains('host is missing the packet-tunnel-provider') ||
      m.contains('host is missing the packet-tunnel-provider network extension')) {
    return true;
  }
  if (m.contains('public developer id downloads intentionally omit')) {
    return true;
  }
  // Flag-style detail without PT-not-active boilerplate.
  if (m.contains('needsteamresidualsign') ||
      m.contains('needs team residual sign')) {
    return true;
  }
  // Do NOT match bare packet-tunnel-provider / sign_macos_residual / team residual
  // — those appear as conditional tips on residual-capable hosts.
  return false;
}

/// True when [nodeDiagnostic] is residual HELLO / admission silence (keygen path).
bool isNodeHelloAdmissionFailure(String nodeDiagnostic) {
  final low = nodeDiagnostic.toLowerCase();
  if (low.isEmpty) return false;
  return low.contains('udp receive timeout') ||
      low.contains('udp receive failed') ||
      low.contains('no reply') ||
      low.contains('payment entitlement') ||
      (low.contains('keygen') && low.contains('connect failed'));
}

/// Single primary root-cause for Connect failure (mirrors native RptFullTunnelResult).
///
/// Residual-capable hosts: HELLO UDP silence / entitlement beats PT tip boilerplate.
/// Public DevID: explicit missing-host-NE beats UDP noise.
String composeConnectFailurePrimaryMessage({
  required bool hostOnlyHello,
  String? vpnIp,
  String? detailMessage,
  String? nodeDiagnostic,
}) {
  final detail = (detailMessage ?? '').trim();
  final node = (nodeDiagnostic ?? '').trim();
  final ip = (vpnIp ?? '').trim();
  final detailLow = detail.toLowerCase();

  // 1) True public-DevID missing host NE only (strict).
  if (isMissingHostNeDetail(detail) || isMissingHostNeDetail(node)) {
    if (detail.isNotEmpty && isMissingHostNeDetail(detail)) return detail;
    if (node.isNotEmpty && isMissingHostNeDetail(node)) return node;
    return detail.isEmpty ? kPacketTunnelNotActiveMessage : detail;
  }

  // 2) Host-only HELLO (node up, no system tunnel).
  if (hostOnlyHello) {
    var line = kHostOnlyHelloNotFullTunnelMessage;
    if (ip.isNotEmpty) line = '$line (node assigned $ip)';
    if (detail.isNotEmpty && !line.toLowerCase().contains(detailLow)) {
      line = '$line $detail';
    }
    return line;
  }

  // 3) Residual-capable: node HELLO/admission failure is primary over PT tips.
  if (node.isNotEmpty && isNodeHelloAdmissionFailure(node)) {
    return primaryNodeConnectFailureMessage(node);
  }

  // 4) Explicit tunnel/NE detail without node HELLO noise.
  if (detail.isNotEmpty) {
    final hasResidualHonesty = detailLow.contains('residual public ip') ||
        detailLow.contains('did not become active') ||
        detailLow.contains('did not become connected') ||
        detailLow.contains('system vpn (packet tunnel)') ||
        detailLow.contains('packet tunnel did not') ||
        detailLow.contains('vpn & filters');
    // Residual-capable free monopin: keep tunnel Allow guidance only — never
    // prepend Team residual re-sign boilerplate over a live tunnel-fail detail.
    final base = hasResidualHonesty
        ? detail
        : '$kPacketTunnelNotActiveMessage $detail';
    if (node.isNotEmpty &&
        !_isRedundantNodeDiagnostic(node: node, detail: base)) {
      return '$base $node';
    }
    return base;
  }
  if (node.isNotEmpty) {
    return primaryNodeConnectFailureMessage(node);
  }
  return kPacketTunnelNotActiveMessage;
}

/// Prefer keygen / entitlement wording for residual HELLO UDP silence.
String primaryNodeConnectFailureMessage(String nodeDiagnostic) {
  final n = nodeDiagnostic.trim();
  if (n.isEmpty) return n;
  final low = n.toLowerCase();
  if (low.contains('udp receive timeout') ||
      low.contains('udp receive failed') ||
      low.contains('no reply')) {
    if (low.contains('keygen') || low.contains('entitlement')) {
      return n;
    }
    return '$n — residual HELLO got no reply. Product residual nodes refuse HELLO '
        'until this device is bound to an active paid entitlement. If you just paid: '
        'enter the keygen from your fulfilment email (unlock dialog or Settings → '
        'Payment entitlement / keygen), then Connect again.';
  }
  return n;
}

bool _isRedundantNodeDiagnostic({
  required String node,
  required String detail,
}) {
  final n = node.toLowerCase();
  final d = detail.toLowerCase();
  if (n.isEmpty) return true;
  if (d.contains(n)) return true;
  if (isMissingHostNeDetail(detail)) return true;
  return false;
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
///
/// ASCII hyphen only - em dash U+2014 mis-decodes on some Android log/print
/// surfaces as mojibake (e.g. "å€" / "â€"").
const String kDisconnectedResidualIpMessage =
    'Disconnected - system VPN stopped; residual public IP restored';

/// Normalize punctuation for the main-screen print/status window.
///
/// Replaces em/en dashes and common UTF-8-as-Latin-1 mojibake of those dashes
/// so Android never shows garbage like `å€` in disconnect lines.
///
/// **Does not** rewrite ordinary ASCII hyphens (compound words like `end-user`,
/// hostnames, URLs). Only the dash/mojibake forms listed below are substituted.
String sanitizeStatusForPrint(String message) {
  var s = message;
  // Ellipsis only (not hyphen-related).
  s = s.replaceAll('\u2026', '...');

  // Match only em/en dash and known mojibake of UTF-8 em dash (E2 80 94):
  //   real: U+2014 / U+2013
  //   cp1252 misread: â€" / â€" (U+00E2 U+20AC U+201D/U+201C)
  //   latin-1 misread re-encoded: â\u0080\u0094
  //   device font garbage: å€ (U+00E5 U+20AC)
  // Optional surrounding whitespace collapses to a single " - " separator.
  final dashLike = RegExp(
    r'[ \t]*('
    r'\u2014|\u2013' // em / en dash
    r'|\u00e2\u20ac[\u201c\u201d\u2013\u2014]?' // â€" family
    r'|\u00e2\u0080[\u0093\u0094]' // latin-1 re-encode of E2 80 93/94
    r'|\u00e5\u20ac' // å€
    r'|[\u00e2\u00e5]\u20ac' // bare â€ / å€ fragment
    r')[ \t]*',
  );
  s = s.replaceAll(dashLike, ' - ');
  // Collapse runs of spaces introduced by substitution only.
  s = s.replaceAll(RegExp(r' {2,}'), ' ');
  return s.trim();
}
