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
    'Multi-hop residual routes via an exit hop (e.g. entry → Romania exit) so '
    'egress IP is the exit, not only the Iceland entry. '
    'OFF (product default) = single hop to the entry node — lower lag/ping. '
    'ON = extra hop path when configured — more privacy of path, higher latency. '
    'Requires residual multi-hop routing; does not replace licence/keygen unlock. '
    'While connected, Disconnect then Connect to re-establish via the new hop.';

/// Mirrors EXPLAINER_CORE_VPN.
const String kExplainerCoreVpn =
    'Always on: licence + keygen entitlement, cryptographic HELLO/session, and '
    'system residual tunnel (capture your public IP through the VPN node). '
    'Those cannot be turned off here — without them this is not a working VPN.';

const String kPingStatsDisclaimer =
    'Best-effort TCP probe RTT to product entry (and exit when multi-hop is ON). '
    'Not a contractual SLA or browser speedbench.';

const String kConnectionLogDisclaimer =
    'Connection events are stored only on this device. Restore Privacy does not '
    'upload this log to the node or any remote collector. Export saves a local file '
    'you choose to keep or share.';

const String kLeakTestDisclaimer =
    'Leak test checks residual public-IP capture and tunnel DNS posture on this '
    'device. Multi-hop residual is opt-in (RPT_MULTIHOP_ENABLED=1) and means residual '
    'via the exit hop — not full intermediate encapsulation or perfect leak-proofing '
    'on every OEM.';
