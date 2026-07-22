"""Multi-hop path configuration and residual routing selection.

Product default remains **single hop** to the Iceland entry node. When multi-hop
is **enabled** with ≥2 hops and routing is implemented, residual Connect dials
the **exit** (last) hop so egress residual is the exit VPS; the hop list still
names entry → exit for path honesty.

**Entry downtime failover** (weekly wipe/rebuild): pure selection prefers
**entry** when healthy; automatically residual-fails over to **exit** when entry
is draining/down; re-prefers entry when healthy again. Fail closed if neither
path is usable.

Node-only zram + LUKS2 applies on multi-hop hosts; clients never run LUKS/zram.

Honesty:
- ``is_multihop_active()`` is True only when routing is implemented **and**
  multi-hop is enabled with ≥2 hops.
- Status never claims multi-hop residual when disabled or when only one hop.
- Failover does not invent a third hop; if exit is also unhealthy, selection fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

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

    For entry-drain / health-aware selection (weekly wipe failover), use
    :func:`select_residual_endpoint` instead.
    """
    cfg = config or MultiHopConfig()
    hops = build_hop_path(cfg.active_hops())
    if is_multihop_active(cfg) and len(hops) >= 2:
        return hops[-1].as_endpoint()
    return hops[0].as_endpoint()


class ResidualUnavailable(Exception):
    """Neither entry nor exit residual is usable (fail closed)."""


@dataclass(frozen=True)
class ResidualSelection:
    """Result of entry-primary / exit-failover residual preference."""

    endpoint: Endpoint
    reason: str  # entry_primary | exit_failover | multihop_residual_via_exit | entry_fallback
    entry_healthy: bool
    exit_healthy: bool
    entry_draining: bool
    failover_active: bool

    def to_dict(self) -> dict:
        return {
            "host": self.endpoint.host,
            "port": self.endpoint.port,
            "reason": self.reason,
            "entry_healthy": self.entry_healthy,
            "exit_healthy": self.exit_healthy,
            "entry_draining": self.entry_draining,
            "failover_active": self.failover_active,
        }


def entry_endpoint(config: MultiHopConfig | None = None) -> Endpoint:
    """Entry hop endpoint (product Iceland when default)."""
    return first_hop_endpoint(config)


def exit_endpoint(config: MultiHopConfig | None = None) -> Endpoint:
    """Exit hop when multi-hop path configured; else product exit constant."""
    cfg = config or MultiHopConfig()
    if hop_path_configured(cfg):
        hops = build_hop_path(cfg.hops)
        return hops[-1].as_endpoint()
    return Endpoint(host=PRODUCT_EXIT_HOST, port=PRODUCT_EXIT_PORT)


def select_residual_endpoint(
    config: MultiHopConfig | None = None,
    *,
    entry_healthy: bool = True,
    exit_healthy: bool = True,
    entry_draining: bool = False,
) -> ResidualSelection:
    """Prefer entry when healthy; automatic exit failover when entry down/draining.

    Rules (pure, unit-testable):
    1. Entry healthy and not draining → **entry-primary** residual (re-entry after rebuild).
    2. Entry unhealthy or draining, exit healthy → **exit failover** residual.
    3. Multi-hop active + entry healthy: product residual-via-exit still dials exit
       for intentional multi-hop egress (not a wipe failover).
    4. Both unusable → raise :class:`ResidualUnavailable` (fail closed).

    Weekly entry wipe sets ``entry_draining=True`` so clients flip to exit without
    a manual user step; when entry recovers, pass ``entry_healthy=True`` /
    ``entry_draining=False`` so preference returns to entry.
    """
    cfg = config or MultiHopConfig()
    entry_ok = bool(entry_healthy) and not bool(entry_draining)
    exit_ok = bool(exit_healthy)
    entry_ep = entry_endpoint(cfg)
    exit_ep = exit_endpoint(cfg)

    # Intentional multi-hop residual-via-exit when entry is up (product path).
    if is_multihop_active(cfg) and entry_ok:
        if exit_ok:
            return ResidualSelection(
                endpoint=residual_endpoint(cfg),
                reason="multihop_residual_via_exit",
                entry_healthy=True,
                exit_healthy=True,
                entry_draining=bool(entry_draining),
                failover_active=False,
            )
        # Multihop wants exit but exit down — fall back to entry if still up
        return ResidualSelection(
            endpoint=entry_ep,
            reason="entry_fallback",
            entry_healthy=True,
            exit_healthy=False,
            entry_draining=bool(entry_draining),
            failover_active=False,
        )

    # Entry-primary (single-hop default and post-rebuild re-entry)
    if entry_ok:
        return ResidualSelection(
            endpoint=entry_ep,
            reason="entry_primary",
            entry_healthy=True,
            exit_healthy=exit_ok,
            entry_draining=False,
            failover_active=False,
        )

    # Entry down/draining → solid exit failover
    if exit_ok:
        return ResidualSelection(
            endpoint=exit_ep,
            reason="exit_failover",
            entry_healthy=bool(entry_healthy),
            exit_healthy=True,
            entry_draining=bool(entry_draining),
            failover_active=True,
        )

    raise ResidualUnavailable(
        "fail closed: entry unavailable (down/draining) and exit unhealthy — "
        "no residual path; do not invent a third hop"
    )


def residual_try_order(
    config: MultiHopConfig | None = None,
    *,
    entry_healthy: bool = True,
    exit_healthy: bool = True,
    entry_draining: bool = False,
) -> list[Endpoint]:
    """Ordered residual dial targets for HELLO failover (unique endpoints).

    Preferred first; alternate hop second when available so connect can try
    exit if entry HELLO fails (and re-prefer entry when entry is healthy).
    """
    cfg = config or MultiHopConfig()
    try:
        primary = select_residual_endpoint(
            cfg,
            entry_healthy=entry_healthy,
            exit_healthy=exit_healthy,
            entry_draining=entry_draining,
        ).endpoint
    except ResidualUnavailable:
        return []

    order: list[Endpoint] = [primary]
    entry_ep = entry_endpoint(cfg)
    exit_ep = exit_endpoint(cfg)
    # Always allow try of the other hop when it is believed healthy
    for alt, ok in ((exit_ep, exit_healthy), (entry_ep, entry_healthy and not entry_draining)):
        if not ok:
            continue
        if any(a.host == alt.host and a.port == alt.port for a in order):
            continue
        order.append(alt)
    return order


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
    """Build MultiHopConfig from operator environment and/or user Settings.

    - ``RPT_MULTIHOP_ENABLED=1`` — enable multi-hop residual via exit hop
      (when this env key is set it wins over Settings)
    - When env key is unset, product Settings ``privacy_multihop`` is used
      (default **off** / single-hop residual baseline)
    - ``RPT_MULTIHOP_HOPS`` — CSV ``host[:port],host2[:port]``
    - ``RPT_EXIT_HOST`` / ``RPT_EXIT_PORT`` — second hop (default product exit)
    """
    import os

    e = env if env is not None else os.environ
    if "RPT_MULTIHOP_ENABLED" in e and str(e.get("RPT_MULTIHOP_ENABLED", "")).strip() != "":
        enabled = str(e.get("RPT_MULTIHOP_ENABLED", "")).strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    elif env is not None:
        # Explicit env dict without key → treat as operator off (tests)
        enabled = False
    else:
        try:
            from client.product_policy import product_multihop_enabled

            enabled = bool(product_multihop_enabled())
        except Exception:  # noqa: BLE001
            enabled = False
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
