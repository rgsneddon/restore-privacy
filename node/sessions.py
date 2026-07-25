"""In-memory live sessions for routing — not published as a public client count."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# UDP has no TCP FIN: drop sessions idle longer than this (DATA/KEEPALIVE refresh last_seen).
DEFAULT_SESSION_IDLE_SEC = 60.0


@dataclass
class Session:
    session_id: bytes
    crypto: object
    client_addr: Tuple[str, int]
    vpn_ip: str
    counter_out: int = 0
    last_seen: float = field(default_factory=time.time)


class SessionRegistry:
    """Live session store for routing (internal size only; not a public metric)."""

    def __init__(self, idle_sec: float = DEFAULT_SESSION_IDLE_SEC) -> None:
        self._by_id: Dict[bytes, Session] = {}
        self._by_ip: Dict[str, Session] = {}
        self._lock = threading.Lock()
        self.idle_sec = float(idle_sec)

    def count(self) -> int:
        """Internal live session size for routing/tests — not exposed on public status."""
        with self._lock:
            return len(self._by_id)

    def add(self, session: Session) -> None:
        with self._lock:
            # Replacing same id is fine; do not keep orphaned IP mapping
            old = self._by_id.get(session.session_id)
            if old and old.vpn_ip != session.vpn_ip:
                self._by_ip.pop(old.vpn_ip, None)
            # If another session held this VPN IP, drop it (one tunnel IP → one live session)
            prior_ip = self._by_ip.get(session.vpn_ip)
            if prior_ip is not None and prior_ip.session_id != session.session_id:
                self._by_id.pop(prior_ip.session_id, None)
            # Same client UDP endpoint reconnecting → drop prior session (new session_id)
            # so count does not accumulate orphans from reconnect storms.
            dead_sid = [
                sid
                for sid, s in self._by_id.items()
                if s.client_addr == session.client_addr
                and sid != session.session_id
            ]
            for sid in dead_sid:
                s = self._by_id.pop(sid, None)
                if s:
                    self._by_ip.pop(s.vpn_ip, None)
            self._by_id[session.session_id] = session
            self._by_ip[session.vpn_ip] = session

    def get(self, session_id: bytes) -> Optional[Session]:
        with self._lock:
            return self._by_id.get(session_id)

    def get_by_ip(self, vpn_ip: str) -> Optional[Session]:
        with self._lock:
            return self._by_ip.get(vpn_ip)

    def touch(self, session_id: bytes, addr: Tuple[str, int]) -> None:
        with self._lock:
            s = self._by_id.get(session_id)
            if s:
                s.client_addr = addr
                s.last_seen = time.time()

    def remove(self, session_id: bytes) -> bool:
        """Remove one session. Returns True if it was present."""
        with self._lock:
            s = self._by_id.pop(session_id, None)
            if s:
                self._by_ip.pop(s.vpn_ip, None)
                return True
            return False

    def expire_stale(
        self,
        now: Optional[float] = None,
        idle_sec: Optional[float] = None,
    ) -> int:
        """Remove sessions idle longer than idle_sec. Returns how many were dropped.

        UDP has no explicit disconnect — idle prune frees tunnel IPs for routing.
        """
        now_t = time.time() if now is None else float(now)
        limit = self.idle_sec if idle_sec is None else float(idle_sec)
        removed = 0
        with self._lock:
            dead: List[bytes] = [
                sid
                for sid, s in self._by_id.items()
                if (now_t - float(s.last_seen)) > limit
            ]
            for sid in dead:
                s = self._by_id.pop(sid, None)
                if s:
                    self._by_ip.pop(s.vpn_ip, None)
                    removed += 1
        return removed

    def live_session_ids(self) -> list[bytes]:
        with self._lock:
            return list(self._by_id.keys())

    def status_payload(self) -> dict:
        """Public status: product title only — no live client count field.

        Session registry still prunes idle sessions for routing; count and any
        aggregate bandwidth counters are never published on the public UI/API.
        """
        self.expire_stale()
        from node.aggregate_metrics import filter_public_status

        return filter_public_status({"title": "RESTORE PRIVACY"})

    def private_capacity_payload(self, *, host: str = "") -> dict:
        """Token-gated capacity snapshot for residual load hints (not public).

        Uses in-memory live session count vs soft max sessions, plus process-wide
        byte counters for operator admin bandwidth used-vs-capability. Never used
        by public HTML/JSON status paths.
        """
        self.expire_stale()
        from node.aggregate_metrics import process_counters
        from node.private_capacity import build_private_capacity_payload

        snap = process_counters().snapshot()
        return build_private_capacity_payload(
            live=self.count(),
            host=host,
            total_bytes_in=int(snap.get("total_bytes_in") or 0),
            total_bytes_out=int(snap.get("total_bytes_out") or 0),
            total_bytes_relayed=int(snap.get("total_bytes_relayed") or 0),
            process_uptime_sec=int(snap.get("process_uptime_sec") or 0),
        )
