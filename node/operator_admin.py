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
from typing import Any, Callable, Mapping, Optional, Sequence

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
                    # Honest empty when session never reported a product monopin.
                    "product_version": (getattr(s, "product_version", None) or "").strip(),
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
        product_version: str = "",
    ) -> dict[str, Any]:
        """Test/lab helper: add a synthetic live session.

        *product_version* is optional; omit or empty for honest unknown (do not
        invent a monopin for lab sessions that never reported one).
        """
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
        ver = (product_version or "").strip()
        sess = Session(
            session_id=sid,
            crypto=object(),
            client_addr=addr,
            vpn_ip=ip,
            product_version=ver,
        )
        reg.add(sess)
        return {
            "client_id": sid.hex(),
            "session_id_hex": sid.hex(),
            "vpn_ip": ip,
            "product_version": ver,
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

    def suite_host_inventory(self, *, version: str | None = None) -> dict[str, Any]:
        """Build-host Suite monopin inventory (for client-push prefill + match)."""
        try:
            from suite_client_push import summarize_local_suite_inventory
        except ImportError:  # pragma: no cover
            from status_page.suite_client_push import (  # type: ignore
                summarize_local_suite_inventory,
            )
        ver = (version or "").strip() or self.catalog_version_default()
        inv = self.list_local_packages(version=ver, brand_wide=False)
        # Enrich sizes/paths already present; linux label for Arch coverage
        pkgs = list(inv.get("packages") or [])
        for p in pkgs:
            if str(p.get("platform") or "").lower() == "linux":
                p["platform_label"] = "Linux / Arch Linux (x86_64)"
                p["covers_archlinux"] = True
            path = str(p.get("path") or "")
            if p.get("present") and path:
                try:
                    p["size"] = int(Path(path).stat().st_size)
                except OSError:
                    pass
        return summarize_local_suite_inventory(pkgs, version=ver)

    def suite_helsinki_inventory(
        self,
        *,
        version: str | None = None,
        filenames: list[str] | None = None,
        probe_one: Any | None = None,
        remote_rows: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Helsinki paid_assets Suite inventory (injectable for tests)."""
        try:
            from suite_client_push import (
                probe_helsinki_suite_packages,
                summarize_helsinki_suite_inventory,
            )
        except ImportError:  # pragma: no cover
            from status_page.suite_client_push import (  # type: ignore
                probe_helsinki_suite_packages,
                summarize_helsinki_suite_inventory,
            )
        ver = (version or "").strip() or self.catalog_version_default()
        if remote_rows is not None:
            return summarize_helsinki_suite_inventory(
                ver, remote_rows, expected_filenames=filenames
            )
        names = filenames
        if not names:
            host = self.suite_host_inventory(version=ver)
            names = [
                str(p.get("filename") or "")
                for p in (host.get("packages") or [])
                if p.get("filename")
            ]
        return probe_helsinki_suite_packages(
            ver, names or [], probe_one=probe_one
        )

    def suite_client_push_match_gate(
        self,
        *,
        version: str | None = None,
        only_filenames: list[str] | set[str] | tuple[str, ...] | None = None,
        helsinki: Mapping[str, Any] | None = None,
        host: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Gate: host and Helsinki Suite package sets must match to push clients."""
        try:
            from suite_client_push import match_host_helsinki_suite
        except ImportError:  # pragma: no cover
            from status_page.suite_client_push import (  # type: ignore
                match_host_helsinki_suite,
            )
        ver = (version or "").strip() or self.catalog_version_default()
        host_inv = host if host is not None else self.suite_host_inventory(version=ver)
        hel_inv = (
            helsinki
            if helsinki is not None
            else self.suite_helsinki_inventory(version=ver)
        )
        sel = None
        if only_filenames is not None:
            sel = [str(x).strip() for x in only_filenames if str(x).strip()]
        gate = match_host_helsinki_suite(host_inv, hel_inv, only_filenames=sel)
        gate["host"] = host_inv
        gate["helsinki"] = hel_inv
        gate["suite"] = self.suite_product_label(ver)
        return gate

    def push_selected_suite_updates_to_clients(
        self,
        *,
        version: str | None = None,
        only_filenames: list[str] | set[str] | tuple[str, ...] | None = None,
        url: str = "",
        message: str = "",
        target_client_id: str = "",
        require_host_helsinki_match: bool = True,
        helsinki: Mapping[str, Any] | None = None,
        host: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """UPLOADS path: push Suite monopin update directive to residual clients.

        Enqueues via :meth:`push_update` (UPDATE_PUSH queue). Clients apply only
        when Settings **CHECK BREADCRUMBS** (push-update) is enabled — this never
        claims force-install for opt-out clients.

        When *require_host_helsinki_match* is True (default), build-host and
        Helsinki Suite package sizes for the selected basenames must match or
        the push is rejected with a clear cannot-complete reason.

        *only_filenames*: selected Suite catalog basenames (required when gate
        is on — empty selection blocks push).
        """
        ver = (version or "").strip() or self.catalog_version_default()
        inv = self.list_local_packages(version=ver, brand_wide=False)
        known = {
            str(p.get("filename") or ""): p
            for p in (inv.get("packages") or [])
            if p.get("filename")
        }
        sel = [
            str(x).strip()
            for x in (only_filenames or [])
            if str(x).strip()
        ]
        gate: dict[str, Any] | None = None
        if require_host_helsinki_match:
            gate = self.suite_client_push_match_gate(
                version=ver,
                only_filenames=sel if sel else [],
                helsinki=helsinki,
                host=host,
            )
            if not gate.get("can_push"):
                return {
                    "ok": False,
                    "error": str(
                        gate.get("reason")
                        or "Host and Helsinki Suite packages do not match — "
                        "push cannot be completed."
                    ),
                    "delivered_to": [],
                    "suite": self.suite_product_label(ver),
                    "version": ver,
                    "only_filenames": list(sel),
                    "platforms": [],
                    "unknown_filenames": [f for f in sel if f not in known],
                    "opt_in_only": True,
                    "client_gate": "CHECK BREADCRUMBS",
                    "force_install": False,
                    "can_push": False,
                    "match": False,
                    "match_gate": gate,
                }
        unknown = [f for f in sel if f not in known]
        platforms = [
            str(known[f].get("platform") or "")
            for f in sel
            if f in known
        ]
        platforms = [p for p in platforms if p]
        # Expand linux → Linux / Arch Linux in message
        plat_labels: list[str] = []
        try:
            from suite_client_push import suite_platform_display_label
        except ImportError:  # pragma: no cover
            from status_page.suite_client_push import (  # type: ignore
                suite_platform_display_label,
            )
        for p in platforms:
            lab = suite_platform_display_label(p)
            if lab not in plat_labels:
                plat_labels.append(lab)
        try:
            from suite_client_push import default_client_update_url
        except ImportError:  # pragma: no cover
            from status_page.suite_client_push import (  # type: ignore
                default_client_update_url,
            )
        u = (url or "").strip() or default_client_update_url(ver)
        if not message.strip():
            plat_s = ", ".join(plat_labels) if plat_labels else "all Suite platforms"
            msg = (
                f"Restore Privacy Suite v{ver} update available ({plat_s}). "
                "Clients apply only when CHECK BREADCRUMBS is enabled."
            )
        else:
            msg = message.strip()
        r = self.push_update(
            version=ver,
            url=u,
            message=msg,
            target_client_id=(target_client_id or "").strip(),
        )
        return {
            **r,
            "suite": self.suite_product_label(ver),
            "version": ver,
            "only_filenames": list(sel),
            "platforms": platforms,
            "platform_labels": plat_labels,
            "unknown_filenames": unknown,
            "opt_in_only": True,
            "client_gate": "CHECK BREADCRUMBS",
            "force_install": False,
            "url": u,
            "message": msg,
            "can_push": True,
            "match": True if gate is None else bool(gate.get("match")),
            "match_gate": gate,
        }

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

    # --- catalog package stage + Helsinki upload (manual GUI) ------------

    def _load_host_paid_assets(self):
        """Import shipped ``scripts/host_paid_assets_vps`` helpers."""
        import importlib.util

        path = self.repo_root / "scripts" / "host_paid_assets_vps.py"
        if not path.is_file():
            raise FileNotFoundError(f"missing {path}")
        spec = importlib.util.spec_from_file_location("host_paid_assets_vps", path)
        if spec is None or spec.loader is None:
            raise ImportError("cannot load host_paid_assets_vps")
        mod = importlib.util.module_from_spec(spec)
        # Ensure status_page is importable (script expects it on path)
        sp = str(self.repo_root / "status_page")
        if sp not in sys.path:
            sys.path.insert(0, sp)
        if str(self.repo_root) not in sys.path:
            sys.path.insert(0, str(self.repo_root))
        spec.loader.exec_module(mod)
        return mod

    def ssh_upload_access_preflight(
        self,
        *,
        upload: bool = True,
        env: dict[str, str] | None = None,
        home: Path | None = None,
    ) -> dict[str, Any]:
        """Check host SSH access keys before package upload (no network).

        Delegates to shipped ``host_paid_assets_vps.ssh_upload_preflight``. When
        keys are missing and *upload* is True, returns ``redirect`` to the public
        app-testers URL so the admin browser can be forced there.
        """
        try:
            mod = self._load_host_paid_assets()
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "missing_ssh_keys": True,
                "redirect": "https://restoreprivacy.online/app-testers",
                "error": f"host script unavailable: {exc}"[:240],
                "key_path": "",
            }
        preflight = getattr(mod, "ssh_upload_preflight", None)
        if not callable(preflight):
            return {
                "ok": False,
                "missing_ssh_keys": True,
                "redirect": "https://restoreprivacy.online/app-testers",
                "error": "ssh_upload_preflight helper missing",
                "key_path": "",
            }
        return dict(
            preflight(upload=bool(upload), env=env, home=home)  # type: ignore[misc]
        )

    def catalog_version_default(self) -> str:
        """Current shipped catalog monopin (downloads.RELEASE_VERSION)."""
        try:
            sys.path.insert(0, str(self.repo_root / "status_page"))
            from downloads import RELEASE_VERSION

            return str(RELEASE_VERSION).strip() or "1.0.0"
        except Exception:  # noqa: BLE001
            ver = (self.repo_root / "client" / "VERSION").read_text(encoding="utf-8")
            return ver.strip() or "1.0.0"

    def suite_product_label(self, version: str | None = None) -> str:
        """Human suite label for admin flash / UI (e.g. Restore Privacy Suite v1.0.0)."""
        ver = (version or "").strip() or self.catalog_version_default()
        try:
            sys.path.insert(0, str(self.repo_root / "status_page"))
            from downloads import SUITE_PRODUCT_TITLE

            title = str(SUITE_PRODUCT_TITLE).strip() or "Restore Privacy Suite"
        except Exception:  # noqa: BLE001
            title = "Restore Privacy Suite"
        return f"{title} v{ver}"

    def push_suite_packages(
        self,
        *,
        version: str | None = None,
        stage: bool = True,
        upload: bool = True,
        dry_run: bool = False,
        force: bool = True,
        allow_missing: bool = False,
        install_serve: bool = False,
        progress_cb: Any | None = None,
        brand_wide: bool = True,
        only_filenames: list[str] | set[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Admin primary path: stage + upload brand installers to Helsinki.

        Default *brand_wide* includes Suite clients, rpOS, Pens/Tables/Slides,
        browser/Rx, node-installer, and node-operator packages.

        *only_filenames*: admin-selected basenames only (cross-OS packages not
        selected never fail the job). Defaults: *force* True; *allow_missing*
        False for selected rows.
        """
        ver = (version or "").strip() or self.catalog_version_default()
        inv = self.list_local_packages(version=ver, brand_wide=bool(brand_wide))
        deploy = self.upload_catalog_packages(
            version=ver,
            stage=bool(stage),
            upload=bool(upload),
            dry_run=bool(dry_run),
            force=bool(force),
            allow_missing=bool(allow_missing),
            install_serve=bool(install_serve),
            progress_cb=progress_cb,
            brand_wide=bool(brand_wide),
            only_filenames=only_filenames,
        )
        sel = deploy.get("only_filenames") or []
        return {
            "ok": bool(deploy.get("ok")),
            "suite": self.suite_product_label(ver),
            "version": ver,
            "stage": bool(stage),
            "upload": bool(upload),
            "dry_run": bool(dry_run),
            "force": bool(force),
            "allow_missing": bool(allow_missing),
            "install_serve": bool(install_serve),
            "brand_wide": bool(brand_wide),
            "only_filenames": list(sel) if sel else [],
            "inventory": inv,
            "inventory_after": deploy.get("inventory_after") or {},
            "staged": deploy.get("staged") or [],
            "upload_code": deploy.get("upload_code"),
            "error": deploy.get("error") or "",
            "present_count": int(inv.get("present_count") or 0),
            "total": int(inv.get("total") or 0),
            "packages": inv.get("packages") or [],
            "kinds": inv.get("kinds") or [],
            "missing_ssh_keys": bool(deploy.get("missing_ssh_keys")),
            "redirect": str(deploy.get("redirect") or ""),
            "ssh_key_path": str(deploy.get("ssh_key_path") or ""),
        }

    def list_local_packages(
        self, *, version: str | None = None, brand_wide: bool = True
    ) -> dict[str, Any]:
        """Inventory packages under releases/ and status_page/assets/.

        When *brand_wide* is True (default for admin push), includes full brand
        set (Suite + rpOS + Pens/Tables/Slides + extras).
        """
        ver = (version or "").strip() or self.catalog_version_default()
        if brand_wide:
            try:
                scripts = str(self.repo_root / "scripts")
                if scripts not in sys.path:
                    sys.path.insert(0, scripts)
                from brand_package_inventory import inventory_with_presence

                inv = inventory_with_presence(
                    suite_version=ver, repo_root=self.repo_root
                )
                inv["version"] = ver
                return inv
            except Exception as exc:  # noqa: BLE001
                return {
                    "ok": False,
                    "error": str(exc)[:240],
                    "version": ver,
                    "packages": [],
                    "present_count": 0,
                    "staged_count": 0,
                    "total": 0,
                    "kinds": [],
                }
        try:
            mod = self._load_host_paid_assets()
            pkgs = mod.list_packages(ver)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": str(exc)[:240],
                "version": ver,
                "packages": [],
            }
        rows: list[dict[str, Any]] = []
        for p in pkgs:
            fname = p["filename"]
            found = None
            size = 0
            for cand in mod._candidate_sources(ver, fname):  # noqa: SLF001
                if cand.is_file() and cand.stat().st_size > 0:
                    found = cand
                    size = int(cand.stat().st_size)
                    break
            staged = self.repo_root / "status_page" / "assets" / ver / fname
            plat = str(p.get("platform") or "")
            plat_label = plat
            covers_arch = False
            if plat.lower() == "linux":
                plat_label = "Linux / Arch Linux (x86_64)"
                covers_arch = True
            rows.append(
                {
                    "kind": "suite_client",
                    "product": "Restore Privacy Suite",
                    "platform": plat,
                    "platform_label": plat_label,
                    "covers_archlinux": covers_arch,
                    "filename": fname,
                    "present": found is not None,
                    "path": str(found) if found else "",
                    "size": size,
                    "staged": staged.is_file() and staged.stat().st_size > 0,
                    "staged_path": str(staged),
                    "status": "pending",
                    "progress": 0,
                }
            )
        return {
            "ok": True,
            "version": ver,
            "packages": rows,
            "present_count": sum(1 for r in rows if r["present"]),
            "staged_count": sum(1 for r in rows if r["staged"]),
            "total": len(rows),
            "kinds": ["suite_client"],
        }

    def upload_catalog_packages(
        self,
        *,
        version: str | None = None,
        stage: bool = True,
        upload: bool = True,
        dry_run: bool = False,
        force: bool = True,
        allow_missing: bool = False,
        install_serve: bool = False,
        progress_cb: Any | None = None,
        brand_wide: bool = True,
        only_filenames: list[str] | set[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Manual deploy: stage local packages and/or upload to Helsinki.

        When *brand_wide* is True, stages/uploads the brand inventory
        (Suite + rpOS + Pens/Tables/Slides + extras), optionally limited by
        *only_filenames* (admin package checkboxes).

        Defaults: *force* re-uploads selected packages (no skip-if-present);
        *allow_missing* is off so **selected** incomplete files fail closed.
        """
        ver = (version or "").strip() or self.catalog_version_default()
        sel_list: list[str] | None = None
        if only_filenames is not None:
            sel_list = [str(x).strip() for x in only_filenames if str(x).strip()]
        out: dict[str, Any] = {
            "ok": False,
            "version": ver,
            "stage": bool(stage),
            "upload": bool(upload),
            "dry_run": bool(dry_run),
            "force": bool(force),
            "allow_missing": bool(allow_missing),
            "install_serve": bool(install_serve),
            "brand_wide": bool(brand_wide),
            "only_filenames": list(sel_list) if sel_list is not None else [],
            "staged": [],
            "upload_code": None,
            "error": "",
            "inventory": {},
        }
        try:
            mod = self._load_host_paid_assets()
        except Exception as exc:  # noqa: BLE001
            out["error"] = f"host script unavailable: {exc}"[:240]
            return out

        inv_before = self.list_local_packages(version=ver, brand_wide=bool(brand_wide))
        out["inventory"] = inv_before

        if not stage and not upload:
            out["ok"] = True
            out["error"] = "nothing to do (stage and upload both off)"
            return out

        # Real SSH upload (not dry-run) requires host access keys.
        if upload and not dry_run:
            pre = self.ssh_upload_access_preflight(upload=True)
            if not pre.get("ok"):
                out["error"] = str(pre.get("error") or "SSH access keys missing")
                out["missing_ssh_keys"] = True
                out["redirect"] = str(pre.get("redirect") or "")
                return out
            out["missing_ssh_keys"] = False
            out["ssh_key_path"] = str(pre.get("key_path") or "")

        # Progress UI: report one file at a time. When both stage and upload run,
        # only the upload phase drives progress_cb so rows do not flash
        # done-then-reupload or get auto-skipped at finish while still pending.
        stage_cb = progress_cb if (progress_cb and stage and not upload) else None
        upload_cb = progress_cb if (progress_cb and upload) else None

        # Selective filenames always use brand stage/upload (supports only_filenames
        # + progress_cb). Suite-only inventory still passes Suite basenames only.
        use_selective = sel_list is not None
        use_brand_path = bool(brand_wide) or use_selective

        if stage:
            try:
                if use_brand_path and hasattr(mod, "stage_brand_packages"):
                    staged_paths = mod.stage_brand_packages(
                        version=ver,
                        allow_missing=bool(allow_missing),
                        progress_cb=stage_cb,
                        only_filenames=sel_list,
                    )
                else:
                    staged_paths = mod.stage_packages(
                        version=ver, allow_missing=bool(allow_missing)
                    )
                out["staged"] = [str(p) for p in staged_paths]
            except FileNotFoundError as exc:
                out["error"] = f"stage failed: {exc}"[:300]
                return out
            except Exception as exc:  # noqa: BLE001
                out["error"] = f"stage failed: {exc}"[:300]
                return out

        if upload:
            try:
                if use_brand_path and hasattr(mod, "upload_brand_packages"):
                    code = int(
                        mod.upload_brand_packages(
                            version=ver,
                            dry_run=bool(dry_run),
                            install_serve=bool(install_serve),
                            force=bool(force),
                            allow_missing=bool(allow_missing),
                            progress_cb=upload_cb,
                            only_filenames=sel_list,
                        )
                    )
                else:
                    code = int(
                        mod.upload_packages(
                            version=ver,
                            dry_run=bool(dry_run),
                            install_serve=bool(install_serve),
                            force=bool(force),
                            allow_missing=bool(allow_missing),
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                out["error"] = f"upload failed: {exc}"[:300]
                return out
            out["upload_code"] = code
            if code != 0:
                out["error"] = f"upload_packages returned {code}"
                return out

        out["ok"] = True
        out["inventory_after"] = self.list_local_packages(
            version=ver, brand_wide=bool(brand_wide)
        )
        return out

    def validate_package_file_path(self, path: str | Path) -> dict[str, Any]:
        """Validate a local filesystem path for monopin package stage/upload.

        Pure-ish: no SSH. Returns resolved path, filename, version, platform
        when the basename matches a catalog installer; otherwise an honest error.
        """
        raw = str(path or "").strip()
        out: dict[str, Any] = {
            "ok": False,
            "path": raw,
            "resolved": "",
            "filename": "",
            "version": "",
            "platform": "",
            "size": 0,
            "error": "",
        }
        if not raw:
            out["error"] = "path is required"
            return out
        # Reject null bytes / empty after expand
        if "\x00" in raw:
            out["error"] = "invalid path"
            return out
        try:
            p = Path(raw).expanduser()
            # Resolve carefully: missing path still resolves parents; use absolute
            p = p if p.is_absolute() else (Path.cwd() / p)
            p = p.resolve(strict=False)
        except (OSError, RuntimeError, ValueError) as exc:
            out["error"] = f"invalid path: {exc}"[:200]
            return out
        out["resolved"] = str(p)
        out["filename"] = p.name
        if not p.exists():
            out["error"] = f"path does not exist: {p}"
            return out
        if not p.is_file():
            out["error"] = f"path is not a file: {p}"
            return out
        try:
            size = int(p.stat().st_size)
        except OSError as exc:
            out["error"] = f"cannot stat path: {exc}"[:200]
            return out
        if size <= 0:
            out["error"] = f"file is empty: {p}"
            return out
        out["size"] = size
        # Match catalog monopin basename for current pin (or parse version from name)
        try:
            mod = self._load_host_paid_assets()
            ver = self.catalog_version_default()
            pkgs = mod.list_packages(ver)
        except Exception as exc:  # noqa: BLE001
            out["error"] = f"catalog unavailable: {exc}"[:200]
            return out
        matched = None
        for pkg in pkgs:
            if pkg.get("filename") == p.name:
                matched = pkg
                break
        if matched is None:
            # Allow versioned catalog basenames for non-default pins
            import re

            m = re.match(
                r"^restore-privacy-client-([0-9]+(?:\.[0-9]+)*)-(.+)$",
                p.name,
            )
            if not m:
                out["error"] = (
                    f"filename is not a catalog monopin installer: {p.name}"
                )
                return out
            alt_ver = m.group(1)
            try:
                pkgs_alt = mod.list_packages(alt_ver)
            except Exception:  # noqa: BLE001
                pkgs_alt = []
            for pkg in pkgs_alt:
                if pkg.get("filename") == p.name:
                    matched = pkg
                    break
            if matched is None:
                out["error"] = (
                    f"filename not in catalog for version {alt_ver}: {p.name}"
                )
                return out
        out["ok"] = True
        out["version"] = str(matched.get("version") or "")
        out["platform"] = str(matched.get("platform") or "")
        out["error"] = ""
        return out

    def upload_package_by_path(
        self,
        path: str | Path,
        *,
        stage: bool = True,
        upload: bool = True,
        dry_run: bool = False,
        force: bool = False,
        install_serve: bool = False,
    ) -> dict[str, Any]:
        """Stage (and optionally upload) one local package file by filesystem path.

        Admin path-upload entry: validates *path*, copies into
        ``status_page/assets/{version}/`` under the catalog basename, then
        drives :meth:`upload_catalog_packages` (allow_missing) so Helsinki upload
        uses the existing host_paid_assets path.
        """
        import shutil

        v = self.validate_package_file_path(path)
        out: dict[str, Any] = {
            "ok": False,
            "path": str(path or "").strip(),
            "resolved": v.get("resolved") or "",
            "filename": v.get("filename") or "",
            "version": v.get("version") or "",
            "platform": v.get("platform") or "",
            "size": int(v.get("size") or 0),
            "stage": bool(stage),
            "upload": bool(upload),
            "dry_run": bool(dry_run),
            "staged_to": "",
            "upload_code": None,
            "error": "",
            "deploy": {},
        }
        if not v.get("ok"):
            out["error"] = str(v.get("error") or "invalid path")
            return out

        ver = str(v["version"])
        fname = str(v["filename"])
        src = Path(str(v["resolved"]))
        stage_dir = self.repo_root / "status_page" / "assets" / ver
        dest = stage_dir / fname

        if dry_run and not stage and not upload:
            out["ok"] = True
            out["error"] = "dry-run: nothing to do (stage and upload both off)"
            return out

        if stage:
            try:
                stage_dir.mkdir(parents=True, exist_ok=True)
                if dry_run:
                    out["staged_to"] = str(dest)
                    out["error"] = ""
                else:
                    if src.resolve() != dest.resolve():
                        shutil.copy2(src, dest)
                    out["staged_to"] = str(dest)
                    if not dest.is_file() or dest.stat().st_size <= 0:
                        out["error"] = f"stage failed: dest missing or empty ({dest})"
                        return out
            except OSError as exc:
                out["error"] = f"stage failed: {exc}"[:300]
                return out

        if upload:
            # Reuse shipped catalog upload (allow_missing so single-file ships)
            dep = self.upload_catalog_packages(
                version=ver,
                stage=False,  # already staged this file
                upload=True,
                dry_run=bool(dry_run),
                force=bool(force),
                allow_missing=True,
                install_serve=bool(install_serve),
            )
            out["deploy"] = dep
            out["upload_code"] = dep.get("upload_code")
            if not dep.get("ok"):
                out["error"] = str(dep.get("error") or "upload failed")[:300]
                out["missing_ssh_keys"] = bool(dep.get("missing_ssh_keys"))
                out["redirect"] = str(dep.get("redirect") or "")
                # Stage may still have succeeded
                if stage and out.get("staged_to") and not dry_run:
                    if not out.get("missing_ssh_keys"):
                        out["error"] = (
                            f"staged ok but upload failed: {out['error']}"
                        )[:300]
                return out
            out["missing_ssh_keys"] = False
            out["ssh_key_path"] = str(dep.get("ssh_key_path") or "")

        out["ok"] = True
        out["error"] = ""
        return out
