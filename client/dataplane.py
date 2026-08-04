"""RPT encrypted DATA plane — TUN IP packets sealed/opened over UDP.

This is the real traffic path: every packet through seal_packet / open_packet
on the shipped RptClient session (not raw IP over UDP).

Idle residual liveness: protocol KEEPALIVE is sent on a fixed lean interval
strictly under the node session idle prune window so long user-browsing idle
does not drop the session (and leave dual /1 blackholing internet). Keepalive
does **not** require cover/pad traffic.
"""

from __future__ import annotations

import select
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from node.crypto_session import CoverFrame
from node.protocol import MsgType, pack_data, peek_type
from node.sessions import DEFAULT_SESSION_IDLE_SEC
from node.traffic_shape import (
    DEFAULT_TRAFFIC_SHAPE,
    TrafficShapePolicy,
    apply_send_jitter,
)
from node.obfuscation import maybe_unwrap, product_obfuscation_enabled

from .connect import RptClient

# Consecutive failed keepalives before residual session is treated as dead.
KEEPALIVE_FAIL_THRESHOLD = 3
# Idle select/sleep backoff caps (seconds) — no busy spin.
IDLE_SELECT_MIN_S = 0.05
IDLE_SELECT_MAX_S = 0.40


def residual_keepalive_interval_s(
    node_idle_sec: float | None = None,
) -> float:
    """Protocol keepalive interval for residual dataplane (pure).

    Must stay **strictly less than** node :data:`DEFAULT_SESSION_IDLE_SEC` so
    idle prune cannot fire solely because the user is not browsing. Also short
    enough to refresh typical NAT/UDP mappings without high-rate cover traffic.

    Returns a value in ``[10, 25]`` seconds and ``< node_idle_sec``.
    """
    idle = float(
        node_idle_sec if node_idle_sec is not None else DEFAULT_SESSION_IDLE_SEC
    )
    if idle <= 0:
        idle = DEFAULT_SESSION_IDLE_SEC
    # ~1/3 of node idle, clamped — default 60s → 20s.
    interval = max(10.0, min(25.0, idle / 3.0))
    if interval >= idle:
        interval = max(5.0, idle * 0.4)
    return float(interval)


def residual_idle_select_max_s() -> float:
    """Max select/sleep wait while residual is quiet (resource bound)."""
    return float(IDLE_SELECT_MAX_S)


def residual_keepalive_under_node_idle(
    keepalive_s: float,
    node_idle_sec: float | None = None,
) -> bool:
    """True when *keepalive_s* is a safe residual interval vs node prune."""
    idle = float(
        node_idle_sec if node_idle_sec is not None else DEFAULT_SESSION_IDLE_SEC
    )
    return keepalive_s > 0 and keepalive_s < idle


class TunIO(Protocol):
    def read_packet(self, max_size: int = 65535) -> Optional[bytes]:
        """Return one IP packet or None if none available."""

    def write_packet(self, packet: bytes) -> None:
        """Write one decrypted IP packet to the TUN."""

    def fileno(self) -> int:
        """OS fileno for select(), or -1 if poll-only."""

    def close(self) -> None:
        ...


@dataclass
class DataPlaneStats:
    tun_to_udp: int = 0
    udp_to_tun: int = 0
    errors: int = 0
    cover_sent: int = 0
    cover_recv: int = 0
    keepalives_sent: int = 0
    keepalives_failed: int = 0
    consecutive_keepalive_failures: int = 0
    session_liveness_lost: bool = False
    started: bool = False
    stopped: bool = False


