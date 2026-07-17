"""RPT encrypted DATA plane — TUN IP packets sealed/opened over UDP.

This is the real traffic path: every packet through seal_packet / open_packet
on the shipped RptClient session (not raw IP over UDP).
"""

from __future__ import annotations

import select
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from node.protocol import MsgType, peek_type

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
    started: bool = False
    stopped: bool = False


class RptDataPlane:
    """Bidirectional RPT DATA loop bound to an established client session."""

    def __init__(self, client: RptClient):
        if not client.session or not client._sock:
            raise RuntimeError("RptDataPlane requires connected RptClient with socket")
        self.client = client
        self.sock: socket.socket = client._sock
        self.stats = DataPlaneStats()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._tun: Optional[TunIO] = None

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
        while not self._stop.is_set():
            try:
                rlist = [sock]
                fd = tun.fileno()
                if fd >= 0:
                    rlist.append(fd)
                readable, _, _ = select.select(rlist, [], [], 0.05)
            except (ValueError, OSError):
                readable = []

            # UDP -> open -> TUN (always try nonblocking recv)
            try:
                data, _addr = sock.recvfrom(65535)
                t = peek_type(data)
                if t == MsgType.DATA:
                    plain = self.client.open_packet(data)
                    tun.write_packet(plain)
                    self.stats.udp_to_tun += 1
            except BlockingIOError:
                pass
            except OSError:
                pass
            except Exception:
                self.stats.errors += 1

            # TUN -> seal -> UDP (real seal_packet on shipped client)
            try:
                pkt = tun.read_packet()
                if pkt:
                    frame = self.client.seal_packet(pkt)
                    sock.sendto(frame, self.client.endpoint.address)
                    self.stats.tun_to_udp += 1
            except Exception:
                self.stats.errors += 1

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
        plain = self.client.open_packet(frame)
        tun.write_packet(plain)
        self.stats.udp_to_tun += 1
        return plain


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
