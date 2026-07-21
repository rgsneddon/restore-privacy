/// Shared product honesty copy for Settings (mirrors client/transparency_copy.py).

const String kDpiMitigationTitle = 'Traffic analysis mitigations';
const String kConnectionLogTitle = 'Connection log';
const String kLeakTestTitle = 'Leak test';
const String kLeakTestButton = 'Run leak test';
const String kExportLogButton = 'Export log';

/// Plain-language: mitigation ≠ DPI-undetectability.
const String kDpiMitigationDisclaimer =
    'Traffic shaping (padding, send jitter, and cover traffic) and outer obfuscation '
    'are on by default on residual paths for all platforms. They reduce '
    'coarse traffic analysis, but they are mitigations only — not a guarantee of '
    'DPI-undetectability or full pluggable-transport parity (for example obfs4, '
    'meek, or V2Ray). A determined network observer may still fingerprint the tunnel.';

const String kConnectionLogDisclaimer =
    'Connection events are stored only on this device. Restore Privacy does not '
    'upload this log to the node or any remote collector. Export saves a local file '
    'you choose to keep or share.';

const String kLeakTestDisclaimer =
    'Leak test checks residual public-IP capture and tunnel DNS posture on this '
    'device. Multi-hop residual is opt-in (RPT_MULTIHOP_ENABLED=1) and means residual '
    'via the exit hop — not full intermediate encapsulation or perfect leak-proofing '
    'on every OEM.';
