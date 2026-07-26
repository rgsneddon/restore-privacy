"""Best-effort device→node RTT probes for Settings ping statistics.

Measures approximate latency to the **selected residual entry** (Settings
``entry_country`` — IS / RO / US) and, when multi-hop is on, the complementary
**exit** peer. Residual VPN uses UDP **44044**; this helper prefers a short
UDP probe and falls back to TCP connect RTT on the node status port when UDP
yields no reply. Results are **probe RTT**, not a browser speedbench SLA.
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Optional

from client.endpoint import PRODUCT_NODE_HOST, PRODUCT_NODE_PORT
from client.multihop import (
    PRODUCT_EXIT_HOST,
    PRODUCT_EXIT_PORT,
    country_node_for_code,
    multihop_config_for_entry_country,
    normalize_entry_country,
    residual_endpoint,
)

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


def probe_entry_rtt_ms(
    *,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
    entry_country: str | None = None,
) -> PingResult:
    """Device → selected residual entry node (default United States monopin)."""
    node = country_node_for_code(entry_country)
    return probe_node_rtt_ms(
        node.host or PRODUCT_NODE_HOST,
        udp_port=int(node.port or PRODUCT_NODE_PORT),
        timeout_s=timeout_s,
    )


def probe_exit_rtt_ms(
    *,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
    entry_country: str | None = None,
    multihop_enabled: bool = True,
) -> PingResult:
    """Device → multi-hop residual exit (or alternate peer when multihop on)."""
    cfg = multihop_config_for_entry_country(
        entry_country,
        multihop_enabled=bool(multihop_enabled),
    )
    # residual_endpoint under multihop active is exit; otherwise alternate RO default.
    if bool(multihop_enabled) and cfg.enabled:
        ep = residual_endpoint(cfg)
        host = (ep.host or PRODUCT_EXIT_HOST).strip()
        port = int(ep.port or PRODUCT_EXIT_PORT)
    else:
        host = PRODUCT_EXIT_HOST
        port = PRODUCT_EXIT_PORT
    return probe_node_rtt_ms(host, udp_port=port, timeout_s=timeout_s)


@dataclass(frozen=True)
class SettingsPingSnapshot:
    """UI-facing snapshot for Settings ping statistics."""

    entry: PingResult
    exit: Optional[PingResult]
    multihop_enabled: bool
    measured_at: float
    entry_country: str = "US"
    entry_name: str = "Iceland"
    exit_name: str = "Romania"

    def entry_display(self) -> str:
        return self.entry.display()

    def exit_display(self) -> str:
        if not self.multihop_enabled:
            return "n/a (multi-hop off)"
        if self.exit is None:
            return "n/a"
        return self.exit.display()

    def entry_label(self) -> str:
        code = (self.entry_country or "IS").strip().upper() or "IS"
        name = (self.entry_name or code).strip() or code
        return f"Entry ({name} / {code})"

    def exit_label(self) -> str:
        name = (self.exit_name or "exit").strip() or "exit"
        return f"Exit ({name})"


def measure_settings_pings(
    *,
    multihop_enabled: bool,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
    entry_country: str | None = None,
) -> SettingsPingSnapshot:
    """Probe selected entry always; probe exit when multi-hop is enabled."""
    code = normalize_entry_country(entry_country)
    entry_node = country_node_for_code(code)
    entry = probe_entry_rtt_ms(timeout_s=timeout_s, entry_country=code)
    exit_r: Optional[PingResult] = None
    exit_name = "Romania"
    if multihop_enabled:
        exit_r = probe_exit_rtt_ms(
            timeout_s=timeout_s,
            entry_country=code,
            multihop_enabled=True,
        )
        if exit_r is not None and exit_r.host:
            # Label exit by catalog name when known
            for n in (
                country_node_for_code("IS"),
                country_node_for_code("RO"),
            ):
                if (n.host or "").strip() == (exit_r.host or "").strip():
                    exit_name = n.name
                    break
    return SettingsPingSnapshot(
        entry=entry,
        exit=exit_r,
        multihop_enabled=bool(multihop_enabled),
        measured_at=time.time(),
        entry_country=code,
        entry_name=str(entry_node.name or code),
        exit_name=exit_name,
    )
