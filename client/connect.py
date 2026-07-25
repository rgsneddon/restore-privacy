"""RPT client connect path — authorized handshake + session (testable without UI).

Admission is cryptographic only: **no public-IP geo** gate and **no third-party geo**
lookup on Connect. Multi-hop residual (when enabled) dials the exit hop; default is
single-hop product entry.
"""

from __future__ import annotations

import hashlib
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional  # Callable used by status_cb

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from node.crypto_session import CoverFrame, SessionCrypto, derive_session_key
from node.elgamal import ElGamalPublicKey
from node.handshake import build_client_hello, ed25519_pub_raw
from node.pedersen import PedersenCommitment, PedersenOpening, open_verified
from node.pfs import (
    EPH_PUB_LEN,
    EphemeralX25519,
    derive_legacy_session_shared,
    derive_pfs_session_shared,
    session_crypto_from_shared,
    x25519_shared_secret,
)
from node.obfuscation import maybe_unwrap, maybe_wrap, product_obfuscation_enabled


def _outer_obfs_enabled() -> bool:
    """Product outer wrap: user Settings / env via product_policy when available."""
    try:
        from client.product_policy import product_outer_obfuscation_enabled

        return bool(product_outer_obfuscation_enabled())
    except Exception:  # noqa: BLE001
        return bool(product_obfuscation_enabled())
from node.protocol import (
    MAGIC,
    MsgType,
    pack_data,
    pack_keepalive,
    parse_data,
    parse_server_hello,
    peek_type,
)
from node.traffic_shape import DEFAULT_TRAFFIC_SHAPE, TrafficShapePolicy

from .endpoint import DEFAULT_ENDPOINT, Endpoint
from .full_tunnel import FullTunnelPlan, assert_full_tunnel_plan, build_full_tunnel_plan
from .capacity_probe import probe_peer_capacity_map
from .multihop import (
    REASON_CAPACITY_MIGRATION,
    MultiHopConfig,
    capacity_migration_advisory,
    entry_endpoint,
    is_multihop_active,
    multihop_config_from_env,
    multihop_status_text,
    residual_endpoint,
    residual_try_order,
    select_residual_endpoint,
)
from .wipe_hop import (
    REASON_WIPE_DRAIN_FAILOVER,
    REASON_WIPE_REJOIN,
    WipeSignal,
    apply_wipe_signal_to_flags,
    parse_node_status_wire,
    parse_wipe_signal_json,
    wipe_hop_advisory,
)
from .secrets_loader import (
    ensure_device_admission_key,
    load_client_private_key,
    load_node_elgamal_public_for_endpoint,
)


def _tunnel_plan_for_session(
    existing: Optional[FullTunnelPlan], vpn_ip: str
) -> FullTunnelPlan:
    """Reuse plan only when VPN IP still matches; otherwise build a fresh plan."""
    ip = (vpn_ip or "").strip()
    if (
        existing is not None
        and existing.tunnel_client_ip == ip
        and existing.is_full_tunnel()
        and not assert_full_tunnel_plan(existing)
    ):
        return existing
    return build_full_tunnel_plan(ip)


class ConnectState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    DISCONNECTED = "disconnected"


@dataclass
class ClientSession:
    session_id: bytes
    crypto: SessionCrypto
    vpn_ip: str
    endpoint: Endpoint
    counter_out: int = 0
    client_pub: bytes = b""
    pfs: bool = False


@dataclass
class ConnectResult:
    ok: bool
    state: ConnectState
    message: str
    session: Optional[ClientSession] = None
    tunnel_plan: Optional[FullTunnelPlan] = None


StatusCallback = Callable[[str], None]


