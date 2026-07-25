"""Multi-hop path configuration and residual routing selection.

Product default remains **single hop** to the Iceland entry node. When multi-hop
is **enabled** with ≥2 hops and routing is implemented, residual Connect dials
the **exit** (last) hop so egress residual is the exit VPS; the hop list still
names entry → exit for path honesty.

**Preferred-entry downtime failover** (fleet wipe/rebuild): pure selection prefers
the user's **selected entry** when healthy; automatically residual-fails over to
the **other catalog peer** when preferred entry is draining/down; re-prefers
entry when healthy again. Fail closed if neither path is usable. Iceland is not
a fixed sole entry role for all users — peers are residual-capable.

Node-only zram + LUKS2 applies on multi-hop hosts; clients never run LUKS/zram.

Honesty:
- ``is_multihop_active()`` is True only when routing is implemented **and**
  multi-hop is enabled with ≥2 hops.
- Status never claims multi-hop residual when disabled or when only one hop.
- Failover does not invent a third hop; if exit is also unhealthy, selection fails closed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from .endpoint import DEFAULT_ENDPOINT, PRODUCT_NODE_HOST, PRODUCT_NODE_PORT, Endpoint

# Real residual multi-hop path selection is implemented: when active, Connect
# dials the last hop (exit) for residual tunnel after the path is configured.
MULTI_HOP_ROUTING_IMPLEMENTED = True

# Product exit hop (Romania FlokiNET) — residual multi-hop egress when enabled.
PRODUCT_EXIT_HOST = "185.146.232.107"
PRODUCT_EXIT_PORT = PRODUCT_NODE_PORT

# --- Country → node catalog (extensible as more VPS countries ship) ---
COUNTRY_IS = "IS"
COUNTRY_RO = "RO"
DEFAULT_ENTRY_COUNTRY = COUNTRY_IS


@dataclass(frozen=True)
class CountryNode:
    """One residual-capable product node identified by country code."""

    code: str  # ISO-ish short code (IS, RO, …)
    name: str  # User-facing country name
    host: str
    port: int = PRODUCT_NODE_PORT
    pub_name: str = "node_elgamal.pub"  # product public ElGamal file (no priv)

    def as_hop(self, *, role: str = "") -> "Hop":
        return Hop(host=self.host, port=int(self.port), role=role)

    def as_endpoint(self) -> Endpoint:
        return Endpoint(host=self.host, port=int(self.port))


# Shipped two-country catalog (Iceland entry monopin + Romania exit peer).
PRODUCT_COUNTRY_CATALOG: tuple[CountryNode, ...] = (
    CountryNode(
        code=COUNTRY_IS,
        name="Iceland",
        host=PRODUCT_NODE_HOST,
        port=PRODUCT_NODE_PORT,
        pub_name="node_elgamal.pub",
    ),
    CountryNode(
        code=COUNTRY_RO,
        name="Romania",
        host=PRODUCT_EXIT_HOST,
        port=PRODUCT_EXIT_PORT,
        pub_name="exit_node_elgamal.pub",
    ),
)


def product_country_catalog() -> tuple[CountryNode, ...]:
    """Current residual country catalog (extend when new nodes ship)."""
    return PRODUCT_COUNTRY_CATALOG


def normalize_entry_country(code: str | None) -> str:
    """Return a valid catalog country code; unknown/empty → Iceland (default)."""
    raw = (code or "").strip().upper()
    if not raw:
        return DEFAULT_ENTRY_COUNTRY
    # Accept full names
    aliases = {
        "ICELAND": COUNTRY_IS,
        "IS": COUNTRY_IS,
        "ROMANIA": COUNTRY_RO,
        "RO": COUNTRY_RO,
        "ROU": COUNTRY_RO,
    }
    code_n = aliases.get(raw, raw)
    for n in PRODUCT_COUNTRY_CATALOG:
        if n.code == code_n:
            return n.code
    return DEFAULT_ENTRY_COUNTRY


def country_node_for_code(
    code: str | None,
    *,
    catalog: Sequence[CountryNode] | None = None,
) -> CountryNode:
    """Lookup catalog node for *code* (falls back to default Iceland)."""
    cat = tuple(catalog) if catalog is not None else PRODUCT_COUNTRY_CATALOG
    want = normalize_entry_country(code)
    for n in cat:
        if n.code == want:
            return n
    # Catalog without IS — first entry
    return cat[0] if cat else PRODUCT_COUNTRY_CATALOG[0]


def resolve_entry_exit(
    entry_country: str | None,
    *,
    multihop_enabled: bool = False,
    catalog: Sequence[CountryNode] | None = None,
    rng: random.Random | None = None,
) -> tuple[CountryNode, CountryNode | None]:
    """Resolve residual entry (+ optional exit) for user country choice.

    - **Single-hop** (multihop off): entry = selected country; exit = None.
    - **Multi-hop** on: entry = selected country; exit = random among other
      catalog countries (deterministic complement when only one non-entry).
    - Exit is never the same host as entry.
    """
    cat = list(catalog) if catalog is not None else list(PRODUCT_COUNTRY_CATALOG)
    if not cat:
        raise ValueError("country catalog is empty")
    entry = country_node_for_code(entry_country, catalog=cat)
    if not multihop_enabled:
        return entry, None
    candidates = [
        n
        for n in cat
        if n.host.strip() != entry.host.strip() or int(n.port) != int(entry.port)
    ]
    if not candidates:
        # No peer — stay single-hop honest
        return entry, None
    if len(candidates) == 1:
        return entry, candidates[0]
    pick_rng = rng if rng is not None else random.Random()
    exit_n = pick_rng.choice(list(candidates))
    return entry, exit_n


def multihop_config_for_entry_country(
    entry_country: str | None = None,
    *,
    multihop_enabled: bool = False,
    catalog: Sequence[CountryNode] | None = None,
    rng: random.Random | None = None,
) -> "MultiHopConfig":
    """Build :class:`MultiHopConfig` from entry-country preference + multihop flag."""
    entry, exit_n = resolve_entry_exit(
        entry_country,
        multihop_enabled=multihop_enabled,
        catalog=catalog,
        rng=rng,
    )
    if exit_n is None or not multihop_enabled:
        return MultiHopConfig(
            hops=[entry.as_hop(role="entry")],
            enabled=False,
        )
    return MultiHopConfig(
        hops=[
            entry.as_hop(role="entry"),
            exit_n.as_hop(role="exit"),
        ],
        enabled=True,
    )


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
        """Configured hop path (entry first; exit only when multi-hop enabled).

        When disabled, returns **only the configured entry hop** (first hop),
        so user entry-country selection (e.g. Romania) is honoured for
        single-hop residual — not hard-locked to the historical Iceland monopin.
        """
        path = build_hop_path(self.hops)
        if not self.enabled:
            return [path[0]] if path else [Hop(PRODUCT_NODE_HOST, PRODUCT_NODE_PORT, role="entry")]
        return path


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


# Near-capacity residual migration (connection load hints; not multi-VPS consensus).
# Utilization is 0.0 (idle) … 1.0 (full). Prefer freer peer when preferred is high.
DEFAULT_NEAR_CAPACITY_THRESHOLD = 0.85
# Alternate must be at least this much freer (lower util) to trigger migration.
DEFAULT_CAPACITY_MARGIN = 0.05
REASON_CAPACITY_MIGRATION = "capacity_migration"


@dataclass(frozen=True)
class ResidualSelection:
    """Result of entry-primary / exit-failover residual preference."""

    endpoint: Endpoint
    reason: str  # entry_primary | exit_failover | multihop_residual_via_exit | entry_fallback | capacity_migration
    entry_healthy: bool
    exit_healthy: bool
    entry_draining: bool
    failover_active: bool
    preferred_host: str = ""
    capacity_util_preferred: float | None = None
    capacity_util_selected: float | None = None

    def to_dict(self) -> dict:
        return {
            "host": self.endpoint.host,
            "port": self.endpoint.port,
            "reason": self.reason,
            "entry_healthy": self.entry_healthy,
            "exit_healthy": self.exit_healthy,
            "entry_draining": self.entry_draining,
            "failover_active": self.failover_active,
            "preferred_host": self.preferred_host,
            "capacity_util_preferred": self.capacity_util_preferred,
            "capacity_util_selected": self.capacity_util_selected,
        }


def normalize_peer_capacity(
    peer_capacity: dict[str, float] | None,
) -> dict[str, float]:
    """Normalize host → utilization map (0.0–1.0); drop empty hosts."""
    if not peer_capacity:
        return {}
    out: dict[str, float] = {}
    for host, util in peer_capacity.items():
        h = (host or "").strip()
        if not h:
            continue
        try:
            u = float(util)
        except (TypeError, ValueError):
            continue
        if u < 0.0:
            u = 0.0
        if u > 1.0:
            u = 1.0
        out[h] = u
    return out


def peer_utilization(
    host: str,
    peer_capacity: dict[str, float] | None,
) -> float | None:
    """Return utilization for *host* if known, else None (no signal)."""
    caps = normalize_peer_capacity(peer_capacity)
    h = (host or "").strip()
    if not h:
        return None
    if h in caps:
        return caps[h]
    return None


def is_near_capacity(
    util: float | None,
    *,
    threshold: float = DEFAULT_NEAR_CAPACITY_THRESHOLD,
) -> bool:
    """True when utilization is known and at/above near-capacity threshold.

    Missing capacity signal → False (do not migrate without evidence).
    """
    if util is None:
        return False
    try:
        t = float(threshold)
    except (TypeError, ValueError):
        t = DEFAULT_NEAR_CAPACITY_THRESHOLD
    if t < 0.0:
        t = 0.0
    if t > 1.0:
        t = 1.0
    return float(util) >= t


def is_freer_capacity(
    candidate_util: float | None,
    preferred_util: float | None,
    *,
    margin: float = DEFAULT_CAPACITY_MARGIN,
) -> bool:
    """True when *candidate* has meaningfully more free capacity than preferred.

    Both must be known; candidate utilization must be lower by at least *margin*.
    """
    if candidate_util is None or preferred_util is None:
        return False
    try:
        m = float(margin)
    except (TypeError, ValueError):
        m = DEFAULT_CAPACITY_MARGIN
    if m < 0.0:
        m = 0.0
    return float(candidate_util) <= float(preferred_util) - m


def capacity_migration_advisory(selection: ResidualSelection | None) -> str | None:
    """Human-readable CLI/status line when residual pick was capacity-driven.

    Returns None for ordinary entry-primary / multihop / health failover reasons
    so non-capacity residual paths stay silent about capacity.
    """
    if selection is None:
        return None
    if selection.reason != REASON_CAPACITY_MIGRATION:
        return None
    pref = (selection.preferred_host or "").strip() or "preferred residual"
    host = selection.endpoint.host
    port = selection.endpoint.port
    util_p = selection.capacity_util_preferred
    util_s = selection.capacity_util_selected
    util_bits = ""
    if util_p is not None and util_s is not None:
        util_bits = (
            f" (preferred ~{int(round(util_p * 100))}% load → "
            f"peer ~{int(round(util_s * 100))}%)"
        )
    return (
        f"Notice: preferred residual node ({pref}) was near connection capacity; "
        f"automatically moved you to freer peer {host}:{port}{util_bits}."
    )


def entry_endpoint(config: MultiHopConfig | None = None) -> Endpoint:
    """Preferred residual entry (user country selection / first hop)."""
    return first_hop_endpoint(config)


def alternate_peer_endpoint(config: MultiHopConfig | None = None) -> Endpoint:
    """Failover residual peer — **never** the same host as preferred entry.

    - Multi-hop path configured: last hop when it differs from entry.
    - Else first catalog peer whose host ≠ entry (IS↔RO when two peers).
    - Never falls back to PRODUCT_EXIT_HOST when entry is already Romania.
    """
    cfg = config or MultiHopConfig()
    entry_ep = entry_endpoint(cfg)
    entry_host = (entry_ep.host or "").strip()
    if hop_path_configured(cfg):
        hops = build_hop_path(cfg.hops)
        if len(hops) >= 2:
            alt = hops[-1].as_endpoint()
            if (alt.host or "").strip() != entry_host:
                return alt
    for n in PRODUCT_COUNTRY_CATALOG:
        if (n.host or "").strip() != entry_host:
            return n.as_endpoint()
    # Single-node catalog edge: cannot invent a peer
    if entry_host == PRODUCT_EXIT_HOST:
        return Endpoint(host=PRODUCT_NODE_HOST, port=PRODUCT_NODE_PORT)
    return Endpoint(host=PRODUCT_EXIT_HOST, port=PRODUCT_EXIT_PORT)


def exit_endpoint(config: MultiHopConfig | None = None) -> Endpoint:
    """Multihop residual exit hop, or alternate catalog peer for failover.

    When multi-hop is configured (≥2 hops), returns the last hop (residual-via-exit).
    When single-hop, returns :func:`alternate_peer_endpoint` so a preferred entry
    of Romania does **not** failover to Romania again.
    """
    cfg = config or MultiHopConfig()
    if hop_path_configured(cfg):
        hops = build_hop_path(cfg.hops)
        last = hops[-1].as_endpoint()
        entry = hops[0].as_endpoint()
        if (last.host or "").strip() != (entry.host or "").strip():
            return last
    return alternate_peer_endpoint(cfg)


def _maybe_capacity_migrate(
    *,
    preferred: Endpoint,
    alternate: Endpoint,
    preferred_healthy: bool,
    alternate_healthy: bool,
    peer_capacity: dict[str, float] | None,
    near_capacity_threshold: float,
    capacity_margin: float,
    entry_healthy: bool,
    exit_healthy: bool,
    entry_draining: bool,
) -> ResidualSelection | None:
    """If preferred residual is near capacity and alternate is freer, migrate.

    Returns a capacity_migration selection, or None to keep the non-capacity pick.
    Never migrates to the same host. No freer peer → None (keep preferred; do not
    black-hole solely because preferred is busy).
    """
    if not preferred_healthy or not alternate_healthy:
        return None
    pref_host = (preferred.host or "").strip()
    alt_host = (alternate.host or "").strip()
    if not pref_host or not alt_host or pref_host == alt_host:
        return None
    util_p = peer_utilization(pref_host, peer_capacity)
    util_a = peer_utilization(alt_host, peer_capacity)
    if not is_near_capacity(util_p, threshold=near_capacity_threshold):
        return None
    if not is_freer_capacity(util_a, util_p, margin=capacity_margin):
        return None
    return ResidualSelection(
        endpoint=alternate,
        reason=REASON_CAPACITY_MIGRATION,
        entry_healthy=bool(entry_healthy),
        exit_healthy=bool(exit_healthy),
        entry_draining=bool(entry_draining),
        failover_active=True,
        preferred_host=pref_host,
        capacity_util_preferred=util_p,
        capacity_util_selected=util_a,
    )


def select_residual_endpoint(
    config: MultiHopConfig | None = None,
    *,
    entry_healthy: bool = True,
    exit_healthy: bool = True,
    entry_draining: bool = False,
    peer_capacity: dict[str, float] | None = None,
    near_capacity_threshold: float = DEFAULT_NEAR_CAPACITY_THRESHOLD,
    capacity_margin: float = DEFAULT_CAPACITY_MARGIN,
) -> ResidualSelection:
    """Prefer selected entry when healthy; failover to alternate catalog peer.

    Rules (pure, unit-testable):
    1. Entry healthy and not draining → **entry-primary** residual.
    2. Entry unhealthy or draining, peer healthy → **exit_failover** to alternate peer
       (never same host as preferred entry).
    3. Multi-hop active + entry healthy: residual-via-exit dials configured exit.
    4. When the preferred residual host is **near connection capacity** and a
       healthy alternate is meaningfully freer → **capacity_migration** (never
       same host). Missing capacity signal does not migrate. No freer peer →
       keep preferred (do not invent a hop / black-hole solely for load).
    5. Both unusable → raise :class:`ResidualUnavailable` (fail closed).

    Fleet wipe sets preferred-entry draining so clients flip to a healthy peer.
    Capacity hints are injectable (host → utilization 0..1); production may
    supply probe results later without changing this pure ranking.
    """
    cfg = config or MultiHopConfig()
    entry_ok = bool(entry_healthy) and not bool(entry_draining)
    exit_ok = bool(exit_healthy)
    entry_ep = entry_endpoint(cfg)
    exit_ep = exit_endpoint(cfg)
    # Never treat same-host as a real failover peer
    if (exit_ep.host or "").strip() == (entry_ep.host or "").strip():
        exit_ep = alternate_peer_endpoint(cfg)
        if (exit_ep.host or "").strip() == (entry_ep.host or "").strip():
            exit_ok = False

    # Intentional multi-hop residual-via-exit when entry is up (product path).
    if is_multihop_active(cfg) and entry_ok:
        if exit_ok:
            residual = residual_endpoint(cfg)
            # Capacity: if exit residual is near full, migrate to freer entry peer
            migrated = _maybe_capacity_migrate(
                preferred=residual,
                alternate=entry_ep,
                preferred_healthy=True,
                alternate_healthy=True,
                peer_capacity=peer_capacity,
                near_capacity_threshold=near_capacity_threshold,
                capacity_margin=capacity_margin,
                entry_healthy=True,
                exit_healthy=True,
                entry_draining=bool(entry_draining),
            )
            if migrated is not None:
                return migrated
            return ResidualSelection(
                endpoint=residual,
                reason="multihop_residual_via_exit",
                entry_healthy=True,
                exit_healthy=True,
                entry_draining=bool(entry_draining),
                failover_active=False,
                preferred_host=(residual.host or "").strip(),
            )
        # Multihop wants exit but exit down — fall back to entry if still up
        return ResidualSelection(
            endpoint=entry_ep,
            reason="entry_fallback",
            entry_healthy=True,
            exit_healthy=False,
            entry_draining=bool(entry_draining),
            failover_active=False,
            preferred_host=(entry_ep.host or "").strip(),
        )

    # Entry-primary (single-hop default and post-rebuild re-entry)
    if entry_ok:
        migrated = _maybe_capacity_migrate(
            preferred=entry_ep,
            alternate=exit_ep,
            preferred_healthy=True,
            alternate_healthy=exit_ok,
            peer_capacity=peer_capacity,
            near_capacity_threshold=near_capacity_threshold,
            capacity_margin=capacity_margin,
            entry_healthy=True,
            exit_healthy=exit_ok,
            entry_draining=False,
        )
        if migrated is not None:
            return migrated
        return ResidualSelection(
            endpoint=entry_ep,
            reason="entry_primary",
            entry_healthy=True,
            exit_healthy=exit_ok,
            entry_draining=False,
            failover_active=False,
            preferred_host=(entry_ep.host or "").strip(),
        )

    # Preferred entry down/draining → solid peer failover (other catalog host)
    if exit_ok and (exit_ep.host or "").strip() != (entry_ep.host or "").strip():
        return ResidualSelection(
            endpoint=exit_ep,
            reason="exit_failover",
            entry_healthy=bool(entry_healthy),
            exit_healthy=True,
            entry_draining=bool(entry_draining),
            failover_active=True,
            preferred_host=(entry_ep.host or "").strip(),
        )

    raise ResidualUnavailable(
        "fail closed: preferred entry unavailable (down/draining) and no healthy "
        "alternate catalog peer — no residual path; do not invent a third hop"
    )


def residual_try_order(
    config: MultiHopConfig | None = None,
    *,
    entry_healthy: bool = True,
    exit_healthy: bool = True,
    entry_draining: bool = False,
    peer_capacity: dict[str, float] | None = None,
    near_capacity_threshold: float = DEFAULT_NEAR_CAPACITY_THRESHOLD,
    capacity_margin: float = DEFAULT_CAPACITY_MARGIN,
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
            peer_capacity=peer_capacity,
            near_capacity_threshold=near_capacity_threshold,
            capacity_margin=capacity_margin,
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
    - ``RPT_ENTRY_COUNTRY`` / Settings ``entry_country`` — IS or RO (default IS)
    - ``RPT_MULTIHOP_HOPS`` — CSV ``host[:port],host2[:port]`` (operator override)
    - ``RPT_EXIT_HOST`` / ``RPT_EXIT_PORT`` — second hop override (legacy)
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

    # Entry country: env wins, else product Settings (default Iceland)
    entry_country = str(e.get("RPT_ENTRY_COUNTRY", "") or "").strip()
    if not entry_country and env is None:
        try:
            from client.windows.settings_store import load_settings

            entry_country = getattr(load_settings(), "entry_country", DEFAULT_ENTRY_COUNTRY)
        except Exception:  # noqa: BLE001
            entry_country = DEFAULT_ENTRY_COUNTRY
    if not entry_country:
        entry_country = DEFAULT_ENTRY_COUNTRY

    csv = str(e.get("RPT_MULTIHOP_HOPS", "") or "").strip()
    if csv:
        hops = parse_hops_csv(csv)
        return MultiHopConfig(hops=hops, enabled=enabled)

    # Legacy RPT_EXIT_HOST with fixed Iceland entry only when env forces exit host
    # without country selection (operator override).
    exit_host_env = str(e.get("RPT_EXIT_HOST", "") or "").strip()
    if exit_host_env and "RPT_ENTRY_COUNTRY" not in e and env is not None:
        try:
            exit_port = int(str(e.get("RPT_EXIT_PORT", "") or PRODUCT_EXIT_PORT))
        except ValueError:
            exit_port = PRODUCT_EXIT_PORT
        hops = build_entry_exit_path(exit_host_env, exit_port=exit_port)
        return MultiHopConfig(hops=hops, enabled=enabled)

    # User path: entry country + multihop → complement/random non-entry exit
    return multihop_config_for_entry_country(
        entry_country,
        multihop_enabled=enabled,
    )


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
    for n in PRODUCT_COUNTRY_CATALOG:
        if host == n.host.strip():
            return n.pub_name
    if host == PRODUCT_EXIT_HOST or host == product_exit_hop().host:
        return "exit_node_elgamal.pub"
    return "node_elgamal.pub"
