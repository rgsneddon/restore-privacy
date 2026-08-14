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
# Packets to drain per turn. Wintun has no select() fd — one packet + sleep
# capped Windows at ~20 pps (desktop: Connected but zip-slow vs same node).
DATAPLANE_BURST = 32


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
    def read_packet(self, max_size: int = 65535, wait_ms: int = 0) -> Optional[bytes]:
        """Return one IP packet or None if none available.

        *wait_ms* is honoured by Wintun (WaitForSingleObject). Queue/other
        backends ignore it and return immediately.
        """

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
    first_tun_src: str = ""
    first_tun_dst: str = ""
    source_rewrites: int = 0
    skipped_non_unicast: int = 0


def ipv4_src_dst(pkt: bytes) -> tuple[str, str] | None:
    """Return (src, dst) for an IPv4 packet, or None."""
    if len(pkt) < 20 or (pkt[0] >> 4) != 4:
        return None
    src = f"{pkt[12]}.{pkt[13]}.{pkt[14]}.{pkt[15]}"
    dst = f"{pkt[16]}.{pkt[17]}.{pkt[18]}.{pkt[19]}"
    return src, dst


def ipv4_skip_forward(dst: str) -> bool:
    """True for dests that must not be sealed as residual DATA.

    Windows dual /1 also captures LAN/IGMP (desktop: ``pkt=10.88.0.206>192.168.1.1``
    then ``tun=0/0``). Those never get a residual reply. Keep 10.88.0.0/16
    (node Unbound) and public unicast.
    """
    parts = (dst or "").strip().split(".")
    if len(parts) != 4:
        return False
    try:
        a, b, _c, d = (int(p) for p in parts)
    except ValueError:
        return False
    if a < 0 or a > 255 or b < 0 or b > 255 or d < 0 or d > 255:
        return False
    if a >= 224 or d == 255:
        return True
    if a == 10:
        return b != 88
    if a == 192 and b == 168:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 169 and b == 254:
        return True
    if a == 127:
        return True
    return False


def _ip_checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) | data[i + 1]
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def _parse_ipv4(ip: str) -> bytes | None:
    parts = (ip or "").strip().split(".")
    if len(parts) != 4:
        return None
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if any(n < 0 or n > 255 for n in nums):
        return None
    return bytes(nums)


def _dns_a_query(name: str = "example.com") -> bytes:
    """RFC 1035 A-IN query. Empty/invalid DNS is ignored by 1.1.1.1 and Unbound."""
    import struct

    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    q = b""
    for label in (name or "example.com").split("."):
        part = label.encode("ascii", "ignore")[:63]
        if not part:
            continue
        q += bytes([len(part)]) + part
    q += b"\x00" + struct.pack("!HH", 1, 1)
    return header + q


def build_ipv4_udp_probe(src: str, dst: str, *, dport: int = 53) -> bytes | None:
    """IPv4/UDP DNS A query for residual DATA inject (no OS routing)."""
    src_b = _parse_ipv4(src)
    dst_b = _parse_ipv4(dst)
    if src_b is None or dst_b is None:
        return None
    payload = _dns_a_query("example.com")
    udp_len = 8 + len(payload)
    udp = bytearray(udp_len)
    udp[0:2] = (53053).to_bytes(2, "big")
    udp[2:4] = int(dport).to_bytes(2, "big")
    udp[4:6] = int(udp_len).to_bytes(2, "big")
    udp[8:] = payload
    # IPv4 UDP checksum 0 is dropped by some resolvers/nodes (desktop tun=2/0).
    ph = src_b + dst_b + bytes([0, 17, (udp_len >> 8) & 0xFF, udp_len & 0xFF])
    uc = _ip_checksum(ph + bytes(udp))
    if uc == 0:
        uc = 0xFFFF
    udp[6] = (uc >> 8) & 0xFF
    udp[7] = uc & 0xFF
    total = 20 + udp_len
    ip = bytearray(20)
    ip[0] = 0x45
    ip[2:4] = int(total).to_bytes(2, "big")
    ip[8] = 64
    ip[9] = 17
    ip[12:16] = src_b
    ip[16:20] = dst_b
    csum = _ip_checksum(bytes(ip))
    ip[10] = (csum >> 8) & 0xFF
    ip[11] = csum & 0xFF
    return bytes(ip) + bytes(udp)


def rewrite_ipv4_source(pkt: bytes, new_src: str) -> tuple[bytes, bool]:
    """Force IPv4 source to *new_src* (tunnel client IP) and fix checksums.

    Windows /32 Wintun often emits packets with the physical NIC source while
    routing them into the TUN. The node maps replies by dest VPN IP, so those
    packets get no DATA back (desktop log: tun=23/0).
    """
    src_b = _parse_ipv4(new_src)
    if src_b is None or len(pkt) < 20 or (pkt[0] >> 4) != 4:
        return pkt, False
    ihl = (pkt[0] & 0x0F) * 4
    if ihl < 20 or len(pkt) < ihl:
        return pkt, False
    if pkt[12:16] == src_b:
        return pkt, False
    out = bytearray(pkt)
    out[12:16] = src_b
    out[10] = 0
    out[11] = 0
    csum = _ip_checksum(bytes(out[:ihl]))
    out[10] = (csum >> 8) & 0xFF
    out[11] = csum & 0xFF
    proto = int(out[9])
    if proto == 17 and len(out) >= ihl + 8:
        # IPv4 UDP checksum may be zero
        out[ihl + 6] = 0
        out[ihl + 7] = 0
    elif proto == 6 and len(out) >= ihl + 18:
        tcp = bytearray(out[ihl:])
        tcp[16] = 0
        tcp[17] = 0
        plen = len(tcp)
        if plen % 2:
            body = bytes(tcp) + b"\x00"
        else:
            body = bytes(tcp)
        ph = bytes(out[12:16]) + bytes(out[16:20]) + bytes([0, 6, (plen >> 8) & 0xFF, plen & 0xFF])
        tc = _ip_checksum(ph + body)
        tcp[16] = (tc >> 8) & 0xFF
        tcp[17] = tc & 0xFF
        out[ihl:] = tcp
    return bytes(out), True


