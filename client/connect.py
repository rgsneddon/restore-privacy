"""RPT client connect path — authorized handshake + session (testable without UI)."""

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
from .flyclient_connect import (
    FlyclientConnectState,
    flyclient_decide_full_connect_work,
    flyclient_reuse_tunnel_plan,
)
from .full_tunnel import FullTunnelPlan, build_full_tunnel_plan
from .secrets_loader import (
    ensure_device_admission_key,
    load_client_private_key,
    load_node_elgamal_public,
)


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
    """
    target = f"{host}:{int(port)}"
    name = type(exc).__name__
    raw = str(exc).strip() or name

    # socket.timeout and TimeoutError both surface as "timed out" on Windows
    is_timeout = isinstance(exc, (TimeoutError, socket.timeout)) or (
        name in ("timeout", "TimeoutError")
        or raw.lower() in ("timed out", "timeout")
        or "timed out" in raw.lower()
    )
    if is_timeout:
        secs = int(timeout_s) if timeout_s == int(timeout_s) else timeout_s
        return (
            f"No reply from VPN node {target} within {secs}s. "
            "Check your internet, firewall/UDP, or that the node is online."
        )

    # Secrets / admission often include useful detail already
    if "secret" in raw.lower() or "client_ed25519" in raw.lower() or "node_elgamal" in raw.lower():
        return raw if len(raw) <= 160 else raw[:157] + "…"

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
    ):
        self.endpoint = endpoint or DEFAULT_ENDPOINT
        self.secrets_dir = Path(secrets_dir) if secrets_dir else None
        self.status_cb = status_cb or (lambda _m: None)
        self.state = ConnectState.IDLE
        self.session: Optional[ClientSession] = None
        self.tunnel_plan: Optional[FullTunnelPlan] = None
        self._sock: Optional[socket.socket] = None
        self._stop = threading.Event()
        self._io_thread: Optional[threading.Thread] = None

    def _status(self, msg: str) -> None:
        self.status_cb(msg)

    def connect(
        self,
        timeout: float = 20.0,
        *,
        force_reconnect: bool = False,
        residual_ready: bool = False,
    ) -> ConnectResult:
        """Perform authorized RPT handshake with the node (manual Connect path).

        Product connect uses device keys + node crypto only — no public-IP geo
        admission and no third-party geo lookup before handshake.

        Flyclient-style fast path: if a live session already exists and residual
        is ready (or only plan reuse is needed), skip a full HELLO exchange.
        """
        # --- flyclient tip: skip re-HELLO when session is warm ---
        step_plan = flyclient_decide_full_connect_work(
            FlyclientConnectState(
                session_connected=self.state == ConnectState.CONNECTED
                and self.session is not None,
                session_vpn_ip=(self.session.vpn_ip if self.session else ""),
                residual_routes_applied=residual_ready,
                residual_tun_up=residual_ready,
                has_if_index_or_iface=True,
                tunnel_plan_vpn_ip=(
                    self.tunnel_plan.tunnel_client_ip if self.tunnel_plan else ""
                ),
                force_reconnect=force_reconnect,
            )
        )
        if (
            not force_reconnect
            and step_plan.early_exit
            and self.session is not None
            and self.tunnel_plan is not None
        ):
            self._status(
                f"Already connected — tunnel IP {self.session.vpn_ip} (flyclient skip)"
            )
            return ConnectResult(
                ok=True,
                state=ConnectState.CONNECTED,
                message=f"already connected as {self.session.vpn_ip}",
                session=self.session,
                tunnel_plan=self.tunnel_plan,
            )
        if (
            not force_reconnect
            and not step_plan.needs_hello()
            and self.session is not None
        ):
            # Warm session: only refresh plan if needed
            self.tunnel_plan = flyclient_reuse_tunnel_plan(
                self.tunnel_plan, self.session.vpn_ip
            )
            self.state = ConnectState.CONNECTED
            self._status(
                f"Session warm — tunnel IP {self.session.vpn_ip} "
                f"(flyclient residual attach remaining)"
            )
            return ConnectResult(
                ok=True,
                state=self.state,
                message=f"connected as {self.session.vpn_ip}",
                session=self.session,
                tunnel_plan=self.tunnel_plan,
            )

        self.state = ConnectState.CONNECTING
        self._status("Connecting to Restore Privacy node…")

        try:
            # Pure crypto prep before socket I/O (short critical path to send HELLO).
            sdir = ensure_device_admission_key(self.secrets_dir)
            client_priv = load_client_private_key(sdir)
            node_pub = load_node_elgamal_public(sdir)
            frame, client_nonce, client_pub, client_eph = build_authorized_client_hello(
                client_priv, node_pub, with_pfs=True
            )
            assert_protocol_magic()
            wire = maybe_wrap(frame)

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.settimeout(timeout)
                sock.sendto(wire, self.endpoint.address)
                self._status(f"HELLO sent → {self.endpoint.host}:{self.endpoint.port}")
                raw_reply, _addr = sock.recvfrom(65535)
                reply = maybe_unwrap(raw_reply)
                session = complete_server_hello(
                    reply, client_nonce, client_pub, client_eph
                )
                session.endpoint = self.endpoint
                self.session = session
                # Reuse plan skeleton only when IP matches prior plan
                self.tunnel_plan = flyclient_reuse_tunnel_plan(
                    self.tunnel_plan, session.vpn_ip
                )
                self._sock = sock
                sock = None  # ownership transferred; disconnect() closes
                self.state = ConnectState.CONNECTED
                pfs_note = " PFS" if session.pfs else ""
                self._status(
                    f"Connected — tunnel IP {session.vpn_ip} (full VPN{pfs_note})"
                )
                return ConnectResult(
                    ok=True,
                    state=self.state,
                    message=f"connected as {session.vpn_ip}",
                    session=session,
                    tunnel_plan=self.tunnel_plan,
                )
            finally:
                # Close only if handshake failed before we assigned self._sock
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass
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
        return maybe_wrap(inner)

    def open_packet(self, frame: bytes) -> bytes:
        if not self.session:
            raise RuntimeError("not connected")
        inner = maybe_unwrap(frame)
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
        inner = maybe_unwrap(frame)
        sid, counter, nonce, sealed = parse_data(inner)
        if sid != self.session.session_id:
            raise ValueError("session mismatch")
        aad = sid + struct.pack("!Q", counter)
        return self.session.crypto.open_allow_cover(nonce, sealed, aad=aad)

    def send_keepalive(self) -> None:
        if not self.session or not self._sock:
            return
        wire = maybe_wrap(pack_keepalive(self.session.session_id))
        self._sock.sendto(wire, self.endpoint.address)

    def disconnect(self) -> None:
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self.session = None
        self.state = ConnectState.DISCONNECTED
        self._status("Disconnected")
