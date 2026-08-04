"""Lean residual session keep-alive policy (client data planes).

Node sessions prune after :data:`node.sessions.DEFAULT_SESSION_IDLE_SEC` (~60s)
without DATA or KEEPALIVE. Product residual clients must send RPT2 KEEPALIVE
on a multi-second period **strictly less** than that idle window, independent
of user browsing and independent of traffic-shape cover (~2s RPTC, opt-in).

Windows residual idle is out of scope for this module's ship tests (operator
platform); Linux/Android/Apple share this interval contract.
"""

from __future__ import annotations

# Must stay clearly below node DEFAULT_SESSION_IDLE_SEC (60s) with margin.
RESIDUAL_KEEPALIVE_INTERVAL_SEC = 25.0

# Absolute upper bound for any client keep-alive period (seconds).
RESIDUAL_KEEPALIVE_INTERVAL_MAX_SEC = 45.0

# Absolute lower bound — avoid sub-second spin / cover-like churn.
RESIDUAL_KEEPALIVE_INTERVAL_MIN_SEC = 5.0


def residual_keepalive_interval_sec(
    requested: float | None = None,
    *,
    node_idle_sec: float = 60.0,
) -> float:
    """Return a lean keep-alive period that stays under *node_idle_sec*.

    Pure: no I/O. Used by Linux dataplane and unit tests; other platforms
    mirror the same numbers in native constants.
    """
    base = (
        float(requested)
        if requested is not None
        else float(RESIDUAL_KEEPALIVE_INTERVAL_SEC)
    )
    # Clamp to product lean band
    interval = max(
        RESIDUAL_KEEPALIVE_INTERVAL_MIN_SEC,
        min(RESIDUAL_KEEPALIVE_INTERVAL_MAX_SEC, base),
    )
    # Hard margin: never meet or exceed node idle prune
    margin = max(5.0, float(node_idle_sec) * 0.25)
    ceiling = float(node_idle_sec) - margin
    if ceiling < RESIDUAL_KEEPALIVE_INTERVAL_MIN_SEC:
        ceiling = RESIDUAL_KEEPALIVE_INTERVAL_MIN_SEC
    return min(interval, ceiling)


def residual_keepalive_is_lean(interval_sec: float) -> bool:
    """True when *interval_sec* is a multi-second lean period (not cover-like)."""
    return float(interval_sec) >= RESIDUAL_KEEPALIVE_INTERVAL_MIN_SEC


def residual_keepalive_beats_node_idle(
    interval_sec: float,
    node_idle_sec: float = 60.0,
) -> bool:
    """True when keep-alive fires strictly before node idle prune."""
    return float(interval_sec) < float(node_idle_sec)
