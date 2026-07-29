"""Private residual capacity signal (operator/token only — never public status).

In-memory live session count is used for **routing capacity utilization** only.
Public HTML/JSON stay title-only via :func:`node.aggregate_metrics.filter_public_status`.

Product soft budgets (operator allowance — not auto NIC line-rate):

| Peer | Bandwidth budget | Session soft max |
|------|------------------|------------------|
| RO Romania (legacy) | **unlimited-class** (extendable at cost) | 256 (base) |
| IS Iceland | **unlimited-class** (extendable at cost) | 512 |
| DE Germany (dedicated) | **unlimited-class** (30 TB class entitlement) | 1024 |
| US | 200 Mbps fixed product budget | 512 |

Session numbers are a **soft** utilization hint for residual routing, not a hard
public admission lock. IS/DE/RO bandwidth is essentially unlimited in product terms
because extended bandwidth is available at extra cost — not a fixed 100 Mbps
product budget. US keeps a fixed 200 Mbps operator allowance.

DE session soft max (1024) is sized for the dedicated residual host
(8 vCPU / 32 GB RAM / 30 TB traffic class): above IS/US 512, soft utilization
only — not a hard admission lock.
"""

from __future__ import annotations

import hmac
import os
from typing import Any, Mapping, Optional

# Soft cap for utilization math (not a hard admission gate).
# RO base; IS/US 512; DE dedicated (8 vCPU / 32 GB) → 1024.
DEFAULT_MAX_SESSIONS = 256  # RO base (legacy peer)
DEFAULT_MAX_SESSIONS_IS = 512  # Iceland
DEFAULT_MAX_SESSIONS_US = 512
DEFAULT_MAX_SESSIONS_DE = 1024  # dedicated DE residual host
ENV_CAPACITY_TOKEN = "RPT_CAPACITY_TOKEN"
ENV_MAX_SESSIONS = "RPT_NODE_MAX_SESSIONS"
ENV_PEER_CODE = "RPT_NODE_PEER_CODE"  # IS | DE | US | RO
ENV_NODE_HOST = "RPT_NODE_HOST"

# Mbps product allowances (operator budget). IS/DE/RO omitted = unlimited-class.
_MBPS = 1_000_000
PRODUCT_BANDWIDTH_CAP_BPS: dict[str, int] = {
    "US": 200 * _MBPS,
    "5.161.242.85": 200 * _MBPS,
}

# Peers with extendable bandwidth at cost — no fixed product Mbps budget.
PRODUCT_UNLIMITED_BANDWIDTH_CODES = frozenset({"IS", "DE", "RO"})
PRODUCT_UNLIMITED_BANDWIDTH_HOSTS = frozenset(
    {"82.221.101.241", "178.105.187.178", "185.146.232.107"}
)

# Session soft max: DE dedicated > IS/US; RO base (legacy)
PRODUCT_SESSION_SOFT_MAX: dict[str, int] = {
    "RO": DEFAULT_MAX_SESSIONS,
    "IS": DEFAULT_MAX_SESSIONS_IS,
    "US": DEFAULT_MAX_SESSIONS_US,
    "DE": DEFAULT_MAX_SESSIONS_DE,
    "185.146.232.107": DEFAULT_MAX_SESSIONS,
    "82.221.101.241": DEFAULT_MAX_SESSIONS_IS,
    "5.161.242.85": DEFAULT_MAX_SESSIONS_US,
    "178.105.187.178": DEFAULT_MAX_SESSIONS_DE,
}


def _lookup_product_map(m: Mapping[str, int], *keys: str) -> int | None:
    for k in keys:
        key = str(k or "").strip()
        if not key:
            continue
        if key in m:
            return int(m[key])
        up = key.upper()
        if up in m:
            return int(m[up])
    return None


def product_session_soft_max(
    *,
    code: str = "",
    host: str = "",
) -> int | None:
    """Product session soft max for a catalog peer (None if unknown peer)."""
    return _lookup_product_map(PRODUCT_SESSION_SOFT_MAX, code, host)


def product_bandwidth_unlimited(
    *,
    code: str = "",
    host: str = "",
) -> bool:
    """True when product treats peer bandwidth as unlimited-class (IS/DE/RO)."""
    c = (code or "").strip().upper()
    h = (host or "").strip()
    if c in PRODUCT_UNLIMITED_BANDWIDTH_CODES:
        return True
    if h in PRODUCT_UNLIMITED_BANDWIDTH_HOSTS:
        return True
    return False


def product_bandwidth_cap_bps(
    *,
    code: str = "",
    host: str = "",
) -> int | None:
    """Product bandwidth allowance (bits/s), or None if unlimited-class / unknown.

    IS/DE/RO return None (extendable bandwidth at cost — no fixed product budget).
    US returns 200 Mbps.
    """
    if product_bandwidth_unlimited(code=code, host=host):
        return None
    return _lookup_product_map(PRODUCT_BANDWIDTH_CAP_BPS, code, host)


