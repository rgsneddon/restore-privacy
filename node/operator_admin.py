"""Local operator admin surface for a residual node host (Mac GUI / API).

Session lists and priority/update controls are **admin-only**. Public node
``/status`` remains title-only via :mod:`node.sessions` / :mod:`node.ui`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from node.client_priority import (
    ClientPriorityStore,
    apply_priorities,
    global_priority_store,
    honour_priority_order,
    prefer_client,
)
from node.update_push import (
    UpdatePushQueue,
    client_receive_update_directives,
    global_update_queue,
    operator_push_update,
)


@dataclass
class NodeProcessState:
    """Running-state snapshot for the operator GUI."""

    state: str  # stopped | starting | running | error | lab
    mode: str  # full | lab
    listen_host: str = "0.0.0.0"
    listen_port: int = 44044
    ui_port: int = 8080
    pid: int | None = None
    detail: str = ""
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "mode": self.mode,
            "listen_host": self.listen_host,
            "listen_port": self.listen_port,
            "ui_port": self.ui_port,
            "pid": self.pid,
            "detail": self.detail,
            "updated_at": self.updated_at,
        }


class NodeOperatorController:
    """In-process controller the Mac operator app drives.

    *lab* mode runs UI + in-memory session registry without Linux TUN (honest on
    macOS). *full* mode spawns ``python -m node`` when the host supports it.
    """

    def __init__(
        self,
        *,
        priority_store: ClientPriorityStore | None = None,
        update_queue: UpdatePushQueue | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self.priority = priority_store or global_priority_store()
        self.updates = update_queue or global_update_queue()
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._lab_registry = None  # lazy SessionRegistry for lab
        self._residual_client = None  # RptClient residual HELLO (test dial)
        self._residual_peer = ""
        self._state = NodeProcessState(
            state="stopped",
            mode="lab",
            updated_at=time.time(),
            detail="Node not started",
        )

    # --- process control -------------------------------------------------

    def get_state(self) -> NodeProcessState:
        with self._lock:
            if self._proc is not None and self._proc.poll() is not None:
                code = self._proc.returncode
                self._state = NodeProcessState(
                    state="stopped",
                    mode=self._state.mode,
                    listen_host=self._state.listen_host,
                    listen_port=self._state.listen_port,
                    ui_port=self._state.ui_port,
                    pid=None,
                    detail=f"node process exited code={code}",
                    updated_at=time.time(),
                )
                self._proc = None
            return NodeProcessState(**self._state.to_dict())

    def start(
        self,
        *,
        mode: str = "lab",
        listen_host: str = "0.0.0.0",
        listen_port: int = 44044,
        ui_port: int = 8080,
    ) -> NodeProcessState:
        """Start residual node stack (lab in-process or full subprocess)."""
        mode_s = (mode or "lab").strip().lower()
        if mode_s not in ("lab", "full"):
            mode_s = "lab"
        with self._lock:
            if self._state.state == "running" and (
                (mode_s == "lab" and self._lab_registry is not None)
                or (mode_s == "full" and self._proc is not None)
            ):
                return NodeProcessState(**self._state.to_dict())

            if mode_s == "full":
                # Linux TUN path — may fail on macOS; surface honest detail
                try:
                    env = os.environ.copy()
                    env.setdefault("RPT_REQUIRE_PAYMENT_ENTITLEMENT", "0")
                    env.setdefault("RPT_REQUIRE_PFS", "0")
                    cmd = [
                        sys.executable,
                        "-m",
                        "node",
                        "--listen-host",
                        listen_host,
                        "--listen-port",
                        str(int(listen_port)),
                        "--ui-port",
                        str(int(ui_port)),
                    ]
                    self._proc = subprocess.Popen(
                        cmd,
                        cwd=str(self.repo_root),
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                    )
                    time.sleep(0.3)
                    if self._proc.poll() is not None:
                        err = b""
                        try:
                            err = self._proc.stderr.read() if self._proc.stderr else b""
                        except Exception:  # noqa: BLE001
                            err = b""
                        detail = (
                            err.decode("utf-8", errors="replace")[:240]
                            or "full node exited immediately (TUN unavailable on this host?)"
                        )
                        self._state = NodeProcessState(
                            state="error",
                            mode="full",
                            listen_host=listen_host,
                            listen_port=int(listen_port),
                            ui_port=int(ui_port),
                            pid=None,
                            detail=detail,
                            updated_at=time.time(),
                        )
                        self._proc = None
                        return NodeProcessState(**self._state.to_dict())
                    self._state = NodeProcessState(
                        state="running",
                        mode="full",
                        listen_host=listen_host,
                        listen_port=int(listen_port),
                        ui_port=int(ui_port),
                        pid=self._proc.pid,
                        detail="full node process running",
                        updated_at=time.time(),
                    )
                except Exception as exc:  # noqa: BLE001
                    self._state = NodeProcessState(
                        state="error",
                        mode="full",
                        detail=str(exc)[:240],
                        updated_at=time.time(),
                    )
                return NodeProcessState(**self._state.to_dict())

            # lab mode — SessionRegistry only (Mac-honest residual lab)
            from node.sessions import SessionRegistry

            self._lab_registry = SessionRegistry()
            self._state = NodeProcessState(
                state="running",
                mode="lab",
                listen_host=listen_host,
                listen_port=int(listen_port),
                ui_port=int(ui_port),
                pid=os.getpid(),
                detail=(
                    "lab mode: in-memory sessions + admin controls "
                    "(no Linux TUN residual on this host)"
                ),
                updated_at=time.time(),
            )
            return NodeProcessState(**self._state.to_dict())

    def stop(self) -> NodeProcessState:
        with self._lock:
            if self._proc is not None:
                try:
                    self._proc.terminate()
                    try:
                        self._proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self._proc.kill()
                except Exception:  # noqa: BLE001
                    pass
                self._proc = None
            self._lab_registry = None
            self._state = NodeProcessState(
                state="stopped",
                mode=self._state.mode,
                listen_host=self._state.listen_host,
                listen_port=self._state.listen_port,
                ui_port=self._state.ui_port,
                pid=None,
                detail="stopped",
                updated_at=time.time(),
            )
            return NodeProcessState(**self._state.to_dict())

    # --- sessions (admin) ------------------------------------------------

    def list_sessions_admin(self) -> list[dict[str, Any]]:
        """Admin session rows (never public status)."""
        with self._lock:
            reg = self._lab_registry
        if reg is None:
            return []
        rows: list[dict[str, Any]] = []
        for sid in reg.live_session_ids():
            s = reg.get(sid)
            if not s:
                continue
            cid = sid.hex()
            rows.append(
                {
                    "client_id": cid,
                    "session_id_hex": cid,
                    "vpn_ip": s.vpn_ip,
                    "client_addr": f"{s.client_addr[0]}:{s.client_addr[1]}",
                    "last_seen": float(s.last_seen),
                    "priority": self.priority.get_priority(cid),
                }
            )
        # Honour priority ordering for admin table
        order = honour_priority_order(
            [r["client_id"] for r in rows], store=self.priority
        )
        by = {r["client_id"]: r for r in rows}
        return [by[c] for c in order if c in by]

    def inject_lab_session(
        self,
        *,
        session_id: bytes | None = None,
        client_addr: tuple[str, int] | None = None,
        vpn_ip: str = "",
    ) -> dict[str, Any]:
        """Test/lab helper: add a synthetic live session."""
        import os as _os

        from node.sessions import Session

        with self._lock:
            if self._lab_registry is None:
                from node.sessions import SessionRegistry

                self._lab_registry = SessionRegistry()
                self._state = NodeProcessState(
                    state="running",
                    mode="lab",
                    pid=_os.getpid(),
                    detail="lab mode (auto-started for inject)",
                    updated_at=time.time(),
                )
            reg = self._lab_registry
            n = reg.count()
        sid = session_id if session_id is not None else _os.urandom(8)
        # Unique UDP endpoint per lab session (registry collapses same client_addr)
        addr = client_addr if client_addr is not None else ("127.0.0.1", 50000 + int(n))
        ip = (vpn_ip or "").strip() or f"10.88.0.{2 + int(n)}"
        sess = Session(
            session_id=sid,
            crypto=object(),
            client_addr=addr,
            vpn_ip=ip,
        )
        reg.add(sess)
        return {
            "client_id": sid.hex(),
            "session_id_hex": sid.hex(),
            "vpn_ip": ip,
        }

    def public_status_title_only(self) -> dict[str, Any]:
        """Public status must stay title-only even when sessions exist."""
        with self._lock:
            reg = self._lab_registry
        if reg is None:
            from node.aggregate_metrics import filter_public_status

            return filter_public_status({"title": "RESTORE PRIVACY"})
        return reg.status_payload()

    # --- priority --------------------------------------------------------

    def set_client_priority(self, client_id: str, priority: int) -> dict[str, Any]:
        p = self.priority.set_priority(client_id, priority)
        return {"ok": True, "client_id": client_id, "priority": p}

    def set_priorities(self, mapping: dict[str, int]) -> dict[str, Any]:
        applied = apply_priorities(mapping, store=self.priority)
        return {"ok": True, "applied": applied}

    def service_order(self, client_ids: Sequence[str] | None = None) -> list[str]:
        if client_ids is None:
            client_ids = [r["client_id"] for r in self.list_sessions_admin()]
        return honour_priority_order(client_ids, store=self.priority)

    def preferred_client(self, client_ids: Sequence[str] | None = None) -> str | None:
        if client_ids is None:
            client_ids = [r["client_id"] for r in self.list_sessions_admin()]
        return prefer_client(client_ids, store=self.priority)

    # --- update push -----------------------------------------------------

    def push_update(
        self,
        *,
        version: str,
        url: str = "",
        message: str = "",
        target_client_id: str = "",
    ) -> dict[str, Any]:
        connected = [r["client_id"] for r in self.list_sessions_admin()]
        return operator_push_update(
            version=version,
            url=url,
            message=message,
            target_client_id=target_client_id,
            connected_client_ids=connected,
            queue=self.updates,
        )

    def client_pull_updates(self, client_id: str) -> list[dict[str, Any]]:
        return client_receive_update_directives(client_id, queue=self.updates)

    # --- residual HELLO to catalog peers (test path) ---------------------

    def connect_residual_peer(
        self,
        *,
        peer: str = "IS",
        timeout: float = 12.0,
        secrets_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Run shipped residual CLIENT_HELLO to a catalog peer (default Iceland).

        This is the **client residual** path for testing from the operator Mac —
        not Linux TUN host mode. Uses product ElGamal pins + device/admission keys.
        """
        code = (peer or "IS").strip().upper()
        try:
            from client.connect import RptClient
            from client.endpoint import Endpoint
            from client.multihop import Hop, MultiHopConfig, product_country_catalog
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": f"client stack unavailable: {exc}"[:200],
                "peer": code,
            }

        host = ""
        port = 44044
        for n in product_country_catalog():
            if str(getattr(n, "code", "")).upper() == code:
                host = str(n.host)
                port = int(n.port or 44044)
                break
        if not host and code == "IS":
            host, port = "82.221.101.241", 44044
        if not host and code == "DE":
            host, port = "178.105.187.178", 44044
        if not host:
            return {"ok": False, "error": f"unknown peer {code}", "peer": code}

        sdir = Path(secrets_dir) if secrets_dir else (self.repo_root / "secrets")
        # Single-hop residual to requested peer (Iceland by default for Mac test)
        mh = MultiHopConfig(
            enabled=False,
            hops=[Hop(host=host, port=port, role="entry")],
        )
        notes: list[str] = []

        def _cb(msg: str) -> None:
            notes.append(str(msg))

        try:
            client = RptClient(
                endpoint=Endpoint(host=host, port=port),
                secrets_dir=sdir,
                status_cb=_cb,
                multihop=mh,
                probe_capacity=False,
            )
            # Pin endpoint — do not re-select away from requested peer
            client._endpoint_pinned = True  # noqa: SLF001 — test dial pin
            result = client.connect(timeout=float(timeout), force_reconnect=True)
            out: dict[str, Any] = {
                "ok": bool(result.ok),
                "peer": code,
                "host": host,
                "port": port,
                "message": str(result.message or ""),
                "state": str(getattr(result.state, "value", result.state) or ""),
                "vpn_ip": getattr(result.session, "vpn_ip", None) if result.session else None,
                "notes": notes[-8:],
            }
            if not result.ok:
                out["error"] = str(result.message or "connect failed")
            # Keep UDP session open on controller for follow-up tests
            with self._lock:
                self._residual_client = client
                self._residual_peer = code
            return out
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": str(exc)[:240],
                "peer": code,
                "host": host,
                "port": port,
                "notes": notes[-8:],
            }

    def residual_connect_status(self) -> dict[str, Any]:
        with self._lock:
            client = getattr(self, "_residual_client", None)
            peer = getattr(self, "_residual_peer", "") or ""
        if client is None:
            return {"connected": False, "peer": peer or None, "vpn_ip": None, "state": "idle"}
        sess = getattr(client, "session", None)
        state = getattr(client, "state", None)
        return {
            "connected": bool(sess is not None and str(getattr(state, "value", state)) == "connected"),
            "peer": peer or None,
            "vpn_ip": getattr(sess, "vpn_ip", None) if sess else None,
            "state": str(getattr(state, "value", state) or "unknown"),
            "host": getattr(getattr(client, "endpoint", None), "host", None),
        }

    def disconnect_residual(self) -> dict[str, Any]:
        with self._lock:
            client = getattr(self, "_residual_client", None)
            self._residual_client = None
            self._residual_peer = ""
        if client is not None:
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True, "connected": False}
