"""Background wipe-drain hop-off and preferred rejoin (no user interaction).

When the preferred residual peer enters drain (scheduled wipe), clients hop to a
healthy alternate catalog peer. When that peer is residual-ready again, clients
rejoin preferred automatically.

Honesty: residual re-select + reconnect — not zero packet-loss mid-tunnel cutover.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from .endpoint import Endpoint
from .multihop import (
    PRODUCT_COUNTRY_CATALOG,
    CountryNode,
    MultiHopConfig,
    ResidualSelection,
    ResidualUnavailable,
    entry_endpoint,
    product_country_catalog,
)

REASON_WIPE_DRAIN_FAILOVER = "wipe_drain_failover"
REASON_WIPE_REJOIN = "wipe_rejoin_preferred"

STATE_READY = "ready"
STATE_DRAINING = "draining"
STATE_REBUILDING = "rebuilding"


@dataclass(frozen=True)
class WipeSignal:
    """Drain/ready signal from a residual peer (control frame or private JSON)."""

    state: str  # ready | draining | rebuilding
    host: str = ""
    role: str = ""

    @property
    def is_drain(self) -> bool:
        return self.state in (STATE_DRAINING, STATE_REBUILDING)

    @property
    def is_ready(self) -> bool:
        return self.state == STATE_READY

    def to_dict(self) -> dict[str, str]:
        return {"state": self.state, "host": self.host, "role": self.role}


def parse_wipe_signal_json(raw: Any) -> WipeSignal | None:
    """Parse private node-state JSON. Fail soft → None."""
    data = raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return None
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
    if not isinstance(data, Mapping):
        return None
    state = str(data.get("state") or "").strip().lower()
    if state in ("drain", "draining"):
        state = STATE_DRAINING
    elif state in ("rebuild", "rebuilding", "held"):
        state = STATE_REBUILDING
    elif state in ("ok", "up", "healthy", "ready", ""):
        state = STATE_READY if state else ""
    if state not in (STATE_READY, STATE_DRAINING, STATE_REBUILDING):
        # Accept flag-style payloads
        if data.get("draining") or data.get("rebuilding"):
            state = (
                STATE_REBUILDING if data.get("rebuilding") else STATE_DRAINING
            )
        elif data.get("ready") is True:
            state = STATE_READY
        else:
            return None
    host = str(data.get("host") or "").strip()
    role = str(data.get("role") or "").strip().lower()
    return WipeSignal(state=state, host=host, role=role)


def parse_node_status_wire(data: bytes) -> WipeSignal | None:
    """Parse residual NODE_STATUS control frame. Fail soft → None."""
    try:
        from node.protocol import (
            NODE_STATUS_DRAINING,
            NODE_STATUS_READY,
            NODE_STATUS_REBUILDING,
            parse_node_status,
        )
    except Exception:  # noqa: BLE001
        try:
            from protocol import (  # type: ignore
                NODE_STATUS_DRAINING,
                NODE_STATUS_READY,
                NODE_STATUS_REBUILDING,
                parse_node_status,
            )
        except Exception:  # noqa: BLE001
            return None
    try:
        _sid, flags, host, role = parse_node_status(data)
    except Exception:  # noqa: BLE001
        return None
    if flags & NODE_STATUS_REBUILDING:
        state = STATE_REBUILDING
    elif flags & NODE_STATUS_DRAINING:
        state = STATE_DRAINING
    elif flags & NODE_STATUS_READY:
        state = STATE_READY
    else:
        state = STATE_READY
    return WipeSignal(state=state, host=host or "", role=role or "")


def catalog_peer_endpoints(
    catalog: Sequence[CountryNode] | None = None,
) -> list[Endpoint]:
    cat = list(catalog) if catalog is not None else list(product_country_catalog())
    out: list[Endpoint] = []
    seen: set[str] = set()
    for n in cat:
        h = (n.host or "").strip()
        if not h or h in seen:
            continue
        seen.add(h)
        out.append(n.as_endpoint())
    return out


def eligible_wipe_alternates(
    preferred: Endpoint,
    *,
    peer_health: Mapping[str, bool] | None = None,
    catalog: Sequence[CountryNode] | None = None,
) -> list[Endpoint]:
    """Healthy catalog peers whose host ≠ preferred (never same host)."""
    pref = (preferred.host or "").strip()
    alts: list[Endpoint] = []
    for ep in catalog_peer_endpoints(catalog):
        h = (ep.host or "").strip()
        if not h or h == pref:
            continue
        if peer_health is not None:
            # Accept host key or any true when host missing (optimistic)
            ok = peer_health.get(h)
            if ok is None:
                # also try by catalog code match
                ok = True
                for n in catalog or product_country_catalog():
                    if (n.host or "").strip() == h:
                        code = (n.code or "").strip().upper()
                        if code in peer_health:
                            ok = bool(peer_health[code])
                        break
            if not ok:
                continue
        alts.append(ep)
    return alts


def pick_random_alternate(
    preferred: Endpoint,
    *,
    peer_health: Mapping[str, bool] | None = None,
    catalog: Sequence[CountryNode] | None = None,
    rng: random.Random | None = None,
) -> Endpoint | None:
    """Random healthy non-preferred peer, or None if none eligible."""
    alts = eligible_wipe_alternates(
        preferred, peer_health=peer_health, catalog=catalog
    )
    if not alts:
        return None
    if len(alts) == 1:
        return alts[0]
    pick_rng = rng if rng is not None else random.Random()
    return pick_rng.choice(list(alts))


def select_wipe_aware_residual(
    config: MultiHopConfig | None = None,
    *,
    preferred_draining: bool = False,
    preferred_healthy: bool = True,
    peer_health: Mapping[str, bool] | None = None,
    catalog: Sequence[CountryNode] | None = None,
    rng: random.Random | None = None,
) -> ResidualSelection:
    """Wipe-cycle residual pick: hop off preferred while draining; rejoin when ready.

    - preferred_draining True → random healthy alternate (wipe_drain_failover)
    - preferred healthy and not draining → preferred (wipe_rejoin / entry_primary)
    - no alternate while draining → ResidualUnavailable (fail closed)
    """
    cfg = config or MultiHopConfig()
    preferred = entry_endpoint(cfg)
    pref_host = (preferred.host or "").strip()

    if preferred_draining:
        alt = pick_random_alternate(
            preferred,
            peer_health=peer_health,
            catalog=catalog if catalog is not None else PRODUCT_COUNTRY_CATALOG,
            rng=rng,
        )
        if alt is None or (alt.host or "").strip() == pref_host:
            raise ResidualUnavailable(
                "fail closed: preferred residual draining and no healthy "
                "alternate catalog peer for wipe hop-off"
            )
        return ResidualSelection(
            endpoint=alt,
            reason=REASON_WIPE_DRAIN_FAILOVER,
            entry_healthy=bool(preferred_healthy),
            exit_healthy=True,
            entry_draining=True,
            failover_active=True,
            preferred_host=pref_host,
        )

    # Ready / not draining — rejoin preferred when healthy
    if preferred_healthy:
        return ResidualSelection(
            endpoint=preferred,
            reason=REASON_WIPE_REJOIN,
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
            failover_active=False,
            preferred_host=pref_host,
        )
    # Preferred down (not just drain mark) — same alternate hop
    alt = pick_random_alternate(
        preferred,
        peer_health=peer_health,
        catalog=catalog if catalog is not None else PRODUCT_COUNTRY_CATALOG,
        rng=rng,
    )
    if alt is None:
        raise ResidualUnavailable(
            "fail closed: preferred residual unhealthy and no alternate peer"
        )
    return ResidualSelection(
        endpoint=alt,
        reason=REASON_WIPE_DRAIN_FAILOVER,
        entry_healthy=False,
        exit_healthy=True,
        entry_draining=False,
        failover_active=True,
        preferred_host=pref_host,
    )


def apply_wipe_signal_to_flags(
    signal: WipeSignal | None,
    *,
    preferred_host: str,
    current_entry_draining: bool = False,
) -> tuple[bool, bool, str]:
    """Map a wipe signal to (entry_draining, should_reselect, note).

    Fail soft: None signal → no change (keep current_entry_draining).
    Only signals for preferred host (or empty host = this residual) apply.
    """
    if signal is None:
        return bool(current_entry_draining), False, "no_signal"
    pref = (preferred_host or "").strip()
    sig_host = (signal.host or "").strip()
    if sig_host and pref and sig_host != pref:
        # Signal from a non-preferred peer — ignore for preferred drain flag
        return bool(current_entry_draining), False, "signal_other_host"
    if signal.is_drain:
        if current_entry_draining:
            return True, False, "already_draining"
        return True, True, "enter_drain_hop_off"
    if signal.is_ready:
        if not current_entry_draining:
            return False, False, "already_ready"
        return False, True, "ready_rejoin_preferred"
    return bool(current_entry_draining), False, "unknown_state"


def wipe_hop_advisory(selection: ResidualSelection | None) -> str | None:
    """Optional status line when hop/rejoin is wipe-driven."""
    if selection is None:
        return None
    if selection.reason == REASON_WIPE_DRAIN_FAILOVER:
        return (
            f"Notice: preferred residual ({selection.preferred_host or 'entry'}) "
            f"is draining for wipe/rebuild — automatically hopped to "
            f"{selection.endpoint.host}:{selection.endpoint.port}."
        )
    if selection.reason == REASON_WIPE_REJOIN:
        return (
            f"Notice: preferred residual is ready again — automatically "
            f"rejoining {selection.endpoint.host}:{selection.endpoint.port}."
        )
    return None
