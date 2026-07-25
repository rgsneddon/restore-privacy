"""Private residual capacity signal (operator/token only — never public status).

In-memory live session count is used for **routing capacity utilization** only.
Public HTML/JSON stay title-only via :func:`node.aggregate_metrics.filter_public_status`.
"""

from __future__ import annotations

import hmac
import os
from typing import Any, Mapping, Optional

# Soft cap for utilization math (not a hard admission gate).
DEFAULT_MAX_SESSIONS = 256
ENV_CAPACITY_TOKEN = "RPT_CAPACITY_TOKEN"
ENV_MAX_SESSIONS = "RPT_NODE_MAX_SESSIONS"


def default_max_sessions(env: Mapping[str, str] | None = None) -> int:
    e = env if env is not None else os.environ
    raw = str(e.get(ENV_MAX_SESSIONS, "") or "").strip()
    if not raw:
        return DEFAULT_MAX_SESSIONS
    try:
        n = int(raw)
    except ValueError:
        return DEFAULT_MAX_SESSIONS
    return max(1, n)


def utilization_from_counts(
    live: int,
    capacity: int,
) -> float:
    """Map live sessions / capacity → utilization in [0.0, 1.0]."""
    cap = max(1, int(capacity))
    live_n = max(0, int(live))
    u = live_n / float(cap)
    if u < 0.0:
        return 0.0
    if u > 1.0:
        return 1.0
    return float(u)


def build_private_capacity_payload(
    *,
    live: int,
    capacity: int | None = None,
    host: str = "",
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """JSON body for private capacity endpoint (not for public status)."""
    cap = int(capacity) if capacity is not None else default_max_sessions(env)
    util = utilization_from_counts(live, cap)
    out: dict[str, Any] = {
        "utilization": util,
        "live": max(0, int(live)),
        "capacity": max(1, int(cap)),
        "private": True,
    }
    h = (host or "").strip()
    if h:
        out["host"] = h
    return out


def capacity_token_configured(env: Mapping[str, str] | None = None) -> str:
    e = env if env is not None else os.environ
    return str(e.get(ENV_CAPACITY_TOKEN, "") or "").strip()


def authorize_capacity_request(
    *,
    authorization_header: str = "",
    x_token_header: str = "",
    query_token: str = "",
    env: Mapping[str, str] | None = None,
) -> tuple[bool, str]:
    """Validate private capacity token. Empty configured token → refuse (fail closed)."""
    expected = capacity_token_configured(env)
    if not expected:
        return False, "capacity token not configured"
    candidates: list[str] = []
    auth = (authorization_header or "").strip()
    if auth.lower().startswith("bearer "):
        candidates.append(auth[7:].strip())
    xt = (x_token_header or "").strip()
    if xt:
        candidates.append(xt)
    qt = (query_token or "").strip()
    if qt:
        candidates.append(qt)
    for c in candidates:
        if c and hmac.compare_digest(c, expected):
            return True, ""
    return False, "unauthorized"


def public_status_must_not_include_capacity(public: Mapping[str, Any]) -> bool:
    """True when public dict is title-only safe (no capacity/session fields)."""
    keys = {str(k).lower() for k in (public or {}).keys()}
    forbidden = {
        "utilization",
        "live",
        "capacity",
        "private",
        "clients_connected",
        "active_sessions",
        "sessions",
        "live_clients",
    }
    return keys <= {"title"} and not (keys & forbidden)