def format_connect_failure(
    exc: BaseException,
    *,
    host: str,
    port: int,
    timeout_s: float,
) -> str:
    """User-facing connect error — never bare 'timed out' without endpoint context.

    UDP HELLO timeouts usually mean the node is down, firewalled, or blocked;
    the message names host:port so the user can act.

    WinError 10054 / connection reset on residual HELLO often means the node
    dropped the session (payment admission, wrong keys, or host closed the
    path) — surface that instead of only the raw socket code.
    """
    target = f"{host}:{int(port)}"
    name = type(exc).__name__
    raw = str(exc).strip() or name
    low = raw.lower()

    # socket.timeout and TimeoutError both surface as "timed out" on Windows
    is_timeout = isinstance(exc, (TimeoutError, socket.timeout)) or (
        name in ("timeout", "TimeoutError")
        or low in ("timed out", "timeout")
        or "timed out" in low
    )
    if is_timeout:
        secs = int(timeout_s) if timeout_s == int(timeout_s) else timeout_s
        return (
            f"No reply from VPN node {target} within {secs}s. "
            "If you just paid: enter the keygen from your fulfilment email "
            "(Settings → Payment entitlement / keygen, or the unlock dialog), "
            "then Connect again so this device is bound. "
            "Also check internet, Windows Firewall/UDP, or that the node is online. "
            "On Windows, run AllowFirewall.bat (or reinstall) if residual is blocked."
        )

    # WSAECONNRESET / forcibly closed — common when remote drops residual HELLO
    is_reset = (
        isinstance(exc, ConnectionResetError)
        or "10054" in raw
        or "forcibly closed" in low
        or "connection reset" in low
        or "wsaeconnreset" in low
    )
    if is_reset:
        return (
            f"VPN node {target} closed the residual connection "
            f"(remote reset: {raw[:80]}). "
            "Usually: licence keygen not entered, device not bound to your paid "
            "subscription, or node refused HELLO. Enter the keygen from your email, "
            "tap Verify keygen / unlock Connect, then try Connect again."
        )

    # Secrets / admission often include useful detail already
    if "secret" in low or "client_ed25519" in low or "node_elgamal" in low:
        return raw if len(raw) <= 160 else raw[:157] + "…"

    if "payment entitlement" in low or "admission" in low:
        return (
            f"{raw} (node {target}). Enter your keygen from the fulfilment email "
            "and verify unlock before Connect."
        )

    if len(raw) <= 120 and target not in raw:
        return f"{raw} (node {target})"
    if target not in raw and len(raw) < 100:
        return f"{raw} — node {target}"
    return raw if len(raw) <= 160 else raw[:157] + "…"


def complete_server_hello(
    reply: bytes,
    client_nonce: bytes,
    client_pub: bytes,
    client_eph: EphemeralX25519 | None = None,
    *,
    traffic_shape: TrafficShapePolicy | None = None,
    require_pfs: bool = True,
) -> ClientSession:
    """Process SERVER_HELLO using real RPT2 crypto (shipped path).

    Product default *require_pfs=True*: session AEAD keys must use ephemeral
    X25519. Legacy nonce-only derivation remains only when require_pfs=False
    (interop tests / older nodes).
    """
    if peek_type(reply) != MsgType.SERVER_HELLO:
        raise ValueError("expected SERVER_HELLO")
    s_commit_b, session_id, nonce, sealed = parse_server_hello(reply)
    hello_shared = hashlib.sha256(client_nonce + client_pub + b"|hello").digest()
    hello_key = derive_session_key(
        hello_shared, salt=client_nonce[:16], info=b"rpt-v2-hello"
    )
    aad = b"RPT2-SERVER-HELLO" + session_id
    # Raw AEAD open — handshake plain is not DATA-padded
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

    plain = ChaCha20Poly1305(hello_key).decrypt(nonce, sealed, aad)
    if len(plain) < 32 + 288 + 4:
        raise ValueError("SERVER_HELLO payload too short")
    server_nonce = plain[:32]
    opening = PedersenOpening.import_bytes(plain[32 : 32 + 288])
    commit = PedersenCommitment.import_bytes(s_commit_b)
    open_verified(commit, opening)
    ip_bytes = plain[32 + 288 : 32 + 288 + 4]
    vpn_ip = ".".join(str(b) for b in ip_bytes)

    pfs = False
    server_eph_off = 32 + 288 + 4
    if (
        client_eph is not None
        and len(plain) >= server_eph_off + EPH_PUB_LEN
    ):
        server_eph_pub = plain[server_eph_off : server_eph_off + EPH_PUB_LEN]
        eph_shared = x25519_shared_secret(client_eph.private, server_eph_pub)
        session_shared = derive_pfs_session_shared(
            client_nonce, server_nonce, session_id, client_pub, eph_shared
        )
        pfs = True
    else:
        if require_pfs:
            raise ValueError(
                "product session path requires PFS (ephemeral X25519); "
                "legacy nonce-only derivation is not the product default"
            )
        session_shared = derive_legacy_session_shared(
            client_nonce, server_nonce, session_id, client_pub
        )
    crypto = session_crypto_from_shared(session_shared, client_nonce)
    if traffic_shape is not None:
        crypto.traffic_shape = traffic_shape
    return ClientSession(
        session_id=session_id,
        crypto=crypto,
        vpn_ip=vpn_ip,
        endpoint=DEFAULT_ENDPOINT,
        client_pub=client_pub,
        pfs=pfs,
    )


