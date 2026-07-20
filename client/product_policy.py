"""Product-level feature policy for the shipped client DATA path.

Traffic shaping (padding, send jitter, cover traffic) is controlled by
``RPT_TRAFFIC_SHAPE``:

- ``1`` / ``true`` / ``on`` / unset → **enabled** product policy (bounded)
- ``0`` / ``false`` / ``off`` → all features off (DEFAULT_TRAFFIC_SHAPE)

Bounded defaults keep bandwidth impact modest; not a DPI-undetectability claim.
"""

from __future__ import annotations

import os

from node.traffic_shape import DEFAULT_TRAFFIC_SHAPE, TrafficShapePolicy

# Product enabled policy (used when RPT_TRAFFIC_SHAPE is on / default).
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
    """Policy passed into ``RptDataPlane`` for product Windows/Linux tunnels."""
    if traffic_shape_enabled_by_env():
        return PRODUCT_ENABLED_TRAFFIC_SHAPE
    return DEFAULT_TRAFFIC_SHAPE
