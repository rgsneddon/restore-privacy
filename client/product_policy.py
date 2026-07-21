"""Product-level feature policy for residual DATA on every platform.

Traffic shaping (padding, send jitter, cover traffic) is controlled by
``RPT_TRAFFIC_SHAPE`` on the Python Windows/Linux residual path:

- ``1`` / ``true`` / ``on`` / unset → **enabled** product policy (bounded)
- ``0`` / ``false`` / ``off`` → all features off (DEFAULT_TRAFFIC_SHAPE)

Native residual (Android VPN service, iOS/macOS Packet Tunnel) ships the same
product defaults in platform constants (pad 128, cover ~2s, jitter ≤40ms) with
outer obfuscation on by default (``RPT_OBFS`` / ``productObfsEnabled``).

Bounded defaults keep bandwidth impact modest; not a DPI-undetectability claim.
"""

from __future__ import annotations

import os

from node.obfuscation import product_obfuscation_enabled
from node.traffic_shape import DEFAULT_TRAFFIC_SHAPE, TrafficShapePolicy

# Product enabled policy (used when RPT_TRAFFIC_SHAPE is on / default).
# Bounds mirrored by Android RptTrafficShape + Apple RptTrafficShape.
PRODUCT_ENABLED_TRAFFIC_SHAPE = TrafficShapePolicy(
    padding=True,
    pad_bucket=128,
    jitter_ms_max=40,
    cover_traffic=True,
    cover_interval_s=2.0,
)


def _env_traffic_shape_raw() -> str:
    return os.environ.get("RPT_TRAFFIC_SHAPE", "1").strip().lower()


def traffic_shape_enabled_by_env() -> bool:
    """True when product traffic shaping should be applied to the DATA plane."""
    raw = _env_traffic_shape_raw()
    if raw in ("0", "false", "off", "no", "disabled"):
        return False
    # Default "1" / empty / true / on / yes
    return True


def product_dataplane_traffic_shape() -> TrafficShapePolicy:
    """Policy passed into ``RptDataPlane`` for product Windows/Linux residual tunnels."""
    if traffic_shape_enabled_by_env():
        return PRODUCT_ENABLED_TRAFFIC_SHAPE
    return DEFAULT_TRAFFIC_SHAPE


def product_outer_obfuscation_enabled() -> bool:
    """Outer QUIC-mimic wrap default-on for residual UDP (``RPT_OBFS=0`` to opt out)."""
    return product_obfuscation_enabled()
