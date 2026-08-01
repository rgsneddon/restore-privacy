"""Multi-hop path configuration and residual routing selection.

Product default is **single hop** to the **Germany (DE)** residual entry.
When multi-hop is **enabled** with ≥2 hops and routing is implemented, residual
Connect dials the **exit** (last) hop so egress residual is the exit VPS; the
hop list still names entry → exit for path honesty.

**Preferred-entry downtime failover** (fleet wipe/rebuild): pure selection prefers
the user's **selected entry** when healthy; automatically residual-fails over to
the **other catalog peer** when preferred entry is draining/down; re-prefers
entry when healthy again. Fail closed if neither path is usable. Live catalog
peers are **Iceland (IS)** and **Germany (DE)** only.

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

# Product exit hop (Germany DE) — residual multi-hop egress when enabled.
PRODUCT_EXIT_HOST = "178.105.187.178"
PRODUCT_EXIT_PORT = PRODUCT_NODE_PORT

# Retired USA residual peer (Hetzner Ashburn) — redaction only; not dialable.
PRODUCT_US_HOST = "5.161.242.85"
PRODUCT_US_PORT = PRODUCT_NODE_PORT

# Germany residual peer (Hetzner DE dedicated) — product default residual entry.
PRODUCT_DE_HOST = "178.105.187.178"
PRODUCT_DE_PORT = PRODUCT_NODE_PORT

# --- Country → node catalog (extensible as more VPS countries ship) ---
COUNTRY_IS = "IS"
COUNTRY_US = "US"  # retired code — normalize maps US → DE
COUNTRY_DE = "DE"
# Historical Romania monopin (removed) — normalize maps RO → product default DE.
COUNTRY_RO = "RO"
# Product default residual entry (empty prefs / fresh install) — Germany monopin.
DEFAULT_ENTRY_COUNTRY = COUNTRY_DE

# Retired monopin hosts (redaction only — not dialable catalog peers).
PRODUCT_RO_HOST = "185.146.232.107"  # former Romania FlokiNET
PRODUCT_DE_LEGACY_HOST = "167.233.224.5"  # former retired DE monopin
# PRODUCT_US_HOST above is also retired (not in live catalog).


@dataclass(frozen=True)
class CountryNode:
    """One residual-capable product node identified by country code."""

    code: str  # ISO-ish short code (IS, DE, US, …)
    name: str  # User-facing country name
    host: str
    port: int = PRODUCT_NODE_PORT
    pub_name: str = "node_elgamal.pub"  # product public ElGamal file (no priv)

    def as_hop(self, *, role: str = "") -> "Hop":
        return Hop(host=self.host, port=int(self.port), role=role)

    def as_endpoint(self) -> Endpoint:
        return Endpoint(host=self.host, port=int(self.port))


# Shipped residual catalog: Iceland + Germany only (US and RO peers retired).
PRODUCT_COUNTRY_CATALOG: tuple[CountryNode, ...] = (
    CountryNode(
        code=COUNTRY_IS,
        name="Iceland",
        host=PRODUCT_NODE_HOST,
        port=PRODUCT_NODE_PORT,
        pub_name="node_elgamal.pub",
    ),
    CountryNode(
        code=COUNTRY_DE,
        name="Germany",
        host=PRODUCT_DE_HOST,
        port=PRODUCT_DE_PORT,
        pub_name="de_node_elgamal.pub",
    ),
)


def product_country_catalog() -> tuple[CountryNode, ...]:
    """Current residual country catalog (extend when new nodes ship)."""
    return PRODUCT_COUNTRY_CATALOG


def normalize_entry_country(code: str | None) -> str:
    """Return a valid catalog country code; unknown/empty/stale RO/US → DE default."""
    raw = (code or "").strip().upper()
    if not raw:
        return DEFAULT_ENTRY_COUNTRY
    # Accept full names; retired RO/US map to product default DE.
    aliases = {
        "ICELAND": COUNTRY_IS,
        "IS": COUNTRY_IS,
        "GERMANY": COUNTRY_DE,
        "DE": COUNTRY_DE,
        "DEU": COUNTRY_DE,
        "DEUTSCHLAND": COUNTRY_DE,
        # Stale prefs after US peer removal → product default DE
        "UNITED STATES": DEFAULT_ENTRY_COUNTRY,
        "UNITED STATES OF AMERICA": DEFAULT_ENTRY_COUNTRY,
        "USA": DEFAULT_ENTRY_COUNTRY,
        "US": DEFAULT_ENTRY_COUNTRY,
        "AMERICA": DEFAULT_ENTRY_COUNTRY,
        # Stale prefs after RO peer removal → product default DE
        "ROMANIA": DEFAULT_ENTRY_COUNTRY,
        "RO": DEFAULT_ENTRY_COUNTRY,
        "ROU": DEFAULT_ENTRY_COUNTRY,
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
    """Lookup catalog node for *code* (falls back to product default IS)."""
    cat = tuple(catalog) if catalog is not None else PRODUCT_COUNTRY_CATALOG
    want = normalize_entry_country(code)
    for n in cat:
        if n.code == want:
            return n
    # Prefer default IS in catalog, else first entry
    for n in cat:
        if n.code == DEFAULT_ENTRY_COUNTRY:
            return n
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


# Hop roles: public catalog residual uses entry/exit only. rpOS flyclient
# participation uses role=hidden (never listed as public dial targets).
ROLE_ENTRY = "entry"
ROLE_EXIT = "exit"
ROLE_HIDDEN = "hidden"


@dataclass(frozen=True)
class Hop:
    """One operator relay hop (config entry).

    *role*: ``entry`` | ``exit`` | ``hidden`` | ``""``.
    Hidden hops are flyclient light nodes (rpOS) — intermediate only, never
    public catalog residual dial peers.
    """

    host: str
    port: int = PRODUCT_NODE_PORT
    role: str = ""  # "entry" | "exit" | "hidden" | ""

    def as_endpoint(self) -> Endpoint:
        return Endpoint(host=self.host, port=int(self.port))

    def is_hidden(self) -> bool:
        return (self.role or "").strip().lower() == ROLE_HIDDEN

    def label(self) -> str:
        """User-facing hop label — country name for monopin peers, never raw IP.

        Hidden flyclient hops are labelled generically (no user-device IP leak).
        """
        if self.is_hidden():
            return "hidden hop"
        try:
            from client.residual_public import (
                is_residual_monopin_host,
                public_label_for_host,
            )

            if is_residual_monopin_host(self.host):
                return public_label_for_host(self.host)
        except Exception:  # noqa: BLE001
            pass
        # Non-catalog hop: avoid echoing dotted-quad IPs in status text
        h = (self.host or "").strip()
        if h and h.replace(".", "").isdigit():
            return "VPN hop"
        return f"{h}:{int(self.port)}" if h else "VPN hop"


@dataclass
class MultiHopConfig:
    """Ordered hop list. Empty or disabled ⇒ product single hop (entry)."""

    hops: list[Hop] = field(default_factory=list)
    enabled: bool = False

    def active_hops(self) -> list[Hop]:
        """Configured hop path (entry first; exit only when multi-hop enabled).

        When disabled, returns **only the configured entry hop** (first hop),
        so user entry-country selection (e.g. Germany) is honoured for
        single-hop residual — not hard-locked to the historical Iceland monopin.
        """
        path = build_hop_path(self.hops)
        if not self.enabled:
            return [path[0]] if path else [Hop(PRODUCT_NODE_HOST, PRODUCT_NODE_PORT, role="entry")]
        return path


def build_hop_path(hops: Sequence[Hop] | Iterable[Hop] | None) -> list[Hop]:
    """Normalize hop list; default to product single hop when empty.

    Preserves explicit ``hidden`` roles (rpOS flyclient intermediate hops).
    Does not promote hidden hops to entry/exit when auto-tagging ends.
    """
    items = list(hops or [])
    cleaned: list[Hop] = []
    for h in items:
        host = (h.host or "").strip()
        if not host:
            continue
        port = int(h.port) if h.port else PRODUCT_NODE_PORT
        if port <= 0 or port > 65535:
            port = PRODUCT_NODE_PORT
        role = (getattr(h, "role", None) or "").strip().lower()
        if role not in ("", ROLE_ENTRY, ROLE_EXIT, ROLE_HIDDEN):
            role = ""
        cleaned.append(Hop(host=host, port=port, role=role))
    if not cleaned:
        return [Hop(PRODUCT_NODE_HOST, PRODUCT_NODE_PORT, role=ROLE_ENTRY)]
    # Tag entry/exit when ≥2 hops and roles empty — never overwrite hidden.
    if len(cleaned) >= 2:
        if not cleaned[0].role:
            cleaned[0] = Hop(cleaned[0].host, cleaned[0].port, role=ROLE_ENTRY)
        if not cleaned[-1].role:
            cleaned[-1] = Hop(cleaned[-1].host, cleaned[-1].port, role=ROLE_EXIT)
        # If last hop was wrongly empty but middle is hidden, exit stays last.
    return cleaned


def is_hidden_hop(hop: Hop | None) -> bool:
    """True when *hop* is a flyclient hidden intermediate (not public catalog)."""
    if hop is None:
        return False
    return bool(hop.is_hidden())


def public_catalog_hosts(
    catalog: Sequence[CountryNode] | None = None,
) -> frozenset[str]:
    """Hosts that are legitimate public residual dial targets (IS/DE catalog)."""
    cat = tuple(catalog) if catalog is not None else PRODUCT_COUNTRY_CATALOG
    return frozenset(n.host.strip() for n in cat if (n.host or "").strip())


def public_dialable_peers(
    catalog: Sequence[CountryNode] | None = None,
    *,
    hidden_hosts: Sequence[str] | None = None,
) -> tuple[CountryNode, ...]:
    """Public catalog peers only — hidden flyclient hosts are never dialable here.

    *hidden_hosts* is an extra denylist (e.g. from a local registry). Catalog
    entries that match a hidden host are excluded (defence in depth).
    """
    cat = tuple(catalog) if catalog is not None else PRODUCT_COUNTRY_CATALOG
    deny = {(h or "").strip() for h in (hidden_hosts or ()) if (h or "").strip()}
    out: list[CountryNode] = []
    for n in cat:
        h = (n.host or "").strip()
        if not h or h in deny:
            continue
        out.append(n)
    return tuple(out)


def build_multihop_path_with_hidden(
    entry: Hop | CountryNode,
    exit_hop: Hop | CountryNode,
    hidden: Sequence[Hop] | None = None,
    *,
    enabled: bool = True,
) -> MultiHopConfig:
    """Build entry → [hidden flyclient hops…] → exit multi-hop path.

    Residual dial remains the **exit** (last hop) when multi-hop is active —
    same honesty as two-hop residual-via-exit. Hidden hops are intermediate
    only and must not be public catalog hosts.

    When *enabled* is False or no exit distinct from entry, returns single-hop
    entry config (fail closed to single-hop; does not invent multi-hop).
    """
    def _as_hop(node: Hop | CountryNode, role: str) -> Hop:
        if isinstance(node, CountryNode):
            return node.as_hop(role=role)
        host = (node.host or "").strip()
        port = int(node.port) if node.port else PRODUCT_NODE_PORT
        return Hop(host=host, port=port, role=role)

    entry_h = _as_hop(entry, ROLE_ENTRY)
    exit_h = _as_hop(exit_hop, ROLE_EXIT)
    if not entry_h.host or not exit_h.host:
        return MultiHopConfig(hops=[entry_h] if entry_h.host else [], enabled=False)
    if not enabled:
        return MultiHopConfig(hops=[entry_h], enabled=False)
    if (
        entry_h.host.strip() == exit_h.host.strip()
        and int(entry_h.port) == int(exit_h.port)
    ):
        # No distinct exit — stay single-hop honest
        return MultiHopConfig(hops=[entry_h], enabled=False)

    pub = public_catalog_hosts()
    mid: list[Hop] = []
    for h in hidden or ():
        host = (h.host or "").strip()
        if not host:
            continue
        # Never place a public monopin as a "hidden" hop
        if host in pub:
            continue
        port = int(h.port) if h.port else PRODUCT_NODE_PORT
        mid.append(Hop(host=host, port=port, role=ROLE_HIDDEN))

    path = build_hop_path([entry_h, *mid, exit_h])
    return MultiHopConfig(hops=path, enabled=True)


def multihop_config_with_hidden_registry(
    entry_country: str | None = None,
    *,
    multihop_enabled: bool = False,
    catalog: Sequence[CountryNode] | None = None,
    hidden_hops: Sequence[Hop] | None = None,
    rng: random.Random | None = None,
) -> MultiHopConfig:
    """Like :func:`multihop_config_for_entry_country` plus optional hidden middles.

    When multi-hop is off or no exit peer exists, hidden hops are ignored
    (fail closed / single-hop residual). Residual remains via exit when active.
    """
    base = multihop_config_for_entry_country(
        entry_country,
        multihop_enabled=multihop_enabled,
        catalog=catalog,
        rng=rng,
    )
    if not multihop_enabled or not base.enabled or len(base.hops) < 2:
        return base
    entry_h = base.hops[0]
    exit_h = base.hops[-1]
    return build_multihop_path_with_hidden(
        entry_h,
        exit_h,
        hidden_hops,
        enabled=True,
    )


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
    """Result of entry-primary / exit-failover / capacity residual preference."""

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
    - Else first catalog peer whose host ≠ entry (e.g. IS↔DE when two peers).
    - Never falls back to PRODUCT_EXIT_HOST when entry is already the exit peer.
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
    of the exit peer does **not** failover to the same exit again.
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
    rng: random.Random | None = None,
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

    # Preferred entry down/draining → solid peer failover (other catalog host).
    # When *rng* is provided and multiple catalog peers exist, pick among
    # non-preferred hosts so multi-peer wipe hop-off is not stuck on one alternate.
    # Drain (fleet wipe) is labeled wipe_drain_failover; plain down is exit_failover.
    if exit_ok and (exit_ep.host or "").strip() != (entry_ep.host or "").strip():
        failover_ep = exit_ep
        if rng is not None:
            alts = [
                n.as_endpoint()
                for n in PRODUCT_COUNTRY_CATALOG
                if (n.host or "").strip()
                and (n.host or "").strip() != (entry_ep.host or "").strip()
            ]
            if alts:
                failover_ep = rng.choice(alts)
        try:
            from client.wipe_hop import REASON_WIPE_DRAIN_FAILOVER as _wipe_reason
        except Exception:  # noqa: BLE001
            _wipe_reason = "wipe_drain_failover"
        reason = (
            _wipe_reason if bool(entry_draining) else "exit_failover"
        )
        return ResidualSelection(
            endpoint=failover_ep,
            reason=reason,
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
    """Honest UI/status for multi-hop.

    Never claims full intermediate onion encapsulation. Hidden flyclient hops
    appear as ``hidden hop`` labels only; residual remains via exit peer.
    """
    cfg = config or MultiHopConfig()
    if not cfg.enabled:
        return "single-hop (multi-hop inactive)"
    hops = build_hop_path(cfg.hops)
    if len(hops) < 2:
        return "single-hop (multi-hop needs ≥2 configured hops)"
    labels = " → ".join(h.label() for h in hops)
    n_hidden = sum(1 for h in hops if h.is_hidden())
    if not MULTI_HOP_ROUTING_IMPLEMENTED:
        return f"multi-hop path configured (not routed; entry-only): {labels}"
    if is_multihop_active(cfg):
        residual = residual_endpoint(cfg)
        try:
            from client.residual_public import public_label_for_host

            via = public_label_for_host(residual.host)
        except Exception:  # noqa: BLE001
            via = "VPN node"
        # Residual-via-exit honesty (not full onion claim)
        extra = ""
        if n_hidden:
            extra = (
                f"; {n_hidden} hidden flyclient hop(s) — light intermediate "
                "participation, not full onion encapsulation"
            )
        return (
            f"multi-hop active ({len(hops)} hops): {labels} "
            f"(residual via {via}){extra}"
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
    """Product exit hop (Germany DE) for multi-hop residual."""
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
    """Shipped entry (Iceland) → exit (Germany DE) path."""
    return build_entry_exit_path(PRODUCT_EXIT_HOST, exit_port=PRODUCT_EXIT_PORT)


def multihop_config_from_env(
    env: dict[str, str] | None = None,
) -> MultiHopConfig:
    """Build MultiHopConfig from operator environment and/or user Settings.

    - ``RPT_MULTIHOP_ENABLED=1`` — enable multi-hop residual via exit hop
      (when this env key is set it wins over Settings)
    - When env key is unset, product Settings ``privacy_multihop`` is used
      (default **off** / single-hop residual baseline)
    - ``RPT_ENTRY_COUNTRY`` / Settings ``entry_country`` — IS or DE (default DE)
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

    # Entry country: env wins, else product Settings (default Germany/DE)
    entry_country = str(e.get("RPT_ENTRY_COUNTRY", "") or "").strip()
    if not entry_country and env is None:
        try:
            import sys as _sys

            if _sys.platform == "win32":
                from client.windows.settings_store import load_settings as _load_s
            else:
                from client.linux.settings_store import load_settings as _load_s

            entry_country = getattr(
                _load_s(), "entry_country", DEFAULT_ENTRY_COUNTRY
            )
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
    if host == PRODUCT_DE_HOST or host == PRODUCT_EXIT_HOST:
        return "de_node_elgamal.pub"
    # Retired US monopin: heal to DE pin (stale prefs normalize entry to DE first)
    if host == PRODUCT_US_HOST:
        return "de_node_elgamal.pub"
    if host == PRODUCT_RO_HOST:
        return "exit_node_elgamal.pub"  # stale RO → exit pin (now DE material)
    return "node_elgamal.pub"
