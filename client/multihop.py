"""Optional multi-hop path selection (privacy: default remains single hop).

Multi-hop is **opt-in**. Status strings stay honest: inactive multi-hop never
claims multi-hop residual protection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .endpoint import DEFAULT_ENDPOINT, PRODUCT_NODE_HOST, PRODUCT_NODE_PORT, Endpoint


@dataclass(frozen=True)
class Hop:
    """One operator relay hop."""

    host: str
    port: int = PRODUCT_NODE_PORT

    def as_endpoint(self) -> Endpoint:
        return Endpoint(host=self.host, port=int(self.port))

    def label(self) -> str:
        return f"{self.host}:{int(self.port)}"


@dataclass
class MultiHopConfig:
    """Ordered hop list. Empty or one hop ⇒ single-hop product path."""

    hops: list[Hop] = field(default_factory=list)
    # When False, ignore hops beyond the first even if listed.
    enabled: bool = False

    def active_hops(self) -> list[Hop]:
        if not self.enabled:
            return [Hop(PRODUCT_NODE_HOST, PRODUCT_NODE_PORT)]
        built = build_hop_path(self.hops)
        return built


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
        cleaned.append(Hop(host=host, port=port))
    if not cleaned:
        return [Hop(PRODUCT_NODE_HOST, PRODUCT_NODE_PORT)]
    return cleaned


def first_hop_endpoint(config: MultiHopConfig | None = None) -> Endpoint:
    """Endpoint used for the initial CLIENT_HELLO (entry hop)."""
    cfg = config or MultiHopConfig()
    hops = cfg.active_hops()
    return hops[0].as_endpoint()


def multihop_status_text(config: MultiHopConfig | None = None) -> str:
    """Honest UI/status string — never claims multi-hop when inactive."""
    cfg = config or MultiHopConfig()
    if not cfg.enabled:
        return "single-hop (multi-hop inactive)"
    hops = build_hop_path(cfg.hops)
    if len(hops) < 2:
        return "single-hop (multi-hop needs ≥2 configured hops)"
    labels = " → ".join(h.label() for h in hops)
    return f"multi-hop active ({len(hops)} hops): {labels}"


def is_multihop_active(config: MultiHopConfig | None = None) -> bool:
    cfg = config or MultiHopConfig()
    return bool(cfg.enabled and len(build_hop_path(cfg.hops)) >= 2)


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
        hops=[Hop(DEFAULT_ENDPOINT.host, DEFAULT_ENDPOINT.port)],
        enabled=False,
    )