def build_authorized_client_hello(
    client_priv: Ed25519PrivateKey,
    node_pub: ElGamalPublicKey,
    *,
    with_pfs: bool = True,
) -> tuple[bytes, bytes, bytes, EphemeralX25519 | None]:
    """Real CLIENT_HELLO for authorized product client (PFS by default)."""
    return build_client_hello(client_priv, node_pub, with_pfs=with_pfs)


def assert_protocol_magic() -> bytes:
    assert MAGIC == b"RPT2"
    return MAGIC


class RptClient:
    """Auto-connect client controller used by Windows/Android shells."""

    def __init__(
        self,
        endpoint: Endpoint | None = None,
        secrets_dir: Path | str | None = None,
        status_cb: StatusCallback | None = None,
        multihop: MultiHopConfig | None = None,
        *,
        entry_healthy: bool = True,
        exit_healthy: bool = True,
        entry_draining: bool = False,
        peer_capacity: dict[str, float] | None = None,
        probe_capacity: bool = True,
        capacity_transport: object | None = None,
    ):
        self.multihop = multihop if multihop is not None else multihop_config_from_env()
        # Health hints for weekly entry wipe failover (entry-primary / exit failover).
        self.entry_healthy = bool(entry_healthy)
        self.exit_healthy = bool(exit_healthy)
        self.entry_draining = bool(entry_draining)
        # Optional host → utilization (0..1) for near-capacity residual migration.
        # Missing map → no capacity migration (default product path unchanged).
        self.peer_capacity: dict[str, float] | None = (
            dict(peer_capacity) if peer_capacity else None
        )
        # When True and peer_capacity not pre-set, best-effort private probes run
        # before residual select (fail-soft; requires RPT_CAPACITY_TOKEN).
        self.probe_capacity = bool(probe_capacity)
        self._capacity_transport = capacity_transport
        self.last_selection_reason: str = ""
        self.last_capacity_advisory: str = ""
        self.last_wipe_advisory: str = ""
        self._wipe_poll_stop = threading.Event()
        self._wipe_poll_thread: Optional[threading.Thread] = None
        # Residual dial: preference-aware (entry healthy → entry; else exit failover;
        # near-capacity preferred → freer peer when capacity hints say so;
        # wipe-drain → random alternate; ready → rejoin preferred).
        if endpoint is not None:
            self.endpoint = endpoint
            self._endpoint_pinned = True
        else:
            self._endpoint_pinned = False
            try:
                self._refresh_capacity_from_probes(force=False)
                sel = select_residual_endpoint(
                    self.multihop,
                    entry_healthy=self.entry_healthy,
                    exit_healthy=self.exit_healthy,
                    entry_draining=self.entry_draining,
                    peer_capacity=self.peer_capacity,
                )
                self.endpoint = sel.endpoint
                self.last_selection_reason = sel.reason
            except Exception:
                self.endpoint = residual_endpoint(self.multihop)
        self.secrets_dir = Path(secrets_dir) if secrets_dir else None
        self.status_cb = status_cb or (lambda _m: None)
        self.state = ConnectState.IDLE
        self.session: Optional[ClientSession] = None
        self.tunnel_plan: Optional[FullTunnelPlan] = None
        self._sock: Optional[socket.socket] = None
        self._stop = threading.Event()
        self._io_thread: Optional[threading.Thread] = None

    def set_node_health(
        self,
        *,
        entry_healthy: Optional[bool] = None,
        exit_healthy: Optional[bool] = None,
        entry_draining: Optional[bool] = None,
    ) -> None:
        """Update entry/exit health for automatic failover / re-entry preference."""
        if entry_healthy is not None:
            self.entry_healthy = bool(entry_healthy)
        if exit_healthy is not None:
            self.exit_healthy = bool(exit_healthy)
        if entry_draining is not None:
            self.entry_draining = bool(entry_draining)

    def set_peer_capacity(
        self,
        peer_capacity: dict[str, float] | None,
    ) -> None:
        """Inject or clear host → utilization map for capacity-aware residual pick."""
        self.peer_capacity = dict(peer_capacity) if peer_capacity else None

    def apply_wipe_signal(
        self,
        signal: WipeSignal | None,
        *,
        reconnect: bool = True,
        timeout: float = 20.0,
    ) -> str:
        """Apply drain/ready signal; auto hop-off or rejoin without user input.

        Returns a short note of the action taken.
        """
        preferred = entry_endpoint(self.multihop).host
        draining, reselect, note = apply_wipe_signal_to_flags(
            signal,
            preferred_host=preferred,
            current_entry_draining=self.entry_draining,
        )
        self.entry_draining = draining
        if not reselect:
            return note
        # Automatic residual re-select + reconnect (background; no UI confirm)
        if reconnect:
            try:
                self.disconnect()
            except Exception:  # noqa: BLE001
                pass
            result = self.connect(timeout=timeout, force_reconnect=True)
            if result.ok:
                if self.last_selection_reason == REASON_WIPE_DRAIN_FAILOVER:
                    self.last_wipe_advisory = (
                        f"Notice: preferred residual ({preferred}) is draining "
                        f"for wipe/rebuild — automatically hopped to "
                        f"{self.endpoint.host}:{self.endpoint.port}."
                    )
                    self._status(self.last_wipe_advisory)
                elif note == "ready_rejoin_preferred":
                    self.last_wipe_advisory = (
                        f"Notice: preferred residual is ready again — automatically "
                        f"rejoining {self.endpoint.host}:{self.endpoint.port}."
                    )
                    self._status(self.last_wipe_advisory)
            return f"{note};reconnect_ok={result.ok}"
        return note

    def process_node_status_frame(self, frame: bytes) -> str:
        """Consume residual NODE_STATUS wire frame (e.g. KEEPALIVE reply)."""
        try:
            inner = maybe_unwrap(frame, enabled=_outer_obfs_enabled())
        except Exception:  # noqa: BLE001
            inner = frame
        signal = parse_node_status_wire(inner)
        return self.apply_wipe_signal(signal, reconnect=True)

    def poll_preferred_node_state(
        self,
        *,
        url: str | None = None,
        timeout_s: float = 2.0,
        reconnect: bool = True,
    ) -> str:
        """HTTP poll private node-state for preferred residual (fail soft)."""
        import urllib.error
        import urllib.request

        preferred = entry_endpoint(self.multihop)
        host = (preferred.host or "").strip()
        if not host:
            return "no_preferred_host"
        poll_url = (url or f"http://{host}:8080/api/private/node-state").strip()
        try:
            req = urllib.request.Request(poll_url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
                body = resp.read()
        except Exception:  # noqa: BLE001
            return "poll_failed"
        signal = parse_wipe_signal_json(body)
        return self.apply_wipe_signal(signal, reconnect=reconnect)

    def start_wipe_hop_watch(self, *, interval_s: float = 30.0) -> None:
        """Background poll preferred peer drain/ready; auto hop/rejoin."""
        if self._wipe_poll_thread and self._wipe_poll_thread.is_alive():
            return
        self._wipe_poll_stop.clear()

        def _loop() -> None:
            while not self._wipe_poll_stop.wait(timeout=max(5.0, float(interval_s))):
                try:
                    self.poll_preferred_node_state(reconnect=True)
                except Exception:  # noqa: BLE001
                    continue

        self._wipe_poll_thread = threading.Thread(
            target=_loop, name="rpt-wipe-hop-watch", daemon=True
        )
        self._wipe_poll_thread.start()

    def stop_wipe_hop_watch(self) -> None:
        self._wipe_poll_stop.set()

    def _refresh_capacity_from_probes(self, *, force: bool = True) -> dict[str, float]:
        """Best-effort private capacity probes → peer_capacity map (fail-soft).

        Skips network when probe_capacity is False, or when a map was already
        injected and *force* is False. Never raises; never invents utilization.
        Probe failures leave the map unchanged (no synthetic full/empty load).
        """
        if not self.probe_capacity:
            return dict(self.peer_capacity or {})
        if self.peer_capacity and not force:
            return dict(self.peer_capacity)
        try:
            probed = probe_peer_capacity_map(
                transport=self._capacity_transport,  # type: ignore[arg-type]
            )
        except Exception:  # noqa: BLE001
            probed = {}
        if not probed:
            return dict(self.peer_capacity or {})
        base = dict(self.peer_capacity or {})
        base.update(probed)
        self.peer_capacity = base
        return dict(self.peer_capacity)

    def _status(self, msg: str) -> None:
        self.status_cb(msg)

    def _hello_to_endpoint(
        self,
        endpoint: Endpoint,
        *,
        timeout: float,
        sdir: Path,
        client_priv,
        mh_note: str,
    ) -> ConnectResult:
        """Single residual HELLO attempt to *endpoint*."""
        self.endpoint = endpoint
        node_pub = load_node_elgamal_public_for_endpoint(endpoint, sdir)
        frame, client_nonce, client_pub, client_eph = build_authorized_client_hello(
            client_priv, node_pub, with_pfs=True
        )
        assert_protocol_magic()
        wire = maybe_wrap(frame, enabled=_outer_obfs_enabled())

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(timeout)
            sock.sendto(wire, endpoint.address)
            entry_host = entry_endpoint(self.multihop).host
            if self.last_selection_reason == REASON_CAPACITY_MIGRATION:
                hop_kind = "capacity migration residual"
            elif self.last_selection_reason == REASON_WIPE_DRAIN_FAILOVER:
                hop_kind = "wipe-drain hop residual"
            elif endpoint.host != entry_host and (
                is_multihop_active(self.multihop)
                or self.last_selection_reason
                in (
                    "exit_failover",
                    "hello_failover",
                    "multihop_residual_via_exit",
                    REASON_CAPACITY_MIGRATION,
                    REASON_WIPE_DRAIN_FAILOVER,
                )
            ):
                hop_kind = (
                    "exit failover"
                    if self.last_selection_reason
                    in ("exit_failover", "hello_failover")
                    else "exit residual"
                )
            else:
                hop_kind = "entry"
            self._status(
                f"HELLO sent → {endpoint.host}:{endpoint.port} ({hop_kind})"
            )
            raw_reply, _addr = sock.recvfrom(65535)
            reply = maybe_unwrap(raw_reply)
            session = complete_server_hello(
                reply, client_nonce, client_pub, client_eph
            )
            session.endpoint = endpoint
            self.session = session
            self.tunnel_plan = _tunnel_plan_for_session(
                self.tunnel_plan, session.vpn_ip
            )
            self._sock = sock
            sock = None  # ownership transferred; disconnect() closes
            self.state = ConnectState.CONNECTED
            # Background: poll preferred peer drain/ready; hop off / rejoin
            # automatically for scheduled wipe without user interaction.
            try:
                self.start_wipe_hop_watch()
            except Exception:  # noqa: BLE001
                pass
            pfs_note = " PFS" if session.pfs else ""
            self._status(
                f"Connected — tunnel IP {session.vpn_ip} (full VPN{pfs_note}); {mh_note}"
            )
            return ConnectResult(
                ok=True,
                state=self.state,
                message=f"connected as {session.vpn_ip}",
                session=session,
                tunnel_plan=self.tunnel_plan,
            )
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

    def connect(
        self,
        timeout: float = 20.0,
        *,
        force_reconnect: bool = False,
        residual_ready: bool = False,
    ) -> ConnectResult:
        """Perform authorized RPT handshake with residual node (entry or exit).

        Preference (automatic, no manual user step):
        - Entry healthy (not draining) → prefer **entry** residual (re-entry after rebuild).
        - Entry down/draining → **exit failover** residual so flow is retained.
        - Preferred residual near connection capacity + freer peer → **capacity migration**.
        - Multi-hop active + entry up → residual-via-exit product path.
        - HELLO failure on primary → try alternate hop when healthy (solid failover).
        - Fail closed if neither path succeeds.
        """
        _ = residual_ready  # residual attach is handled by platform tunnel layers
        if (
            not force_reconnect
            and self.state == ConnectState.CONNECTED
            and self.session is not None
            and self.tunnel_plan is not None
        ):
            self._status(
                f"Already connected — tunnel IP {self.session.vpn_ip}"
            )
            return ConnectResult(
                ok=True,
                state=ConnectState.CONNECTED,
                message=f"already connected as {self.session.vpn_ip}",
                session=self.session,
                tunnel_plan=self.tunnel_plan,
            )

        self.state = ConnectState.CONNECTING
        mh_note = multihop_status_text(self.multihop)
        self.last_capacity_advisory = ""

        if self._endpoint_pinned:
            targets = [self.endpoint]
            self.last_selection_reason = "pinned"
        else:
            try:
                # Live private capacity probes (fail-soft) when token configured
                self._refresh_capacity_from_probes(force=True)
                sel = select_residual_endpoint(
                    self.multihop,
                    entry_healthy=self.entry_healthy,
                    exit_healthy=self.exit_healthy,
                    entry_draining=self.entry_draining,
                    peer_capacity=self.peer_capacity,
                )
                self.last_selection_reason = sel.reason
                self.endpoint = sel.endpoint
                advisory = capacity_migration_advisory(sel)
                if advisory:
                    self.last_capacity_advisory = advisory
                    self._status(advisory)
                    mh_note = (
                        f"{mh_note}; capacity migration to freer peer "
                        f"{sel.endpoint.host}:{sel.endpoint.port}"
                    )
                elif sel.reason == REASON_CAPACITY_MIGRATION:
                    # Defensive: reason set but advisory builder returned None
                    mh_note = f"{mh_note}; capacity migration residual"
                elif sel.reason == REASON_WIPE_DRAIN_FAILOVER:
                    wadv = wipe_hop_advisory(sel)
                    if wadv:
                        self.last_wipe_advisory = wadv
                        self._status(wadv)
                    mh_note = (
                        f"{mh_note}; wipe-drain hop to "
                        f"{sel.endpoint.host}:{sel.endpoint.port}"
                    )
                elif sel.failover_active:
                    mh_note = f"{mh_note}; exit failover (entry draining/down)"
                elif sel.reason == "entry_primary":
                    mh_note = f"{mh_note}; entry-primary residual"
            except Exception as sel_exc:
                self.last_selection_reason = "unavailable"
                self.state = ConnectState.ERROR
                msg = f"residual unavailable (fail closed): {sel_exc}"
                self._status(f"Connect failed: {msg}")
                return ConnectResult(ok=False, state=self.state, message=msg)

            targets = residual_try_order(
                self.multihop,
                entry_healthy=self.entry_healthy,
                exit_healthy=self.exit_healthy,
                entry_draining=self.entry_draining,
                peer_capacity=self.peer_capacity,
            )
            if not targets:
                targets = [self.endpoint]

        self._status(f"Connecting… {mh_note}")

        try:
            sdir = ensure_device_admission_key(self.secrets_dir)
            client_priv = load_client_private_key(sdir)
            last_exc: Optional[BaseException] = None
            for i, ep in enumerate(targets):
                try:
                    if i > 0:
                        self._status(
                            f"Primary residual failed — trying failover "
                            f"{ep.host}:{ep.port}"
                        )
                        self.last_selection_reason = "hello_failover"
                    return self._hello_to_endpoint(
                        ep,
                        timeout=timeout,
                        sdir=sdir,
                        client_priv=client_priv,
                        mh_note=mh_note,
                    )
                except Exception as exc:
                    last_exc = exc
                    continue
            assert last_exc is not None
            raise last_exc
        except Exception as exc:
            self.state = ConnectState.ERROR
            msg = format_connect_failure(
                exc,
                host=self.endpoint.host,
                port=self.endpoint.port,
                timeout_s=timeout,
            )
            self._status(f"Connect failed: {msg}")
            return ConnectResult(ok=False, state=self.state, message=msg)

    def auto_connect_on_launch(self, timeout: float = 20.0) -> ConnectResult:
        """Legacy helper — same as connect(); product UI no longer auto-invokes this."""
        return self.connect(timeout=timeout)

    def seal_packet(self, ip_packet: bytes) -> bytes:
        """Seal IP into RPT DATA then outer-layer wrap (product obfuscation)."""
        if not self.session:
            raise RuntimeError("not connected")
        self.session.counter_out += 1
        aad = self.session.session_id + struct.pack("!Q", self.session.counter_out)
        nonce, sealed = self.session.crypto.seal(ip_packet, aad=aad)
        inner = pack_data(
            self.session.session_id, self.session.counter_out, nonce, sealed
        )
        return maybe_wrap(inner, enabled=_outer_obfs_enabled())

    def open_packet(self, frame: bytes) -> bytes:
        if not self.session:
            raise RuntimeError("not connected")
        inner = maybe_unwrap(frame, enabled=_outer_obfs_enabled())
        sid, counter, nonce, sealed = parse_data(inner)
        if sid != self.session.session_id:
            raise ValueError("session mismatch")
        aad = sid + struct.pack("!Q", counter)
        try:
            return self.session.crypto.open(nonce, sealed, aad=aad)
        except CoverFrame as exc:
            raise CoverFrame("cover frame") from exc

    def open_packet_allow_cover(self, frame: bytes) -> tuple[bytes | None, bool]:
        """Open DATA (after outer unwrap); return (ip_or_None, is_cover)."""
        if not self.session:
            raise RuntimeError("not connected")
        inner = maybe_unwrap(frame, enabled=_outer_obfs_enabled())
        sid, counter, nonce, sealed = parse_data(inner)
        if sid != self.session.session_id:
            raise ValueError("session mismatch")
        aad = sid + struct.pack("!Q", counter)
        return self.session.crypto.open_allow_cover(nonce, sealed, aad=aad)

    def send_keepalive(self) -> None:
        if not self.session or not self._sock:
            return
        wire = maybe_wrap(
            pack_keepalive(self.session.session_id),
            enabled=_outer_obfs_enabled(),
        )
        try:
            self._sock.sendto(wire, self.endpoint.address)
            # Best-effort NODE_STATUS reply (drain/ready) for background hop/rejoin
            self._sock.settimeout(1.5)
            try:
                raw, _addr = self._sock.recvfrom(65535)
            except (socket.timeout, OSError):
                return
            try:
                inner = maybe_unwrap(raw, enabled=_outer_obfs_enabled())
            except Exception:  # noqa: BLE001
                inner = raw
            if peek_type(inner) == MsgType.NODE_STATUS:
                signal = parse_node_status_wire(inner)
                # Background hop/rejoin off the keepalive recv path
                threading.Thread(
                    target=lambda sig=signal: self.apply_wipe_signal(
                        sig, reconnect=True
                    ),
                    name="rpt-wipe-hop-ka",
                    daemon=True,
                ).start()
        except OSError:
            return

    def disconnect(self) -> None:
        self._stop.set()
        self.stop_wipe_hop_watch()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self.session = None
        self.state = ConnectState.DISCONNECTED
        self._status("Disconnected")
