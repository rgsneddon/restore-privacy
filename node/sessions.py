"""In-memory sessions only — count exposed to UI, no user-info persistence."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass
class Session:
    session_id: bytes
    crypto: object
    client_addr: Tuple[str, int]
    vpn_ip: str
    counter_out: int = 0
    last_seen: float = field(default_factory=time.time)


class SessionRegistry:
    def __init__(self) -> None:
        self._by_id: Dict[bytes, Session] = {}
        self._by_ip: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def count(self) -> int:
        with self._lock:
            return len(self._by_id)

    def add(self, session: Session) -> None:
        with self._lock:
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

    def remove(self, session_id: bytes) -> None:
        with self._lock:
            s = self._by_id.pop(session_id, None)
            if s:
                self._by_ip.pop(s.vpn_ip, None)

    def status_payload(self) -> dict:
        """Only title + count — never client IPs or identities."""
        return {"title": "RESTORE PRIVACY", "clients_connected": self.count()}