class RptDataPlane:
    """Bidirectional RPT DATA loop bound to an established client session."""

    def __init__(
        self,
        client: RptClient,
        *,
        traffic_shape: TrafficShapePolicy | None = None,
        on_liveness_lost: Optional[Callable[[], None]] = None,
        keepalive_interval_s: float | None = None,
    ):
        if not client.session or not client._sock:
            raise RuntimeError("RptDataPlane requires connected RptClient with socket")
        self.client = client
        self.sock: socket.socket = client._sock
        self.traffic_shape = traffic_shape or DEFAULT_TRAFFIC_SHAPE
        # Apply policy to session crypto for pad/cover on seal/open
        if client.session:
            client.session.crypto.traffic_shape = self.traffic_shape
        self.stats = DataPlaneStats()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._tun: Optional[TunIO] = None
        self._on_liveness_lost = on_liveness_lost
        self._keepalive_interval_s = (
            float(keepalive_interval_s)
            if keepalive_interval_s is not None
            else residual_keepalive_interval_s()
        )
        # Defensive: never schedule slower than node idle.
        if not residual_keepalive_under_node_idle(self._keepalive_interval_s):
            self._keepalive_interval_s = residual_keepalive_interval_s()

    def apply_traffic_shape(self, policy: TrafficShapePolicy | None) -> TrafficShapePolicy:
        """Hot-apply traffic shape to the live residual DATA plane + session crypto.

        Safe to call while the dataplane thread is running: the loop reads
        ``self.traffic_shape`` each packet/cover tick; session seal/open use
        ``crypto.traffic_shape`` for pad/cover. Does not stop residual capture.
        """
        pol = policy if policy is not None else DEFAULT_TRAFFIC_SHAPE
        self.traffic_shape = pol
        sess = getattr(self.client, "session", None)
        if sess is not None and getattr(sess, "crypto", None) is not None:
            sess.crypto.traffic_shape = pol
        return pol

    def is_running(self) -> bool:
        return self.stats.started and not self.stats.stopped and self._thread is not None

    def start(self, tun: TunIO) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._tun = tun
        self._stop.clear()
        self.stats = DataPlaneStats(started=True)
        self.sock.setblocking(False)
        self._thread = threading.Thread(target=self._loop, name="rpt-dataplane", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self.stats.stopped = True
        if self._tun:
            try:
                self._tun.close()
            except Exception:
                pass
            self._tun = None

    def _loop(self) -> None:
        tun = self._tun
        assert tun is not None
        sock = self.sock
        last_keepalive = 0.0
        last_cover = 0.0
        last_activity = time.time()
        # Lean protocol keepalive — independent of TUN browsing traffic / cover.
        keepalive_every = float(self._keepalive_interval_s)
        idle_select_s = IDLE_SELECT_MIN_S
        idle_select_max_s = residual_idle_select_max_s()
        liveness_notified = False
        while not self._stop.is_set():
            try:
                rlist = [sock]
                fd = tun.fileno()
                if fd >= 0:
                    rlist.append(fd)
                readable, _, _ = select.select(rlist, [], [], idle_select_s)
            except (ValueError, OSError):
                readable = []
                fd = -1

            # UDP -> NODE_STATUS control | unwrap+open DATA -> TUN
            # (nonblocking only — never steal frames via keepalive recv)
            try:
                data, _addr = sock.recvfrom(65535)
                last_activity = time.time()
                idle_select_s = IDLE_SELECT_MIN_S
                try:
                    try:
                        from client.product_policy import (
                            product_outer_obfuscation_enabled,
                        )

                        outer_on = bool(product_outer_obfuscation_enabled())
                    except Exception:  # noqa: BLE001
                        outer_on = bool(product_obfuscation_enabled())
                    inner = maybe_unwrap(data, enabled=outer_on)
                except Exception:  # noqa: BLE001
                    inner = data
                if peek_type(inner) == MsgType.NODE_STATUS:
                    # Drain/ready control — do not treat as sealed DATA
                    try:
                        threading.Thread(
                            target=lambda frame=data: self.client.process_node_status_frame(
                                frame
                            ),
                            name="rpt-wipe-hop-ns",
                            daemon=True,
                        ).start()
                    except Exception:  # noqa: BLE001
                        self.stats.errors += 1
                else:
                    # open_packet_allow_cover unwraps outer obfuscation layer
                    plain, is_cover = self.client.open_packet_allow_cover(data)
                    if is_cover:
                        self.stats.cover_recv += 1
                    elif plain:
                        tun.write_packet(plain)
                        self.stats.udp_to_tun += 1
            except BlockingIOError:
                pass
            except OSError:
                pass
            except Exception:
                self.stats.errors += 1

            # TUN -> seal+wrap -> UDP (real seal_packet on shipped client)
            try:
                pkt = tun.read_packet()
                if pkt:
                    last_activity = time.time()
                    idle_select_s = IDLE_SELECT_MIN_S
                    if self.traffic_shape.jitter_ms_max > 0:
                        apply_send_jitter(self.traffic_shape.jitter_ms_max)
                    frame = self.client.seal_packet(pkt)
                    sock.sendto(frame, self.client.endpoint.address)
                    self.stats.tun_to_udp += 1
            except Exception:
                self.stats.errors += 1

            # Optional cover traffic (dummy sealed frames) — not required for liveness
            now = time.time()
            if (
                self.traffic_shape.cover_traffic
                and self.traffic_shape.cover_interval_s > 0
                and (now - last_cover) >= self.traffic_shape.cover_interval_s
            ):
                try:
                    self._send_cover_frame()
                    self.stats.cover_sent += 1
                except Exception:
                    self.stats.errors += 1
                last_cover = now
                last_activity = now

            # Periodic KEEPALIVE so idle tunnels are not pruned (node + NAT/UDP).
            # Independent of TUN browsing traffic. Only advance timer on success.
            if (now - last_keepalive) >= keepalive_every:
                ok = False
                try:
                    ok = bool(self.client.send_keepalive())
                except Exception:
                    ok = False
                    self.stats.errors += 1
                if ok:
                    last_keepalive = now
                    self.stats.keepalives_sent += 1
                    self.stats.consecutive_keepalive_failures = 0
                    # Keepalive is residual activity (NAT refresh) — reset idle select.
                    last_activity = now
                    idle_select_s = IDLE_SELECT_MIN_S
                else:
                    self.stats.keepalives_failed += 1
                    self.stats.consecutive_keepalive_failures += 1
                    self.stats.errors += 1
                    # Retry sooner after failure (half interval) without busy loop.
                    last_keepalive = now - (keepalive_every * 0.5)
                    if (
                        self.stats.consecutive_keepalive_failures
                        >= KEEPALIVE_FAIL_THRESHOLD
                        and not self.stats.session_liveness_lost
                    ):
                        self.stats.session_liveness_lost = True
                        if not liveness_notified:
                            liveness_notified = True
                            self._notify_liveness_lost()

            # Idle backoff: when no TUN/UDP activity, lengthen select wait (battery).
            quiet_s = now - last_activity
            if quiet_s >= 0.5:
                idle_select_s = min(
                    idle_select_max_s,
                    IDLE_SELECT_MIN_S + min(quiet_s, 2.0) * 0.15,
                )
            if fd < 0:
                # Wintun poll-only: honour idle backoff (was capped at 50ms always).
                time.sleep(idle_select_s)

    def _notify_liveness_lost(self) -> None:
        """Best-effort callback when residual session cannot be kept alive."""
        cb = self._on_liveness_lost
        if not callable(cb):
            return
        try:
            cb()
        except Exception:
            pass
    def seal_from_tun_once(self, tun: TunIO) -> bytes:
        """Read one TUN packet and seal it via RptClient.seal_packet (tests + manual pump)."""
        pkt = tun.read_packet()
        if not pkt:
            raise RuntimeError("no TUN packet")
        frame = self.client.seal_packet(pkt)
        self.stats.tun_to_udp += 1
        return frame

    def open_to_tun_once(self, tun: TunIO, frame: bytes) -> bytes:
        """Open one RPT DATA frame via RptClient.open_packet and write to TUN."""
        plain, is_cover = self.client.open_packet_allow_cover(frame)
        if is_cover or plain is None:
            self.stats.cover_recv += 1
            return b""
        tun.write_packet(plain)
        self.stats.udp_to_tun += 1
        return plain

    def _send_cover_frame(self) -> bytes:
        """Seal and send one cover DATA frame (discarded by peer after open)."""
        sess = self.client.session
        if not sess:
            raise RuntimeError("not connected")
        sess.counter_out += 1
        aad = sess.session_id + struct.pack("!Q", sess.counter_out)
        nonce, sealed = sess.crypto.seal_cover(self.traffic_shape.pad_bucket, aad=aad)
        from node.obfuscation import maybe_wrap

        try:
            from client.product_policy import product_outer_obfuscation_enabled

            obfs = bool(product_outer_obfuscation_enabled())
        except Exception:  # noqa: BLE001
            # Lean residual baseline when policy import fails (no accidental wrap).
            obfs = False
        frame = pack_data(sess.session_id, sess.counter_out, nonce, sealed)
        wire = maybe_wrap(frame, enabled=obfs)
        self.sock.sendto(wire, self.client.endpoint.address)
        return wire


class QueueTun:
    """In-memory TUN for tests — still goes through seal/open on real client."""

    def __init__(self) -> None:
        import queue

        self.inbound: queue.Queue[bytes] = queue.Queue()  # to be "read" from TUN
        self.outbound: queue.Queue[bytes] = queue.Queue()  # written to TUN

    def read_packet(self, max_size: int = 65535) -> Optional[bytes]:
        try:
            return self.inbound.get_nowait()
        except Exception:
            return None

    def write_packet(self, packet: bytes) -> None:
        self.outbound.put(packet)

    def fileno(self) -> int:
        return -1

    def close(self) -> None:
        pass
