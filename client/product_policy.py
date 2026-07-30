"""Product-level feature policy for residual DATA on every platform.

Traffic shaping (padding, send jitter, cover traffic), outer obfuscation
(QUIC-mimic wrap), and multi-hop residual are controlled by:

1. **Operator env** (when the key is set): ``RPT_TRAFFIC_SHAPE``, ``RPT_OBFS``,
   ``RPT_MULTIHOP_ENABLED`` — wins for tests / self-host.
2. **User Settings** (when env key is unset): privacy-scale toggles in the
   product settings store (pre-adjustment defaults lean-off: shaping,
   outer obfuscation, and multi-hop all **off**; residual VPN core stays
   always-on and is not a user-offable Settings switch).

Bounded optional layers can be turned **on** for stronger fingerprint
resistance; residual VPN (HELLO, session crypto, system capture) stays
required either way. Not a DPI-undetectability claim.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from node.obfuscation import product_obfuscation_enabled
from node.traffic_shape import DEFAULT_TRAFFIC_SHAPE, TrafficShapePolicy

# Product enabled policy (used when traffic shape is on / default).
# Bounds mirrored by Android RptTrafficShape + Apple RptTrafficShape.
PRODUCT_ENABLED_TRAFFIC_SHAPE = TrafficShapePolicy(
    padding=True,
    pad_bucket=128,
    jitter_ms_max=40,
    cover_traffic=True,
    cover_interval_s=2.0,
)

# --- Customer-facing explainers (Settings UI; honest speed vs privacy) ---

EXPLAINER_TRAFFIC_SHAPE = (
    "Traffic shaping pads packet sizes, adds small send jitter, and sends "
    "periodic cover (dummy) frames so traffic is harder to fingerprint. "
    "OFF (product default) = leaner packets and less cover → snappier browsing; "
    "weaker against size/timing analysis. "
    "ON = stronger privacy against coarse traffic analysis; slightly more "
    "bandwidth and latency. Residual VPN crypto and tunnel still work either way."
)

EXPLAINER_OUTER_OBFUSCATION = (
    "Outer obfuscation wraps residual UDP in a QUIC-like shell so clear RPT "
    "framing is not obvious on the wire. "
    "OFF (product default) = bare RPT frames (node still accepts both) → "
    "slightly less overhead; easier for simple classifiers to spot product traffic. "
    "ON = better blend with generic encrypted UDP; small CPU/header cost. "
    "Not a claim of full DPI-undetectability either way."
)

EXPLAINER_MULTIHOP = (
    "Multi-hop residual routes via an exit hop (entry → Germany exit) so "
    "egress IP is the exit, not only the selected entry (default Germany). "
    "OFF (product default) = single hop to the entry node — lower lag/ping. "
    "ON = extra hop path when configured — more privacy of path, higher latency. "
    "Requires residual multi-hop routing; does not replace licence/keygen unlock."
)

EXPLAINER_CORE_VPN = (
    "Always on: licence + keygen entitlement, cryptographic HELLO/session, and "
    "system residual tunnel (capture your public IP through the VPN node). "
    "Those cannot be turned off here — without them this is not a working VPN."
)

# Connected residual still encrypts OS traffic — honest power/CPU note (P2).
EXPLAINER_CONNECTED_IDLE_POWER = (
    "While Connected, residual full-tunnel protection stays active even if you are not "
    "browsing: background app and system traffic still goes through the VPN crypto path, "
    "which uses battery and CPU. Disconnect when you do not need protection. "
    "Traffic shaping ON also sends periodic cover frames (~every 2s), which uses a little "
    "extra power and data."
)


@dataclass(frozen=True)
class PrivacyScalePrefs:
    """Optional residual privacy layers (off until the user opts in)."""

    traffic_shape: bool = False
    outer_obfuscation: bool = False
    multihop: bool = False  # product residual baseline: single-hop

    def to_dict(self) -> dict[str, bool]:
        return {
            "traffic_shape": bool(self.traffic_shape),
            "outer_obfuscation": bool(self.outer_obfuscation),
            "multihop": bool(self.multihop),
        }


@dataclass(frozen=True)
class ResolvedPrivacyPolicy:
    """Observable residual privacy policy for a session (not cosmetic)."""

    traffic_shape_enabled: bool
    outer_obfuscation_enabled: bool
    multihop_enabled: bool
    residual_vpn_core: bool = True  # always true — never user-disabled
    admission_and_crypto: bool = True  # always true

    def traffic_shape_policy(self) -> TrafficShapePolicy:
        if self.traffic_shape_enabled:
            return PRODUCT_ENABLED_TRAFFIC_SHAPE
        return DEFAULT_TRAFFIC_SHAPE


def _env_key_set(name: str) -> bool:
    return name in os.environ and str(os.environ.get(name, "")).strip() != ""


def _env_truthy(name: str, *, default_on: bool = True) -> bool:
    raw = os.environ.get(name, "1" if default_on else "0").strip().lower()
    if raw in ("0", "false", "off", "no", "disabled"):
        return False
    if raw in ("1", "true", "on", "yes", "enabled"):
        return True
    return default_on


def load_privacy_scale_prefs(
    settings_path: Optional[object] = None,
) -> PrivacyScalePrefs:
    """Load user privacy-scale toggles from the platform settings store.

    ``settings_path`` is an optional Path for tests (Windows/Linux store).
    Free tier (``RPT_FREE_TIER``) forces lean Iceland-only prefs (all off).
    """
    try:
        from client.free_tier import free_tier_enabled, free_tier_privacy_scale_locked_off

        if free_tier_enabled():
            shape, obfs, mh = free_tier_privacy_scale_locked_off()
            return PrivacyScalePrefs(
                traffic_shape=shape,
                outer_obfuscation=obfs,
                multihop=mh,
            )
    except Exception:  # noqa: BLE001
        pass
    try:
        if os.name == "nt":
            from client.windows.settings_store import load_settings
        else:
            from client.linux.settings_store import load_settings

        s = load_settings(path=settings_path)  # type: ignore[arg-type]
        return PrivacyScalePrefs(
            traffic_shape=bool(getattr(s, "privacy_traffic_shape", False)),
            outer_obfuscation=bool(getattr(s, "privacy_outer_obfuscation", False)),
            multihop=bool(getattr(s, "privacy_multihop", False)),
        )
    except Exception:  # noqa: BLE001
        return PrivacyScalePrefs()


def _env_traffic_shape_raw() -> str:
    # Lean residual baseline when env is set without a value-like toggle.
    return os.environ.get("RPT_TRAFFIC_SHAPE", "0").strip().lower()


def traffic_shape_enabled_by_env() -> bool:
    """True when env says shaping is on (only used when RPT_TRAFFIC_SHAPE is set)."""
    raw = _env_traffic_shape_raw()
    if raw in ("0", "false", "off", "no", "disabled", ""):
        return False
    if raw in ("1", "true", "on", "yes", "enabled"):
        return True
    return False


def traffic_shape_enabled(
    *,
    prefs: PrivacyScalePrefs | None = None,
) -> bool:
    """Resolved traffic-shaping enable: env key wins if set, else user Settings."""
    try:
        from client.free_tier import free_tier_enabled

        if free_tier_enabled():
            return False
    except Exception:  # noqa: BLE001
        pass
    if _env_key_set("RPT_TRAFFIC_SHAPE"):
        return traffic_shape_enabled_by_env()
    p = prefs if prefs is not None else load_privacy_scale_prefs()
    return bool(p.traffic_shape)


def product_dataplane_traffic_shape(
    *,
    prefs: PrivacyScalePrefs | None = None,
) -> TrafficShapePolicy:
    """Policy passed into ``RptDataPlane`` for product Windows/Linux residual tunnels."""
    if traffic_shape_enabled(prefs=prefs):
        return PRODUCT_ENABLED_TRAFFIC_SHAPE
    return DEFAULT_TRAFFIC_SHAPE


def product_outer_obfuscation_enabled(
    *,
    prefs: PrivacyScalePrefs | None = None,
) -> bool:
    """Outer QUIC-mimic wrap: env ``RPT_OBFS`` if set, else user Settings (default off)."""
    try:
        from client.free_tier import free_tier_enabled

        if free_tier_enabled():
            return False
    except Exception:  # noqa: BLE001
        pass
    if _env_key_set("RPT_OBFS"):
        return product_obfuscation_enabled()
    p = prefs if prefs is not None else load_privacy_scale_prefs()
    return bool(p.outer_obfuscation)


def product_multihop_enabled(
    *,
    prefs: PrivacyScalePrefs | None = None,
) -> bool:
    """Multi-hop residual: env ``RPT_MULTIHOP_ENABLED`` if set, else Settings (default off)."""
    try:
        from client.free_tier import free_tier_enabled

        if free_tier_enabled():
            return False
    except Exception:  # noqa: BLE001
        pass
    if _env_key_set("RPT_MULTIHOP_ENABLED"):
        return _env_truthy("RPT_MULTIHOP_ENABLED", default_on=False)
    p = prefs if prefs is not None else load_privacy_scale_prefs()
    return bool(p.multihop)


def resolve_privacy_policy(
    *,
    prefs: PrivacyScalePrefs | None = None,
) -> ResolvedPrivacyPolicy:
    """Full residual privacy policy snapshot used for Connect/session honesty."""
    p = prefs if prefs is not None else load_privacy_scale_prefs()
    return ResolvedPrivacyPolicy(
        traffic_shape_enabled=traffic_shape_enabled(prefs=p),
        outer_obfuscation_enabled=product_outer_obfuscation_enabled(prefs=p),
        multihop_enabled=product_multihop_enabled(prefs=p),
        residual_vpn_core=True,
        admission_and_crypto=True,
    )
