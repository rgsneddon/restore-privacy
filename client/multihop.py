"""Multi-hop path configuration and residual routing selection.

Product default remains **single hop** to the Iceland entry node. When multi-hop
is **enabled** with ≥2 hops and routing is implemented, residual Connect dials
the **exit** (last) hop so egress residual is the exit VPS; the hop list still
names entry → exit for path honesty.

Node-only zram + LUKS2 applies on multi-hop hosts; clients never run LUKS/zram.

Honesty:
- ``is_multihop_active()`` is True only when routing is implemented **and**
  multi-hop is enabled with ≥2 hops.
- Status never claims multi-hop residual when disabled or when only one hop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .endpoint import DEFAULT_ENDPOINT, PRODUCT_NODE_HOST, PRODUCT_NODE_PORT, Endpoint

# Real residual multi-hop path selection is implemented: when active, Connect
# dials the last hop (exit) for residual tunnel after the path is configured.
MULTI_HOP_ROUTING_IMPLEMENTED = True

# Product exit hop (Romania FlokiNET) — residual multi-hop egress when enabled.
PRODUCT_EXIT_HOST = "185.146.232.107"
PRODUCT_EXIT_PORT = PRODUCT_NODE_PORT


@dataclass(frozen=True)
class Hop:
    """One operator relay hop (config entry)."""

    host: str
    port: int = PRODUCT_NODE_PORT
    role: str = ""  # "entry" | "exit" | ""

    def as_endpoint(self) -> Endpoint:
        return Endpoint(host=self.host, port=int(self.port))

    def label(self) -> str:
        return f"{self.host}:{int(self.port)}"


@dataclass
class MultiHopConfig:
    """Ordered hop list. Empty or disabled ⇒ product single hop (entry)."""

    hops: list[Hop] = field(default_factory=list)
    enabled: bool = False

    def active_hops(self) -> list[Hop]:
        """Configured hop path (entry first when multi-hop enabled)."""
        if not self.enabled:
            return [Hop(PRODUCT_NODE_HOST, PRODUCT_NODE_PORT, role="entry")]
        return build_hop_path(self.hops)


def build_hop_path(hops: Sequence[Hop] | Iterable[Hop] | None) -> list[Hop]:
    """Normalize hop list; default to product single hop when empty."""
    items = list(hops or [])
    cleaned: list[Hop] = []
    for h in items:
        host = (h.host or "").strip()
        if not host:
            continue
        port = int(h.port) if h.port else PRODUCT_NODE_PORT
        if port <= 0 or port > 65535:
            port = PRODUCT_NODE_PORT
        role = (getattr(h, "role", None) or "").strip()
        cleaned.append(Hop(host=host, port=port, role=role))
    if not cleaned:
        return [Hop(PRODUCT_NODE_HOST, PRODUCT_NODE_PORT, role="entry")]
    # Tag entry/exit when ≥2 hops and roles empty
    if len(cleaned) >= 2:
        if not cleaned[0].role:
            cleaned[0] = Hop(cleaned[0].host, cleaned[0].port, role="entry")
        if not cleaned[-1].role:
            cleaned[-1] = Hop(cleaned[-1].host, cleaned[-1].port, role="exit")
    return cleaned


def first_hop_endpoint(config: MultiHopConfig | None = None) -> Endpoint:
    """Entry hop endpoint (path hop 0)."""
    cfg = config or MultiHopConfig()
    hops = cfg.active_hops()
    return hops[0].as_endpoint()


def residual_endpoint(config: MultiHopConfig | None = None) -> Endpoint:
    """Endpoint used for residual TUN / CLIENT_HELLO.

    - Multi-hop **active**: last hop (exit) — residual egress is the exit VPS.
    - Otherwise: first hop / product entry.
    """
    cfg = config or MultiHopConfig()
    hops = build_hop_path(cfg.active_hops())
    if is_multihop_active(cfg) and len(hops) >= 2:
        return hops[-1].as_endpoint()
    return hops[0].as_endpoint()


def hop_path_configured(config: MultiHopConfig | None = None) -> bool:
    """True when operator enabled multi-hop with ≥2 listed hops."""
    cfg = config or MultiHopConfig()
    return bool(cfg.enabled and len(build_hop_path(cfg.hops)) >= 2)


def multihop_status_text(config: MultiHopConfig | None = None) -> str:
    """Honest UI/status for multi-hop."""
    cfg = config or MultiHopConfig()
    if not cfg.enabled:
        return "single-hop (multi-hop inactive)"
    hops = build_hop_path(cfg.hops)
    if len(hops) < 2:
        return "single-hop (multi-hop needs ≥2 configured hops)"
    labels = " → ".join(h.label() for h in hops)
    if not MULTI_HOP_ROUTING_IMPLEMENTED:
        return f"multi-hop path configured (not routed; entry-only): {labels}"
    if is_multihop_active(cfg):
        residual = residual_endpoint(cfg)
        return (
            f"multi-hop active ({len(hops)} hops): {labels} "
            f"(residual via {residual.host}:{residual.port})"
        )
    return f"multi-hop path configured (not active): {labels}"


def is_multihop_active(config: MultiHopConfig | None = None) -> bool:
    """True when routing is implemented and multi-hop path is selected."""
    if not MULTI_HOP_ROUTING_IMPLEMENTED:
        return False
    return hop_path_configured(config)


def parse_hops_csv(text: str) -> list[Hop]:
    """Parse ``host[:port],host2[:port]`` for operator config / env."""
    out: list[Hop] = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            host, _, port_s = part.rpartition(":")
            try:
                port = int(port_s)
            except ValueError:
                host, port = part, PRODUCT_NODE_PORT
        else:
            host, port = part, PRODUCT_NODE_PORT
        if host.strip():
            out.append(Hop(host=host.strip(), port=port))
    return out


def default_single_hop() -> MultiHopConfig:
    return MultiHopConfig(
        hops=[Hop(DEFAULT_ENDPOINT.host, DEFAULT_ENDPOINT.port, role="entry")],
        enabled=False,
    )


def entry_hop() -> Hop:
    """Product entry hop (Iceland / FlokiNET production node)."""
    return Hop(PRODUCT_NODE_HOST, PRODUCT_NODE_PORT, role="entry")


def product_exit_hop() -> Hop:
    """Product exit hop (Romania / FlokiNET) for multi-hop residual."""
    return Hop(PRODUCT_EXIT_HOST, PRODUCT_EXIT_PORT, role="exit")


def build_entry_exit_path(
    exit_host: str,
    *,
    exit_port: int = PRODUCT_NODE_PORT,
    entry_host: str | None = None,
    entry_port: int = PRODUCT_NODE_PORT,
) -> list[Hop]:
    """Ordered path: entry → exit."""
    exit_h = (exit_host or "").strip()
    if not exit_h:
        raise ValueError("exit_host is required for entry→exit path planning")
    entry_h = (entry_host or PRODUCT_NODE_HOST).strip() or PRODUCT_NODE_HOST
    return build_hop_path(
        [
            Hop(entry_h, entry_port, role="entry"),
            Hop(exit_h, exit_port, role="exit"),
        ]
    )


def product_multihop_path() -> list[Hop]:
    """Shipped entry (Iceland) → exit (Romania) path."""
    return build_entry_exit_path(PRODUCT_EXIT_HOST, exit_port=PRODUCT_EXIT_PORT)


def multihop_config_from_env(
    env: dict[str, str] | None = None,
) -> MultiHopConfig:
    """Build MultiHopConfig from operator environment (opt-in).

    - ``RPT_MULTIHOP_ENABLED=1`` — enable multi-hop residual via exit hop
    - ``RPT_MULTIHOP_HOPS`` — CSV ``host[:port],host2[:port]``
    - ``RPT_EXIT_HOST`` / ``RPT_EXIT_PORT`` — second hop (default product exit)
    """
    import os

    e = env if env is not None else os.environ
    enabled = str(e.get("RPT_MULTIHOP_ENABLED", "")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    csv = str(e.get("RPT_MULTIHOP_HOPS", "") or "").strip()
    if csv:
        hops = parse_hops_csv(csv)
    else:
        exit_host = str(e.get("RPT_EXIT_HOST", "") or "").strip()
        if not exit_host and enabled:
            exit_host = PRODUCT_EXIT_HOST
        if exit_host:
            try:
                exit_port = int(str(e.get("RPT_EXIT_PORT", "") or PRODUCT_EXIT_PORT))
            except ValueError:
                exit_port = PRODUCT_EXIT_PORT
            hops = build_entry_exit_path(exit_host, exit_port=exit_port)
        else:
            hops = [entry_hop()]
    return MultiHopConfig(hops=hops, enabled=enabled)


def exit_hop_label(config: MultiHopConfig | None = None) -> str | None:
    """Second hop label when a multi-hop path is configured; else None."""
    cfg = config or MultiHopConfig()
    if not hop_path_configured(cfg):
        return None
    hops = build_hop_path(cfg.hops)
    return hops[1].label() if len(hops) >= 2 else None


def node_pub_name_for_endpoint(endpoint: Endpoint) -> str:
    """Which public key file to load for HELLO to *endpoint*."""
    host = (endpoint.host or "").strip()
    if host == PRODUCT_EXIT_HOST or host == product_exit_hop().host:
        return "exit_node_elgamal.pub"
    return "node_elgamal.pub"
