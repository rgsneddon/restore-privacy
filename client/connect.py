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
from typing import Callable, Optional  # Callable used by status_cb + uk_gate_fetcher

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from node.crypto_session import SessionCrypto, derive_session_key
from node.elgamal import ElGamalPublicKey
from node.handshake import build_client_hello, ed25519_pub_raw
from node.pedersen import PedersenCommitment, PedersenOpening, open_verified
from node.protocol import (
    MAGIC,
    MsgType,
    pack_data,
    pack_keepalive,
    parse_data,
    parse_server_hello,
    peek_type,
)

from .endpoint import DEFAULT_ENDPOINT, Endpoint
from .full_tunnel import FullTunnelPlan, build_full_tunnel_plan
from .secrets_loader import (
    ensure_device_admission_key,
    load_client_private_key,
    load_node_elgamal_public,
)
from .uk_gate import UkGateResult, check_uk_public_ip


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
) -> ClientSession:
    """Process SERVER_HELLO using real RPT2 crypto (shipped path)."""
    if peek_type(reply) != MsgType.SERVER_HELLO:
        raise ValueError("expected SERVER_HELLO")
    s_commit_b, session_id, nonce, sealed = parse_server_hello(reply)
    hello_shared = hashlib.sha256(client_nonce + client_pub + b"|hello").digest()
    hello_crypto = SessionCrypto(
        key=derive_session_key(hello_shared, salt=client_nonce[:16], info=b"rpt-v2-hello")
    )
    aad = b"RPT2-SERVER-HELLO" + session_id
    plain = hello_crypto.open(nonce, sealed, aad=aad)
    if len(plain) < 32 + 288 + 4:
        raise ValueError("SERVER_HELLO payload too short")
    server_nonce = plain[:32]
    opening = PedersenOpening.import_bytes(plain[32 : 32 + 288])
    commit = PedersenCommitment.import_bytes(s_commit_b)
    open_verified(commit, opening)
    ip_bytes = plain[32 + 288 : 32 + 288 + 4]
    vpn_ip = ".".join(str(b) for b in ip_bytes)

    session_shared = hashlib.sha256(client_nonce + server_nonce + session_id + client_pub).digest()
    crypto = SessionCrypto(
        key=derive_session_key(session_shared, salt=client_nonce[:16], info=b"rpt-v2-session")
    )
    return ClientSession(
        session_id=session_id,
        crypto=crypto,
        vpn_ip=vpn_ip,
        endpoint=DEFAULT_ENDPOINT,
        client_pub=client_pub,
    )


def build_authorized_client_hello(
    client_priv: Ed25519PrivateKey,
    node_pub: ElGamalPublicKey,
) -> tuple[bytes, bytes, bytes]:
    """Real CLIENT_HELLO for authorized product client."""
    return build_client_hello(client_priv, node_pub)


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
        uk_gate_fetcher: Optional[Callable[[], dict]] = None,
        skip_uk_gate: bool = False,
    ):
        self.endpoint = endpoint or DEFAULT_ENDPOINT
        self.secrets_dir = Path(secrets_dir) if secrets_dir else None
        self.status_cb = status_cb or (lambda _m: None)
        # Injectable geo fetch for tests; production uses live UK gate
        self.uk_gate_fetcher = uk_gate_fetcher
        self.skip_uk_gate = skip_uk_gate
        self.state = ConnectState.IDLE
        self.session: Optional[ClientSession] = None
        self.tunnel_plan: Optional[FullTunnelPlan] = None
        self._sock: Optional[socket.socket] = None
        self._stop = threading.Event()
        self._io_thread: Optional[threading.Thread] = None
        self.last_uk_gate: Optional[UkGateResult] = None

    def _status(self, msg: str) -> None:
        self.status_cb(msg)

    def run_uk_gate(self) -> UkGateResult:
        """Security gate: only United Kingdom public IPs may proceed to handshake."""
        if self.skip_uk_gate:
            result = UkGateResult(True, "UK gate skipped (test/dev)")
            self.last_uk_gate = result
            return result
        self._status("Verifying UK public IP location…")
        result = check_uk_public_ip(fetcher=self.uk_gate_fetcher)
        self.last_uk_gate = result
        if result.allowed:
            self._status(
                f"UK location OK"
                + (f" ({result.country_code})" if result.country_code else "")
            )
        else:
            self._status(result.message)
        return result

    def connect(self, timeout: float = 20.0) -> ConnectResult:
        """Perform authorized RPT handshake with the node (manual Connect path).

        UK public-IP gate runs first; non-UK users get a clear failure notice.
        """
        self.state = ConnectState.CONNECTING
        self._status("Connecting to Restore Privacy node…")

        # --- UK IP security gate (before any HELLO / secrets use) ---
        gate = self.run_uk_gate()
        if not gate.allowed:
            self.state = ConnectState.ERROR
            return ConnectResult(ok=False, state=self.state, message=gate.message)

        try:
            # First run: generate a unique Ed25519 device key if missing; reuse thereafter.
            sdir = ensure_device_admission_key(self.secrets_dir)
            client_priv = load_client_private_key(sdir)
            node_pub = load_node_elgamal_public(sdir)
            frame, client_nonce, client_pub = build_authorized_client_hello(client_priv, node_pub)
            assert_protocol_magic()

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(frame, self.endpoint.address)
            self._status(f"HELLO sent → {self.endpoint.host}:{self.endpoint.port}")
            reply, _addr = sock.recvfrom(65535)
            session = complete_server_hello(reply, client_nonce, client_pub)
            session.endpoint = self.endpoint
            self.session = session
            self.tunnel_plan = build_full_tunnel_plan(session.vpn_ip)
            self._sock = sock
            self.state = ConnectState.CONNECTED
            self._status(f"Connected — tunnel IP {session.vpn_ip} (full VPN)")
            return ConnectResult(
                ok=True,
                state=self.state,
                message=f"connected as {session.vpn_ip}",
                session=session,
                tunnel_plan=self.tunnel_plan,
            )
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
        if not self.session:
            raise RuntimeError("not connected")
        self.session.counter_out += 1
        aad = self.session.session_id + struct.pack("!Q", self.session.counter_out)
        nonce, sealed = self.session.crypto.seal(ip_packet, aad=aad)
        return pack_data(self.session.session_id, self.session.counter_out, nonce, sealed)

    def open_packet(self, frame: bytes) -> bytes:
        if not self.session:
            raise RuntimeError("not connected")
        sid, counter, nonce, sealed = parse_data(frame)
        if sid != self.session.session_id:
            raise ValueError("session mismatch")
        aad = sid + struct.pack("!Q", counter)
        return self.session.crypto.open(nonce, sealed, aad=aad)

    def send_keepalive(self) -> None:
        if not self.session or not self._sock:
            return
        self._sock.sendto(pack_keepalive(self.session.session_id), self.endpoint.address)

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