class RptDataPlane:
    """Bidirectional RPT DATA loop bound to an established client session."""

    def __init__(
        self,
        client: RptClient,
        *,
        traffic_shape: TrafficShapePolicy | None = None,
        on_liveness_lost: Optional[Callable[[], None]] = None,
        keepalive_interval_s: float | None = None,
        tunnel_src_ip: str | None = None,
    ):
        if not client.session or not client._sock:
            raise RuntimeError("RptDataPlane requires connected RptClient with socket")
        self.client = client
        self.sock: socket.socket = client._sock
        self._tunnel_src_ip = (tunnel_src_ip or "").strip() or None
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

    def _handle_udp_datagram(self, tun: TunIO, data: bytes, *, outer_on: bool) -> None:
        try:
            inner = maybe_unwrap(data, enabled=outer_on)
        except Exception:  # noqa: BLE001
            inner = data
        if peek_type(inner) == MsgType.NODE_STATUS:
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
            return
        plain, is_cover = self.client.open_packet_allow_cover(data)
        if is_cover:
            self.stats.cover_recv += 1
        elif plain:
            tun.write_packet(plain)
            self.stats.udp_to_tun += 1

    def seal_unicast_probe(self, dst: str = "1.1.1.1") -> bool:
        """Seal one public IPv4 UDP probe via the live residual session.

        OS bind+sendto often never appears on Wintun (desktop ``tun=0/0``).
        This injects on the dataplane path so ``udp_to_tun`` can prove return.
        """
        src = self._tunnel_src_ip or ""
        pkt = build_ipv4_udp_probe(src, dst)
        if not pkt:
            return False
        try:
            return bool(self._handle_tun_packet(self.sock, pkt))
        except Exception:
            self.stats.errors += 1
            return False

    def _handle_tun_packet(self, sock: socket.socket, pkt: bytes) -> bool:
        """Seal one TUN packet. True when it was real unicast (not skipped)."""
        info = ipv4_src_dst(pkt)
        # IPv6 / non-IPv4 must not be sealed as residual DATA (desktop
        # ``pkt=->- tun=156/0`` while IPv6 leak-mitigation was still applying).
        if info is None or ipv4_skip_forward(info[1]):
            self.stats.skipped_non_unicast += 1
            return False
        if not self.stats.first_tun_src:
            self.stats.first_tun_src, self.stats.first_tun_dst = info
        if self._tunnel_src_ip:
            pkt, changed = rewrite_ipv4_source(pkt, self._tunnel_src_ip)
            if changed:
                self.stats.source_rewrites += 1
        if self.traffic_shape.jitter_ms_max > 0:
            apply_send_jitter(self.traffic_shape.jitter_ms_max)
        frame = self.client.seal_packet(pkt)
        sock.sendto(frame, self.client.endpoint.address)
        self.stats.tun_to_udp += 1
        return True

    def _read_tun(self, tun: TunIO, wait_ms: int) -> Optional[bytes]:
        try:
            return tun.read_packet(wait_ms=wait_ms)
        except TypeError:
            return tun.read_packet()

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
        try:
            from client.product_policy import product_outer_obfuscation_enabled

            outer_on = bool(product_outer_obfuscation_enabled())
        except Exception:  # noqa: BLE001
            outer_on = bool(product_obfuscation_enabled())
        burst = int(DATAPLANE_BURST)
        while not self._stop.is_set():
            try:
                rlist = [sock]
                fd = tun.fileno()
                if fd >= 0:
                    rlist.append(fd)
                    wait = idle_select_s
                else:
                    # Wintun: do not park here — select cannot see the ring.
                    wait = 0.0
                select.select(rlist, [], [], wait)
            except (ValueError, OSError):
                fd = -1

            udp_n = 0
            while udp_n < burst:
                try:
                    data, _addr = sock.recvfrom(65535)
                except BlockingIOError:
                    break
                except OSError:
                    break
                except Exception:
                    self.stats.errors += 1
                    break
                udp_n += 1
                last_activity = time.time()
                idle_select_s = IDLE_SELECT_MIN_S
                try:
                    self._handle_udp_datagram(tun, data, outer_on=outer_on)
                except Exception:
                    self.stats.errors += 1

            tun_n = 0
            while tun_n < burst:
                try:
                    pkt = self._read_tun(tun, 0)
                    if not pkt:
                        break
                    tun_n += 1
                    if self._handle_tun_packet(sock, pkt):
                        last_activity = time.time()
                        idle_select_s = IDLE_SELECT_MIN_S
                except Exception:
                    self.stats.errors += 1
                    break

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
            if udp_n == 0 and tun_n == 0 and fd < 0:
                # Park only when the Wintun ring and UDP socket were empty.
                # Sleeping every turn (old path) limited Windows to ~20 pkt/s.
                parked = self._read_tun(tun, max(1, int(idle_select_s * 1000)))
                if parked:
                    try:
                        if self._handle_tun_packet(sock, parked):
                            last_activity = time.time()
                            idle_select_s = IDLE_SELECT_MIN_S
                    except Exception:
                        self.stats.errors += 1

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

    def read_packet(self, max_size: int = 65535, wait_ms: int = 0) -> Optional[bytes]:
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
