"""Operator client priority for residual node admission / relay scheduling.

Higher integer = higher priority. Public status stays title-only; this store is
admin/operator only (node operator GUI or local admin API).
"""

from __future__ import annotations

import threading
from typing import Iterable, Mapping, Sequence


DEFAULT_PRIORITY = 0
MIN_PRIORITY = -1000
MAX_PRIORITY = 1000


def clamp_priority(value: int | float | str) -> int:
    """Normalize a priority integer into the allowed range."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = DEFAULT_PRIORITY
    if n < MIN_PRIORITY:
        return MIN_PRIORITY
    if n > MAX_PRIORITY:
        return MAX_PRIORITY
    return n


class ClientPriorityStore:
    """Thread-safe map of client identity → priority (higher wins)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prio: dict[str, int] = {}

    def set_priority(self, client_id: str, priority: int) -> int:
        """Set priority for *client_id*; returns clamped priority stored."""
        cid = (client_id or "").strip()
        if not cid:
            raise ValueError("client_id required")
        p = clamp_priority(priority)
        with self._lock:
            self._prio[cid] = p
        return p

    def get_priority(self, client_id: str) -> int:
        cid = (client_id or "").strip()
        if not cid:
            return DEFAULT_PRIORITY
        with self._lock:
            return int(self._prio.get(cid, DEFAULT_PRIORITY))

    def clear(self, client_id: str | None = None) -> None:
        with self._lock:
            if client_id is None:
                self._prio.clear()
            else:
                self._prio.pop((client_id or "").strip(), None)

    def as_dict(self) -> dict[str, int]:
        with self._lock:
            return dict(self._prio)

    def order_clients(self, client_ids: Sequence[str]) -> list[str]:
        """Return *client_ids* sorted highest priority first (stable by id)."""
        ids = [str(c or "").strip() for c in client_ids if str(c or "").strip()]
        with self._lock:
            scores = {c: int(self._prio.get(c, DEFAULT_PRIORITY)) for c in ids}
        # Higher priority first; tie-break by client_id for determinism
        return sorted(ids, key=lambda c: (-scores.get(c, DEFAULT_PRIORITY), c))

    def preferred_among(self, client_ids: Sequence[str]) -> str | None:
        """Best (highest priority) client among *client_ids*, or None if empty."""
        ordered = self.order_clients(client_ids)
        return ordered[0] if ordered else None


# Process-wide store used by residual node + operator GUI (same process).
_GLOBAL_STORE: ClientPriorityStore | None = None
_GLOBAL_LOCK = threading.Lock()


def global_priority_store() -> ClientPriorityStore:
    global _GLOBAL_STORE
    with _GLOBAL_LOCK:
        if _GLOBAL_STORE is None:
            _GLOBAL_STORE = ClientPriorityStore()
        return _GLOBAL_STORE


def reset_global_priority_store_for_tests() -> ClientPriorityStore:
    """Replace the process-wide store (tests only)."""
    global _GLOBAL_STORE
    with _GLOBAL_LOCK:
        _GLOBAL_STORE = ClientPriorityStore()
        return _GLOBAL_STORE


def honour_priority_order(
    client_ids: Sequence[str],
    *,
    store: ClientPriorityStore | None = None,
) -> list[str]:
    """Shipped resolve path: order client identities for residual work."""
    st = store if store is not None else global_priority_store()
    return st.order_clients(client_ids)


def prefer_client(
    client_ids: Iterable[str],
    *,
    store: ClientPriorityStore | None = None,
) -> str | None:
    """Pick the highest-priority client id (contention path)."""
    st = store if store is not None else global_priority_store()
    return st.preferred_among(list(client_ids))


def apply_priorities(
    mapping: Mapping[str, int],
    *,
    store: ClientPriorityStore | None = None,
) -> dict[str, int]:
    """Bulk-set priorities; returns effective map applied."""
    st = store if store is not None else global_priority_store()
    out: dict[str, int] = {}
    for cid, prio in (mapping or {}).items():
        out[str(cid)] = st.set_priority(str(cid), int(prio))
    return out
