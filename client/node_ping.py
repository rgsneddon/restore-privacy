"""Best-effort device→node RTT probes for Settings ping statistics.

Measures approximate latency to product **entry** (Iceland) and **exit**
(Romania) hosts. Residual VPN uses UDP **44044**; this helper prefers a short
UDP probe and falls back to TCP connect RTT on the node status port when UDP
yields no reply. Results are **probe RTT**, not a browser speedbench SLA.
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Optional

from client.endpoint import PRODUCT_NODE_HOST, PRODUCT_NODE_PORT
from client.multihop import PRODUCT_EXIT_HOST, PRODUCT_EXIT_PORT

# Node status UI often listens on TCP 8080 — used only as reachability RTT fallback.
STATUS_TCP_PORT = 8080

DEFAULT_PROBE_TIMEOUT_S = 1.5


@dataclass(frozen=True)
class PingResult:
    """One probe outcome."""

    host: str
    port: int
    ok: bool
    rtt_ms: Optional[float]
    method: str  # "udp" | "tcp" | "none"
    error: str = ""

    def display(self) -> str:
        if self.ok and self.rtt_ms is not None:
            return f"{self.rtt_ms:.0f} ms"
        if self.error:
            return f"n/a ({self.error[:40]})"
        return "n/a"


def probe_udp_rtt_ms(
    host: str,
    port: int = PRODUCT_NODE_PORT,
    *,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
) -> PingResult:
    """Send one UDP datagram and wait for any reply (or timeout).

    True residual HELLO needs crypto; this only measures path responsiveness.
    """
    h = (host or "").strip()
    if not h:
        return PingResult(host="", port=port, ok=False, rtt_ms=None, method="none", error="no_host")
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(float(timeout_s))
        # Minimal non-RPT payload — node may ignore; any ICMP/closed is OS-dependent
        payload = b"\x00RPT-PING\x00"
        t0 = time.perf_counter()
        sock.sendto(payload, (h, int(port)))
        try:
            sock.recvfrom(2048)
            rtt = (time.perf_counter() - t0) * 1000.0
            return PingResult(host=h, port=int(port), ok=True, rtt_ms=rtt, method="udp")
        except socket.timeout:
            # No UDP reply — still report send completed (not a positive RTT)
            return PingResult(
                host=h,
                port=int(port),
                ok=False,
                rtt_ms=None,
                method="udp",
                error="udp_timeout",
            )
    except OSError as exc:
        return PingResult(
            host=h,
            port=int(port),
            ok=False,
            rtt_ms=None,
            method="udp",
            error=str(exc)[:80],
        )
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def probe_tcp_rtt_ms(
    host: str,
    port: int = STATUS_TCP_PORT,
    *,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
) -> PingResult:
    """TCP connect RTT to host:port (status port fallback when UDP silent)."""
    h = (host or "").strip()
    if not h:
        return PingResult(host="", port=port, ok=False, rtt_ms=None, method="none", error="no_host")
    try:
        t0 = time.perf_counter()
        with socket.create_connection((h, int(port)), timeout=float(timeout_s)):
            rtt = (time.perf_counter() - t0) * 1000.0
        return PingResult(host=h, port=int(port), ok=True, rtt_ms=rtt, method="tcp")
    except OSError as exc:
        return PingResult(
            host=h,
            port=int(port),
            ok=False,
            rtt_ms=None,
            method="tcp",
            error=str(exc)[:80],
        )


def probe_node_rtt_ms(
    host: str,
    *,
    udp_port: int = PRODUCT_NODE_PORT,
    tcp_port: int = STATUS_TCP_PORT,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
) -> PingResult:
    """Best-effort RTT: prefer UDP residual port, else TCP status port."""
    udp = probe_udp_rtt_ms(host, udp_port, timeout_s=timeout_s)
    if udp.ok:
        return udp
    tcp = probe_tcp_rtt_ms(host, tcp_port, timeout_s=timeout_s)
    if tcp.ok:
        return tcp
    # Prefer the more informative error
    err = tcp.error or udp.error or "unreachable"
    return PingResult(
        host=host,
        port=udp_port,
        ok=False,
        rtt_ms=None,
        method="none",
        error=err,
    )


def probe_entry_rtt_ms(*, timeout_s: float = DEFAULT_PROBE_TIMEOUT_S) -> PingResult:
    """Device → product entry node (Iceland monopin)."""
    return probe_node_rtt_ms(
        PRODUCT_NODE_HOST,
        udp_port=PRODUCT_NODE_PORT,
        timeout_s=timeout_s,
    )


def probe_exit_rtt_ms(*, timeout_s: float = DEFAULT_PROBE_TIMEOUT_S) -> PingResult:
    """Device → product exit node (Romania monopin; multi-hop residual)."""
    return probe_node_rtt_ms(
        PRODUCT_EXIT_HOST,
        udp_port=PRODUCT_EXIT_PORT,
        timeout_s=timeout_s,
    )


@dataclass(frozen=True)
class SettingsPingSnapshot:
    """UI-facing snapshot for Settings ping statistics."""

    entry: PingResult
    exit: Optional[PingResult]
    multihop_enabled: bool
    measured_at: float

    def entry_display(self) -> str:
        return self.entry.display()

    def exit_display(self) -> str:
        if not self.multihop_enabled:
            return "n/a (multi-hop off)"
        if self.exit is None:
            return "n/a"
        return self.exit.display()


def measure_settings_pings(
    *,
    multihop_enabled: bool,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
) -> SettingsPingSnapshot:
    """Probe entry always; probe exit when multi-hop is enabled in Settings."""
    entry = probe_entry_rtt_ms(timeout_s=timeout_s)
    exit_r: Optional[PingResult] = None
    if multihop_enabled:
        exit_r = probe_exit_rtt_ms(timeout_s=timeout_s)
    return SettingsPingSnapshot(
        entry=entry,
        exit=exit_r,
        multihop_enabled=bool(multihop_enabled),
        measured_at=time.time(),
    )
