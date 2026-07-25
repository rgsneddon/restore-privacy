"""Shared product honesty copy for Settings transparency surfaces.

Windows Tk and Flutter Settings import / mirror these strings so DPI and
traffic-analysis disclaimers stay greppable and consistent.
"""

from __future__ import annotations

# Titles / short labels (Settings cards)
DPI_MITIGATION_TITLE = "Traffic analysis mitigations"
CONNECTION_LOG_TITLE = "Connection log"
LEAK_TEST_TITLE = "Leak test"
LEAK_TEST_BUTTON = "Run leak test"
EXPORT_LOG_BUTTON = "Export log"

# Plain-language disclaimer: mitigation ≠ undetectability
DPI_MITIGATION_DISCLAIMER = (
    "Traffic shaping (padding, send jitter, and cover traffic) and outer obfuscation "
    "default off on residual paths (lean residual) until you turn them on in Settings. "
    "When enabled they reduce coarse traffic analysis, but they are mitigations only — "
    "not a guarantee of DPI-undetectability or full pluggable-transport parity "
    "(for example obfs4, meek, or V2Ray). A determined network observer may still "
    "fingerprint the tunnel."
)

CONNECTION_LOG_DISCLAIMER = (
    "Connection events and support diagnostics (app version, platform, connect "
    "outcome / error text) are stored only on this device. Restore Privacy does not "
    "upload this log to the node or any remote collector. Export saves a local file "
    "you can email to support yourself."
)

LEAK_TEST_DISCLAIMER = (
    "Leak test checks residual public-IP capture and tunnel DNS posture on this "
    "device. Multi-hop residual is opt-in (RPT_MULTIHOP_ENABLED=1) and means residual "
    "via the exit hop — not full intermediate encapsulation or perfect leak-proofing "
    "on every OEM."
)

# Substring gates used by tests (must appear in product Settings UI sources)
DPI_DISCLAIMER_MARKERS: tuple[str, ...] = (
    "mitigations only",
    "DPI-undetectability",
    "pluggable-transport",
)
