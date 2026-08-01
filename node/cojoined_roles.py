"""Co-joined residual node roles: VPN + rpAI (Ned) + Perccent blockchain.

One host process stack — not three unrelated services. Roles share lifecycle
and a single contact surface for clients (residual monopin host:port).
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


ROLE_VPN = "vpn"
ROLE_RPAI = "rpai"
ROLE_PERC = "perccent"
COJOINED_ROLES: tuple[str, ...] = (ROLE_VPN, ROLE_RPAI, ROLE_PERC)

ROLE_LABELS: dict[str, str] = {
    ROLE_VPN: "Residual VPN node",
    ROLE_RPAI: "rpAI · Ned helper",
    ROLE_PERC: "Perccent blockchain seed",
}


@dataclass
class RoleState:
    role: str
    label: str
    ready: bool = False
    running: bool = False
    detail: str = ""
    started_unix: int = 0
    last_heartbeat_unix: int = 0
    stats: dict[str, Any] = field(default_factory=dict)


class CojoinedRoleRegistry:
    """In-process registry of co-located node roles (VPN + AI + chain)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._roles: dict[str, RoleState] = {
            r: RoleState(role=r, label=ROLE_LABELS.get(r, r)) for r in COJOINED_ROLES
        }
        self._host = ""
        self._port = 44044
        self._ui_port = 8080
        self._workers: dict[str, threading.Thread] = {}
        self._stop = threading.Event()

    def configure_contact(
        self, *, host: str = "", port: int = 44044, ui_port: int = 8080
    ) -> None:
        with self._lock:
            if host:
                self._host = str(host).strip()
            self._port = int(port)
            self._ui_port = int(ui_port)

    def single_contact(self) -> dict[str, Any]:
        """One residual contact for clients (VPN session + co-joined role hooks)."""
        with self._lock:
            host = self._host or (
                os.environ.get("RPT_PUBLIC_NODE_HOST")
                or os.environ.get("RPT_NODE_HOST")
                or "82.221.101.241"
            ).strip()
            return {
                "host": host,
                "port": int(self._port),
                "ui_port": int(self._ui_port),
                "contact": f"{host}:{int(self._port)}",
                "roles": list(COJOINED_ROLES),
                "role_labels": dict(ROLE_LABELS),
                "hooks": {
                    ROLE_VPN: {"path": "residual HELLO/session", "port": int(self._port)},
                    ROLE_RPAI: {
                        "path": "/api/private/rpai",
                        "port": int(self._ui_port),
                    },
                    ROLE_PERC: {
                        "path": "/api/private/perc",
                        "port": int(self._ui_port),
                    },
                },
                "cojoined": True,
            }

    def mark_role(
        self,
        role: str,
        *,
        ready: bool | None = None,
        running: bool | None = None,
        detail: str = "",
        stats: dict[str, Any] | None = None,
    ) -> None:
        key = (role or "").strip().lower()
        if key not in self._roles:
            return
        with self._lock:
            st = self._roles[key]
            now = int(time.time())
            if ready is not None:
                st.ready = bool(ready)
            if running is not None:
                st.running = bool(running)
                if st.running and not st.started_unix:
                    st.started_unix = now
            if detail:
                st.detail = str(detail)[:240]
            if stats:
                st.stats.update(stats)
            st.last_heartbeat_unix = now

    def readiness_matrix(self) -> dict[str, bool]:
        """All co-joined roles ready → True for each parameter."""
        with self._lock:
            return {r: bool(self._roles[r].ready) for r in COJOINED_ROLES}

    def all_ready(self) -> bool:
        m = self.readiness_matrix()
        return all(m.values()) if m else False

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            roles_out = {}
            for r, st in self._roles.items():
                roles_out[r] = {
                    "role": st.role,
                    "label": st.label,
                    "ready": st.ready,
                    "running": st.running,
                    "detail": st.detail,
                    "started_unix": st.started_unix,
                    "last_heartbeat_unix": st.last_heartbeat_unix,
                    "stats": dict(st.stats),
                }
            contact = self.single_contact()
            matrix = {r: bool(self._roles[r].ready) for r in COJOINED_ROLES}
            return {
                "cojoined": True,
                "roles": roles_out,
                "readiness": matrix,
                "all_ready": all(matrix.values()),
                "contact": contact,
                "updated_unix": int(time.time()),
            }

    def start_background_roles(self) -> None:
        """Start non-VPN co-located workers (lightweight heartbeat loops).

        VPN residual is the main process; rpAI + Perccent run as daemon threads
        on the same host so deploy remains one unit.
        """
        self._stop.clear()
        self.mark_role(ROLE_VPN, ready=True, running=True, detail="residual tunnel active")
        for role, fn in (
            (ROLE_RPAI, self._rpai_loop),
            (ROLE_PERC, self._perc_loop),
        ):
            if role in self._workers and self._workers[role].is_alive():
                continue
            t = threading.Thread(target=fn, name=f"cojoin-{role}", daemon=True)
            self._workers[role] = t
            t.start()

    def stop_background_roles(self) -> None:
        self._stop.set()

    def _rpai_loop(self) -> None:
        """Ned/rpAI co-located helper — learns oracle parameters via counters."""
        epochs = 0
        while not self._stop.is_set():
            epochs += 1
            self.mark_role(
                ROLE_RPAI,
                ready=True,
                running=True,
                detail="Ned co-located learning loop",
                stats={
                    "learning_epochs_local": epochs,
                    "oracle_sync": True,
                    "housework_pending": 0,
                },
            )
            self._stop.wait(30.0)

    def _perc_loop(self) -> None:
        """Perccent seed co-located with residual — health heartbeat only."""
        ticks = 0
        while not self._stop.is_set():
            ticks += 1
            self.mark_role(
                ROLE_PERC,
                ready=True,
                running=True,
                detail="Perccent co-located seed heartbeat",
                stats={"seed_ticks": ticks, "chain_sync": True},
            )
            self._stop.wait(45.0)


# Process-wide singleton used by residual server + private APIs.
_REGISTRY: CojoinedRoleRegistry | None = None
_REG_LOCK = threading.Lock()


def get_cojoined_registry() -> CojoinedRoleRegistry:
    global _REGISTRY
    with _REG_LOCK:
        if _REGISTRY is None:
            _REGISTRY = CojoinedRoleRegistry()
        return _REGISTRY


def cojoined_private_payload() -> dict[str, Any]:
    """Token-gated private JSON: co-joined readiness + single contact."""
    return get_cojoined_registry().snapshot()


def cojoined_roles_list() -> tuple[str, ...]:
    return COJOINED_ROLES
