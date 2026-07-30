/// Shared product honesty copy for Settings (mirrors client/transparency_copy.py
/// and client/product_policy.py explainers).

const String kDpiMitigationTitle = 'Traffic analysis mitigations';
const String kPrivacyScaleTitle = 'Privacy scale (speed vs residual defenses)';
const String kPingStatsTitle = 'Node ping (best-effort)';
const String kConnectionLogTitle = 'Connection log';
const String kLeakTestTitle = 'Leak test';
const String kLeakTestButton = 'Run leak test';
const String kExportLogButton = 'Export log';
const String kRefreshPingsButton = 'Refresh pings';

/// Plain-language: mitigation ≠ DPI-undetectability.
const String kDpiMitigationDisclaimer =
    'Traffic shaping (padding, send jitter, and cover traffic) and outer obfuscation '
    'default off on residual paths (lean residual) until you turn them on in Settings. '
    'When enabled they reduce coarse traffic analysis, but they are mitigations only — '
    'not a guarantee of DPI-undetectability or full pluggable-transport parity '
    '(for example obfs4, meek, or V2Ray). A determined network observer may still '
    'fingerprint the tunnel.';

/// Connected residual still encrypts OS traffic — honest power/CPU note (P2).
const String kConnectedIdlePowerHonesty =
    'While Connected, residual full-tunnel protection stays active even if you are not '
    'browsing: background app and system traffic still goes through the VPN crypto path, '
    'which uses battery and CPU. Disconnect when you do not need protection. '
    'Traffic shaping ON also sends periodic cover frames (~every 2s), which uses a little '
    'extra power and data.';

/// Mirrors EXPLAINER_TRAFFIC_SHAPE in product_policy.py.
const String kExplainerTrafficShape =
    'Traffic shaping pads packet sizes, adds small send jitter, and sends '
    'periodic cover (dummy) frames so traffic is harder to fingerprint. '
    'OFF (product default) = lean residual (no pad/cover/jitter) → snappier browsing; '
    'weaker against size/timing analysis. '
    'ON = stronger privacy against coarse traffic analysis; slightly more bandwidth '
    'and latency. Residual VPN crypto and tunnel still work either way. '
    'Applies on next Connect (not mid-session).';

/// Mirrors EXPLAINER_OUTER_OBFUSCATION.
const String kExplainerOuterObfuscation =
    'Outer obfuscation wraps residual UDP in a QUIC-like shell so clear RPT '
    'framing is not obvious on the wire. '
    'OFF (product default) = bare RPT frames (node still accepts both) → slightly less '
    'overhead; easier for simple classifiers to spot product traffic. '
    'ON = better blend with generic encrypted UDP; small CPU/header cost. '
    'Not a claim of full DPI-undetectability either way. '
    'Applies on next Connect (not mid-session).';

/// Mirrors EXPLAINER_MULTIHOP.
const String kExplainerMultihop =
    'Multi-hop residual routes via an exit hop (entry → Germany exit) so '
    'egress IP is the exit, not only the selected entry (default Germany). '
    'OFF (product default) = single hop to the entry node — lower lag/ping. '
    'ON = extra hop path when configured — more privacy of path, higher latency. '
    'Requires residual multi-hop routing; does not replace licence/keygen unlock. '
    'While connected, Disconnect then Connect to re-establish via the new hop.';

/// Mirrors EXPLAINER_CORE_VPN.
const String kExplainerCoreVpn =
    'Always on: licence + keygen entitlement, cryptographic HELLO/session, and '
    'system residual tunnel (capture your public IP through the VPN node). '
    'Those cannot be turned off here — without them this is not a working VPN.';

/// Residual IPv4 is product always-on (not user-adjustable).
const String kExplainerResidualIpv4 =
    'IPv4 residual is always on: full-tunnel IPv4 capture via dual /1 routes so '
    'residual public IPv4 uses the VPN node. This is core residual protection '
    'and cannot be turned off in Settings.';

/// Residual IPv6 remains user-toggleable (default ON).
const String kExplainerResidualIpv6 =
    'IPv6 residual blocks the ISP IPv6 path while residual is connected so '
    'dual-stack devices do not leak over IPv6. ON (default) = IPv6 ISP path '
    'blocked for residual sessions. OFF = IPv6 may use the ISP; status will not '
    'claim IPv6 is protected. Takes effect on next Connect.';

const String kTooltipResidualIpv4 =
    'Residual IPv4 capture is always on (product policy).';

const String kTooltipResidualIpv6 =
    'When on, residual sessions block ISP IPv6 leaks. When off, IPv6 may bypass '
    'the tunnel.';

const String kPingStatsDisclaimer =
    'Best-effort TCP probe RTT to product entry (and exit when multi-hop is ON). '
    'Not a contractual SLA or browser speedbench.';

const String kConnectionLogDisclaimer =
    'Connection events and support diagnostics (app version, platform, connect '
    'outcome / error text) are stored only on this device in a hidden file '
    '(.rpt_support_log.jsonl under the product data folder). Restore Privacy does '
    'not upload this log to the node or any remote collector. Use Export log, or '
    'copy the hidden file, and email it to support yourself.';

/// Where to find the on-device support log (user email handoff — no auto-upload).
const String kSupportLogPathWindows =
    r'%LOCALAPPDATA%\RestorePrivacy\.rpt_support_log.jsonl';
const String kSupportLogPathLinux =
    '~/.local/share/restore-privacy/.rpt_support_log.jsonl';
const String kSupportLogFindHint =
    'Hidden support log (device only): Windows $kSupportLogPathWindows · '
    'Linux $kSupportLogPathLinux · or Settings → Export log, then email the file yourself.';

const String kLeakTestDisclaimer =
    'Leak test checks residual public-IP capture and tunnel DNS posture on this '
    'device. Multi-hop residual is opt-in (RPT_MULTIHOP_ENABLED=1) and means residual '
    'via the exit hop — not full intermediate encapsulation or perfect leak-proofing '
    'on every OEM.';