def resolve_peer_identity(
    env: Mapping[str, str] | None = None,
    *,
    code: str = "",
    host: str = "",
) -> tuple[str, str]:
    """Return (code, host) from explicit args or node env."""
    e = env if env is not None else os.environ
    c = (code or str(e.get(ENV_PEER_CODE, "") or e.get("RPT_PEER_CODE", "") or "")).strip().upper()
    h = (host or str(e.get(ENV_NODE_HOST, "") or e.get("RPT_RESIDUAL_HOST", "") or "")).strip()
    if not c and h:
        # Infer code from known catalog hosts
        for k, v in (
            ("82.221.101.241", "IS"),
            ("178.105.187.178", "DE"),
            ("185.146.232.107", "RO"),
            ("5.161.242.85", "US"),
        ):
            if h == k:
                c = v
                break
    return c, h


def default_max_sessions(
    env: Mapping[str, str] | None = None,
    *,
    code: str = "",
    host: str = "",
) -> int:
    """Soft max sessions for utilization = live / max.

    Priority:
      1. ``RPT_NODE_MAX_SESSIONS`` (explicit operator override)
      2. Product map for peer code/host (DE 1024; IS/US 512; RO 256)
      3. Flat ``DEFAULT_MAX_SESSIONS`` (256) for unknown peers
    """
    e = env if env is not None else os.environ
    raw = str(e.get(ENV_MAX_SESSIONS, "") or "").strip()
    if raw:
        try:
            n = int(raw)
            return max(1, n)
        except ValueError:
            pass
    c, h = resolve_peer_identity(e, code=code, host=host)
    prod = product_session_soft_max(code=c, host=h)
    if prod is not None:
        return max(1, int(prod))
    return DEFAULT_MAX_SESSIONS


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


def bandwidth_cap_bps(
    env: Mapping[str, str] | None = None,
    *,
    code: str = "",
    host: str = "",
) -> int | None:
    """Optional process-wide bandwidth capability (bits/s) for admin utilization.

    ``RPT_NODE_BANDWIDTH_CAP_BPS`` — soft operator-configured link budget, not
    measured NIC line-rate unless the operator sets it to that. When unset,
    falls back to product peer allowance (IS/DE/RO unlimited-class → None;
    US 200 Mbps). Explicit env still wins if set (legacy host pin).
    """
    e = env if env is not None else os.environ
    raw = str(e.get("RPT_NODE_BANDWIDTH_CAP_BPS", "") or "").strip()
    if raw:
        # 0 or "unlimited" → treat as no fixed budget
        if raw.lower() in ("0", "unlimited", "none", "-"):
            return None
        try:
            n = int(raw)
        except ValueError:
            n = 0
        if n > 0:
            return n
    c, h = resolve_peer_identity(e, code=code, host=host)
    return product_bandwidth_cap_bps(code=c, host=h)


def build_private_capacity_payload(
    *,
    live: int,
    capacity: int | None = None,
    host: str = "",
    env: Mapping[str, str] | None = None,
    total_bytes_in: int | None = None,
    total_bytes_out: int | None = None,
    total_bytes_relayed: int | None = None,
    process_uptime_sec: int | None = None,
    bandwidth_cap_bps_value: int | None = None,
    code: str = "",
) -> dict[str, Any]:
    """JSON body for private capacity endpoint (not for public status).

    Includes session utilization plus optional process-wide byte counters for
    operator admin bandwidth used-vs-capability (never public status).
    """
    e = env if env is not None else os.environ
    c, h = resolve_peer_identity(e, code=code, host=host)
    cap = (
        int(capacity)
        if capacity is not None
        else default_max_sessions(e, code=c, host=h)
    )
    util = utilization_from_counts(live, cap)
    out: dict[str, Any] = {
        "utilization": util,
        "live": max(0, int(live)),
        "capacity": max(1, int(cap)),
        "private": True,
    }
    if h:
        out["host"] = h
    if c:
        out["peer_code"] = c
    # Process-wide aggregates (operator / admin only)
    if total_bytes_in is not None:
        out["total_bytes_in"] = max(0, int(total_bytes_in))
    if total_bytes_out is not None:
        out["total_bytes_out"] = max(0, int(total_bytes_out))
    if total_bytes_relayed is not None:
        out["total_bytes_relayed"] = max(0, int(total_bytes_relayed))
    elif total_bytes_in is not None or total_bytes_out is not None:
        bi = max(0, int(total_bytes_in or 0))
        bo = max(0, int(total_bytes_out or 0))
        out["total_bytes_relayed"] = bi + bo
    if process_uptime_sec is not None:
        out["process_uptime_sec"] = max(0, int(process_uptime_sec))
    bcap = (
        bandwidth_cap_bps_value
        if bandwidth_cap_bps_value is not None
        else bandwidth_cap_bps(e, code=c, host=h)
    )
    if bcap is not None and bcap > 0:
        out["bandwidth_cap_bps"] = int(bcap)
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
