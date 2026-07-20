"""Aggregate, non-identifying monitoring counters (process-wide only).

Public status stays **minimal** (product title). These counters exist for
operator health in-memory only — they never key by client id, session id, IP,
or identity, and they must not become durable per-client activity logs.

Example allowed aggregates: total_bytes_in / total_bytes_out (node-wide).
Forbidden: per-client bandwidth, session lists, live client counts as metrics.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Mapping, MutableMapping, Optional

# --- Public status (what HTML/JSON may show) ---------------------------------

ALLOWED_PUBLIC_STATUS_KEYS: frozenset[str] = frozenset({"title"})

# Keys that must never appear on a public status surface (counts, identities, lists).
FORBIDDEN_PUBLIC_METRIC_KEYS: frozenset[str] = frozenset(
    {
        "clients_connected",
        "current_clients",
        "active_sessions",
        "live_clients",
        "connected_clients",
        "total",
        "total_clients",
        "clients_total",
        "lifetime",
        "lifetime_clients",
        "cumulative",
        "peak",
        "history",
        "ip",
        "ips",
        "client_ip",
        "client_ips",
        "clients",
        "sessions",
        "session_ids",
        "session_list",
        "per_client",
        "per_session",
        "by_client",
        "by_session",
        "client_id",
        "client_ids",
        "user",
        "users",
        "username",
        "identity",
        "identities",
        "pubkey",
        "pubkeys",
        "ed25519",
        "bandwidth_per_client",
        "bytes_per_client",
        "client_bandwidth",
        "session_bandwidth",
    }
)

# Process-wide aggregates operators may hold in memory (not public by default).
ALLOWED_AGGREGATE_INTERNAL_KEYS: frozenset[str] = frozenset(
    {
        "total_bytes_in",
        "total_bytes_out",
        "total_bytes_relayed",
        "total_datagrams_in",
        "total_datagrams_out",
        "process_uptime_sec",
    }
)

_IDENTIFYING_KEY_RE = re.compile(
    r"(per[_-]?client|per[_-]?session|client[_-]?id|session[_-]?id|"
    r"by[_-]?client|by[_-]?session|user[_-]?id|peer[_-]?id|"
    r"client[_-]?ip|source[_-]?ip|remote[_-]?addr)",
    re.IGNORECASE,
)


def is_identifying_metric_key(key: str) -> bool:
    """True when a metric key implies per-client / identity attribution."""
    k = str(key or "").strip()
    if not k:
        return False
    low = k.lower()
    if low in FORBIDDEN_PUBLIC_METRIC_KEYS:
        return True
    if low in ALLOWED_AGGREGATE_INTERNAL_KEYS:
        return False
    if _IDENTIFYING_KEY_RE.search(low):
        return True
    # Nested maps keyed like client_<hex>
    if low.startswith("client_") or low.startswith("session_"):
        if low not in ("client_net",):  # routing config, not a metric
            return True
    return False


def is_allowed_aggregate_key(key: str) -> bool:
    return str(key or "").strip().lower() in ALLOWED_AGGREGATE_INTERNAL_KEYS


def filter_public_status(payload: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """Strict public JSON: product title only (no counts, lists, IPs, aggregates).

    Aggregate bandwidth may exist in process memory but is **not** published here
    so the status page remains minimal.
    """
    data = dict(payload or {})
    title = str(data.get("title", "RESTORE PRIVACY") or "RESTORE PRIVACY")
    return {"title": title}


def assert_public_status_minimal(payload: Mapping[str, Any]) -> list[str]:
    """Return violations if payload is not title-only public status."""
    violations: list[str] = []
    keys = set(payload.keys())
    extra = keys - ALLOWED_PUBLIC_STATUS_KEYS
    for k in sorted(extra):
        violations.append(f"public status must not include {k!r}")
    for k in keys:
        if is_identifying_metric_key(k):
            violations.append(f"identifying public metric key: {k!r}")
    return violations


def assert_metrics_non_identifying(metrics: Mapping[str, Any]) -> list[str]:
    """Return violations if *metrics* contains identifying / per-client keys.

    Nested dict values under an allowed aggregate key are not expected; any
    nested mapping is treated as identifying (would hide per-client maps).
    """
    violations: list[str] = []
    for key, value in metrics.items():
        sk = str(key)
        if is_identifying_metric_key(sk):
            violations.append(f"identifying metric key: {sk!r}")
            continue
        if not is_allowed_aggregate_key(sk) and sk.lower() not in ("title",):
            # Unknown keys that look like totals may be OK if non-identifying
            # pattern; still reject nested structures.
            if is_identifying_metric_key(sk):
                violations.append(f"identifying metric key: {sk!r}")
        if isinstance(value, Mapping):
            violations.append(
                f"metric {sk!r} must not be a map (no per-client nesting)"
            )
        elif isinstance(value, (list, tuple, set)):
            violations.append(
                f"metric {sk!r} must not be a list (no session/client lists)"
            )
    return violations


def sanitize_aggregate_snapshot(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only allowed aggregate scalar counters; drop everything else."""
    out: dict[str, Any] = {}
    for key, value in raw.items():
        sk = str(key).lower()
        if sk not in ALLOWED_AGGREGATE_INTERNAL_KEYS:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if value < 0:
            continue
        out[sk] = int(value) if isinstance(value, float) and value == int(value) else value
    return out


class AggregateCounters:
    """Process-wide byte/datagram totals — never keyed by client or session."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bytes_in = 0
        self._bytes_out = 0
        self._datagrams_in = 0
        self._datagrams_out = 0
        self._started = time.time()

    def record_inbound(self, nbytes: int) -> None:
        n = int(nbytes)
        if n <= 0:
            return
        with self._lock:
            self._bytes_in += n
            self._datagrams_in += 1

    def record_outbound(self, nbytes: int) -> None:
        n = int(nbytes)
        if n <= 0:
            return
        with self._lock:
            self._bytes_out += n
            self._datagrams_out += 1

    def snapshot(self) -> dict[str, int]:
        """Internal aggregate snapshot (not for public status page)."""
        with self._lock:
            bi, bo = self._bytes_in, self._bytes_out
            di, do = self._datagrams_in, self._datagrams_out
            up = int(max(0.0, time.time() - self._started))
        snap = {
            "total_bytes_in": bi,
            "total_bytes_out": bo,
            "total_bytes_relayed": bi + bo,
            "total_datagrams_in": di,
            "total_datagrams_out": do,
            "process_uptime_sec": up,
        }
        # Self-check: never identifying
        bad = assert_metrics_non_identifying(snap)
        if bad:
            raise RuntimeError(f"aggregate snapshot violated policy: {bad}")
        return snap

    def public_status_fragment(self) -> dict[str, Any]:
        """Empty for public merge — aggregates stay off the public surface."""
        return {}


# Module-level process counters (node server may use)
_PROCESS_COUNTERS = AggregateCounters()


def process_counters() -> AggregateCounters:
    return _PROCESS_COUNTERS


def reset_process_counters_for_tests() -> AggregateCounters:
    """Replace process counters (tests only)."""
    global _PROCESS_COUNTERS
    _PROCESS_COUNTERS = AggregateCounters()
    return _PROCESS_COUNTERS
