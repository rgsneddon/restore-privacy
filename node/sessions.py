"""In-memory live sessions only — count is current connections, not lifetime total."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# UDP has no TCP FIN: drop sessions idle longer than this (DATA/KEEPALIVE refresh last_seen).
# Keep short so "Currently connected" tracks live users, not a sticky total.
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
    """Live session store. ``clients_connected`` == number of non-expired sessions."""

    def __init__(self, idle_sec: float = DEFAULT_SESSION_IDLE_SEC) -> None:
        self._by_id: Dict[bytes, Session] = {}
        self._by_ip: Dict[str, Session] = {}
        self._lock = threading.Lock()
        self.idle_sec = float(idle_sec)

    def count(self) -> int:
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

        This is how ``clients_connected`` decreases when clients disconnect or go
        silent (UDP has no explicit disconnect).
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
        """Only title + **current** live count — never lifetime totals or identities.

        Always prunes stale sessions first so the public number cannot stick at a
        cumulative high-water mark of past connects.
        """
        self.expire_stale()
        return {"title": "RESTORE PRIVACY", "clients_connected": self.count()}
