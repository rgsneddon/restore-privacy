"""RPT encrypted DATA plane — TUN IP packets sealed/opened over UDP.

This is the real traffic path: every packet through seal_packet / open_packet
on the shipped RptClient session (not raw IP over UDP).
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
from node.traffic_shape import (
    DEFAULT_TRAFFIC_SHAPE,
    TrafficShapePolicy,
    apply_send_jitter,
)
from node.obfuscation import maybe_unwrap, product_obfuscation_enabled

from .connect import RptClient


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
    started: bool = False
    stopped: bool = False


class RptDataPlane:
    """Bidirectional RPT DATA loop bound to an established client session."""

    def __init__(
        self,
        client: RptClient,
        *,
        traffic_shape: TrafficShapePolicy | None = None,
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
        keepalive_every = 30.0  # keep node session alive (routing / idle prune)
        while not self._stop.is_set():
            try:
                rlist = [sock]
                fd = tun.fileno()
                if fd >= 0:
                    rlist.append(fd)
                readable, _, _ = select.select(rlist, [], [], 0.05)
            except (ValueError, OSError):
                readable = []
                fd = -1

            # UDP -> NODE_STATUS control | unwrap+open DATA -> TUN
            # (nonblocking only — never steal frames via keepalive recv)
            try:
                data, _addr = sock.recvfrom(65535)
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
                    if self.traffic_shape.jitter_ms_max > 0:
                        apply_send_jitter(self.traffic_shape.jitter_ms_max)
                    frame = self.client.seal_packet(pkt)
                    sock.sendto(frame, self.client.endpoint.address)
                    self.stats.tun_to_udp += 1
            except Exception:
                self.stats.errors += 1

            # Optional cover traffic (dummy sealed frames)
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

            # Periodic KEEPALIVE so idle tunnels are not pruned on the node
            if (now - last_keepalive) >= keepalive_every:
                try:
                    self.client.send_keepalive()
                except Exception:
                    self.stats.errors += 1
                last_keepalive = now

            if fd < 0:
                time.sleep(0.01)

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
            obfs = None
        frame = pack_data(sess.session_id, sess.counter_out, nonce, sealed)
        wire = maybe_wrap(frame, enabled=obfs) if obfs is not None else maybe_wrap(frame)
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
