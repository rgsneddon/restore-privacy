"""Sequential fleet wipedown planner for peer residual nodes.

With user-selected entry country, Iceland is **not** a fixed sole entry role —
every catalog country is a residual-capable peer. Fleet wipedown still runs on
**every** peer, but **never concurrently**:

1. Iceland (IS) first  
2. Only after IS wipe+rebuild is complete → Romania (RO)  
3. New catalog countries append in catalog order (recursive: finish prior first)

Uses the same country catalog as :mod:`client.multihop` (single source of truth).

Honesty:
- Host-local exclusive lock is not multi-VPS consensus — one orchestrator must
  drive the fleet sequence.
- Continuity requires ≥1 other catalog peer healthy before wiping a node.
- Not a zero packet-loss guarantee during drain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

# Preferred wipe order for known peers (others append after, catalog order)
PREFERRED_FLEET_ORDER: tuple[str, ...] = ("IS", "RO", "DE")


def _load_catalog():
    """Shared residual country catalog (client multihop factory)."""
    try:
        from client.multihop import product_country_catalog

        return list(product_country_catalog())
    except Exception:  # noqa: BLE001
        # Minimal fallback if client import unavailable on bare node tree
        from dataclasses import dataclass as _dc

        @_dc(frozen=True)
        class _N:
            code: str
            name: str
            host: str
            port: int = 44044

        return [
            _N("IS", "Iceland", "82.221.101.241"),
            _N("RO", "Romania", "185.146.232.107"),
            _N("DE", "Germany", "167.233.224.5"),
        ]


def fleet_country_codes(
    catalog: Sequence[Any] | None = None,
) -> list[str]:
    """Ordered country codes for fleet wipe (IS, RO, then any new peers)."""
    cat = list(catalog) if catalog is not None else _load_catalog()
    codes = [str(getattr(n, "code", "") or "").strip().upper() for n in cat]
    codes = [c for c in codes if c]
    # Stable: preferred order first, then remaining catalog order
    ordered: list[str] = []
    for pref in PREFERRED_FLEET_ORDER:
        if pref in codes and pref not in ordered:
            ordered.append(pref)
    for c in codes:
        if c not in ordered:
            ordered.append(c)
    return ordered


def fleet_wipe_order(
    catalog: Sequence[Any] | None = None,
) -> list[Any]:
    """Catalog nodes in wipe order (IS → RO → appended countries)."""
    cat = list(catalog) if catalog is not None else _load_catalog()
    by_code = {
        str(getattr(n, "code", "") or "").strip().upper(): n for n in cat
    }
    return [by_code[c] for c in fleet_country_codes(cat) if c in by_code]


@dataclass(frozen=True)
class FleetWipeDecision:
    """Pure planner decision for sequential fleet wipe."""

    allow: bool
    target_code: str | None
    reason: str
    completed: tuple[str, ...] = ()
    in_progress: str | None = None
    next_after_complete: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow": self.allow,
            "target_code": self.target_code,
            "reason": self.reason,
            "completed": list(self.completed),
            "in_progress": self.in_progress,
            "next_after_complete": self.next_after_complete,
        }


def next_wipe_target(
    *,
    completed: Iterable[str] = (),
    in_progress: str | None = None,
    catalog: Sequence[Any] | None = None,
) -> str | None:
    """Next country code to wipe, or None if fleet cycle complete / busy.

    If *in_progress* is set, returns that code (continue current node only) —
    never starts a different peer concurrently.
    """
    order = fleet_country_codes(catalog)
    done = {str(c or "").strip().upper() for c in completed if c}
    prog = (in_progress or "").strip().upper() or None
    if prog:
        if prog in order:
            return prog
        return None
    for code in order:
        if code not in done:
            return code
    return None


def assert_sequential_fleet_start(
    target_code: str,
    *,
    completed: Iterable[str] = (),
    in_progress: str | None = None,
    catalog: Sequence[Any] | None = None,
) -> FleetWipeDecision:
    """Refuse concurrent / out-of-order fleet wipe starts.

    Rules:
    - At most one in-progress wipe.
    - Cannot start RO while IS incomplete (unless IS already completed).
    - Cannot start a peer that is not the next incomplete in order.
    - Starting the same *in_progress* target is allowed (continue rebuild).
    """
    order = fleet_country_codes(catalog)
    want = (target_code or "").strip().upper()
    done = tuple(
        c
        for c in order
        if c in {str(x or "").strip().upper() for x in completed if x}
    )
    done_set = set(done)
    prog = (in_progress or "").strip().upper() or None

    if not want:
        return FleetWipeDecision(
            allow=False,
            target_code=None,
            reason="missing wipe target country code",
            completed=done,
            in_progress=prog,
        )
    if want not in order:
        return FleetWipeDecision(
            allow=False,
            target_code=want,
            reason=f"target {want!r} not in fleet catalog order {order}",
            completed=done,
            in_progress=prog,
        )

    expected = next_wipe_target(
        completed=done_set, in_progress=None, catalog=catalog
    )
    next_after = None
    if expected:
        idx = order.index(expected)
        next_after = order[idx + 1] if idx + 1 < len(order) else None

    if prog and prog != want:
        return FleetWipeDecision(
            allow=False,
            target_code=want,
            reason=(
                f"refusing concurrent fleet wipe: {prog} still in progress; "
                f"cannot start {want} until {prog} is fully rebuilt"
            ),
            completed=done,
            in_progress=prog,
            next_after_complete=next_after,
        )

    if prog == want:
        return FleetWipeDecision(
            allow=True,
            target_code=want,
            reason=f"continue in-progress wipe for {want}",
            completed=done,
            in_progress=prog,
            next_after_complete=next_after,
        )

    if want in done_set:
        return FleetWipeDecision(
            allow=False,
            target_code=want,
            reason=f"{want} already completed this fleet cycle",
            completed=done,
            in_progress=prog,
            next_after_complete=next_after,
        )

    if expected != want:
        return FleetWipeDecision(
            allow=False,
            target_code=want,
            reason=(
                f"out-of-order wipe refused: next required is {expected}, "
                f"not {want} (finish prior peer rebuild first)"
            ),
            completed=done,
            in_progress=prog,
            next_after_complete=next_after,
        )

    return FleetWipeDecision(
        allow=True,
        target_code=want,
        reason=f"sequential fleet wipe may start {want} (prior peers complete)",
        completed=done,
        in_progress=None,
        next_after_complete=next_after,
    )


@dataclass(frozen=True)
class PeerPrewipeGateResult:
    """≥1 other catalog peer healthy before wiping *target*."""

    allow_wipe: bool
    target_code: str
    healthy_peers: tuple[str, ...]
    unhealthy_peers: tuple[str, ...]
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow_wipe": self.allow_wipe,
            "target_code": self.target_code,
            "healthy_peers": list(self.healthy_peers),
            "unhealthy_peers": list(self.unhealthy_peers),
            "reasons": list(self.reasons),
            "continuity_honesty": (
                "automatic residual failover to a healthy peer while this node "
                "drains; not absolute zero packet loss"
            ),
        }


def evaluate_peer_prewipe_gate(
    target_code: str,
    peer_health: dict[str, bool],
    *,
    catalog: Sequence[Any] | None = None,
) -> PeerPrewipeGateResult:
    """Fail closed if no other catalog peer is healthy.

    *peer_health* maps country code (IS/RO/…) → healthy bool. Target itself is
    excluded from the peer set.
    """
    order = fleet_country_codes(catalog)
    want = (target_code or "").strip().upper()
    healthy: list[str] = []
    unhealthy: list[str] = []
    for code in order:
        if code == want:
            continue
        ok = bool(peer_health.get(code, False))
        if ok:
            healthy.append(code)
        else:
            unhealthy.append(code)
    if not healthy:
        return PeerPrewipeGateResult(
            allow_wipe=False,
            target_code=want,
            healthy_peers=(),
            unhealthy_peers=tuple(unhealthy),
            reasons=[
                f"fail closed: no healthy peer residual host while wiping {want} "
                f"— refuse wipe (would black-hole all residual paths)"
            ],
        )
    return PeerPrewipeGateResult(
        allow_wipe=True,
        target_code=want,
        healthy_peers=tuple(healthy),
        unhealthy_peers=tuple(unhealthy),
        reasons=[
            f"peer pre-wipe PASS: healthy peers {healthy} available for failover "
            f"while {want} drains"
        ],
    )


def mark_wipe_complete(
    code: str,
    completed: Iterable[str] = (),
    *,
    catalog: Sequence[Any] | None = None,
) -> tuple[list[str], str | None]:
    """Append *code* to completed list; return (new_completed, next_target)."""
    order = fleet_country_codes(catalog)
    done = [c for c in order if c in {str(x or "").strip().upper() for x in completed}]
    c = (code or "").strip().upper()
    if c and c not in done and c in order:
        done.append(c)
    nxt = next_wipe_target(completed=done, in_progress=None, catalog=catalog)
    return done, nxt


# ---------------------------------------------------------------------------
# Host-identity gate (orchestrator must not wipe a different peer locally)
# ---------------------------------------------------------------------------


def catalog_host_for_code(
    code: str,
    *,
    catalog: Sequence[Any] | None = None,
) -> str | None:
    """Return catalog monopin host for *code*, or None if unknown."""
    want = (code or "").strip().upper()
    if not want:
        return None
    for n in fleet_wipe_order(catalog):
        if str(getattr(n, "code", "") or "").strip().upper() == want:
            return str(getattr(n, "host", "") or "").strip() or None
    return None


def catalog_pub_name_for_code(
    code: str,
    *,
    catalog: Sequence[Any] | None = None,
) -> str:
    """Public pin filename for a catalog peer (entry vs exit hop).

    IS → ``node_elgamal.pub``; RO → ``exit_node_elgamal.pub``; others use
    catalog ``pub_name`` when present, else node_elgamal.pub.
    """
    want = (code or "").strip().upper()
    for n in fleet_wipe_order(catalog):
        if str(getattr(n, "code", "") or "").strip().upper() == want:
            pub = str(getattr(n, "pub_name", "") or "").strip()
            if pub:
                return pub
            break
    if want == "RO":
        return "exit_node_elgamal.pub"
    return "node_elgamal.pub"


def local_identity_hosts(
    *,
    env: dict | None = None,
    extra_hosts: Iterable[str] | None = None,
) -> set[str]:
    """Best-effort local host identifiers (IPs / RPT_NODE_HOST / hostname).

    Pure when *env* and *extra_hosts* fully specify identity; otherwise may
    probe the OS for addresses (never raises).
    """
    import os
    import socket

    e = env if env is not None else os.environ
    hosts: set[str] = set()
    for key in (
        "RPT_NODE_HOST",
        "RPT_FLEET_LOCAL_HOST",
        "RPT_LOCAL_HOST",
    ):
        v = str(e.get(key, "") or "").strip()
        if v:
            hosts.add(v)
    if extra_hosts:
        for h in extra_hosts:
            s = str(h or "").strip()
            if s:
                hosts.add(s)
    # OS best-effort (skipped when env forces country-only via RPT_FLEET_LOCAL_COUNTRY
    # and callers only need that — still cheap to collect)
    try:
        hn = socket.gethostname()
        if hn:
            hosts.add(hn)
        try:
            hosts.add(socket.gethostbyname(hn))
        except OSError:
            pass
    except OSError:
        pass
    try:
        # Primary outbound IP heuristic (does not send packets)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                hosts.add(ip)
        finally:
            s.close()
    except OSError:
        pass
    return {h for h in hosts if h}


def resolve_local_country_code(
    *,
    env: dict | None = None,
    local_hosts: Iterable[str] | None = None,
    local_country: str | None = None,
    catalog: Sequence[Any] | None = None,
    allow_orchestrator_default: bool = True,
) -> str | None:
    """Infer which catalog country this host is, if any.

    Priority:
    1. Explicit *local_country* argument
    2. ``RPT_FLEET_LOCAL_COUNTRY`` env
    3. Host match against catalog monopins via *local_hosts* / env / OS
    4. When still unknown and *allow_orchestrator_default*:
       ``RPT_FLEET_ORCHESTRATOR_DEFAULT`` (default **IS**) — fleet timer runs
       on the Iceland orchestrator; RO remains remote-gated until host match.
    """
    import os

    e = env if env is not None else os.environ
    if local_country is not None and str(local_country).strip():
        return str(local_country).strip().upper()
    env_cc = str(e.get("RPT_FLEET_LOCAL_COUNTRY", "") or "").strip().upper()
    if env_cc:
        return env_cc
    hosts = set(local_hosts) if local_hosts is not None else local_identity_hosts(env=e)
    hosts_n = {h.strip() for h in hosts if h and str(h).strip()}
    for n in fleet_wipe_order(catalog):
        h = str(getattr(n, "host", "") or "").strip()
        if h and h in hosts_n:
            return str(getattr(n, "code", "") or "").strip().upper() or None
    if allow_orchestrator_default:
        default = str(
            e.get("RPT_FLEET_ORCHESTRATOR_DEFAULT", "IS") or "IS"
        ).strip().upper()
        return default or None
    return None


def is_target_host_local(
    code: str,
    *,
    env: dict | None = None,
    local_hosts: Iterable[str] | None = None,
    local_country: str | None = None,
    catalog: Sequence[Any] | None = None,
) -> tuple[bool, str]:
    """True when this machine is the catalog peer for *code*.

    Fail closed when identity cannot be established: orchestrator must not
    treat an unknown host as the remote peer (would wipe the wrong box).
    """
    want = (code or "").strip().upper()
    if not want:
        return False, "empty target country code"
    target_host = catalog_host_for_code(want, catalog=catalog)
    local_cc = resolve_local_country_code(
        env=env,
        local_hosts=local_hosts,
        local_country=local_country,
        catalog=catalog,
    )
    if local_cc is not None:
        if local_cc == want:
            return (
                True,
                f"host_identity: local_country={local_cc} matches target={want} "
                f"(host={target_host or '?'})",
            )
        return (
            False,
            f"host_identity: local_country={local_cc} != target={want} "
            f"(target_host={target_host or '?'}) — refuse local destructive wipe "
            f"on orchestrator; use remote peer wipe for {want}",
        )
    # No country override: compare host strings
    import os

    e = env if env is not None else os.environ
    hosts = set(local_hosts) if local_hosts is not None else local_identity_hosts(env=e)
    if target_host and target_host in hosts:
        return (
            True,
            f"host_identity: local address set includes target host {target_host} "
            f"for {want}",
        )
    if target_host:
        return (
            False,
            f"host_identity: target={want} host={target_host} not in local "
            f"identities {sorted(hosts)[:8]} — refuse local stop/selfhost/rebuild; "
            f"orchestrator must not wipe a different peer",
        )
    return False, f"host_identity: unknown catalog host for target={want}"


def assert_local_host_is_target(
    code: str,
    *,
    env: dict | None = None,
    local_hosts: Iterable[str] | None = None,
    local_country: str | None = None,
    catalog: Sequence[Any] | None = None,
) -> None:
    """Raise AssertionError unless this host is the fleet wipe target peer."""
    ok, msg = is_target_host_local(
        code,
        env=env,
        local_hosts=local_hosts,
        local_country=local_country,
        catalog=catalog,
    )
    if not ok:
        raise AssertionError(msg)


def remote_wipe_command_template(
    code: str,
    *,
    env: dict | None = None,
    catalog: Sequence[Any] | None = None,
) -> str:
    """Shell template for wiping a remote peer (or fail-closed comment).

    Honors ``RPT_REMOTE_WIPE_CMD`` with ``{host}`` / ``{code}`` placeholders.
    Without it, returns a fail-closed command (non-zero exit).
    """
    import os
    import shlex

    e = env if env is not None else os.environ
    want = (code or "").strip().upper()
    host = catalog_host_for_code(want, catalog=catalog) or ""
    tmpl = str(e.get("RPT_REMOTE_WIPE_CMD", "") or "").strip()
    if tmpl:
        try:
            return tmpl.format(host=host, code=want)
        except (KeyError, ValueError):
            return tmpl.replace("{host}", host).replace("{code}", want)
    # Fail closed: do not pretend local wipe is remote success
    return (
        f"echo 'host_identity_gate: target={want} host={host} is remote; "
        f"set RPT_REMOTE_WIPE_CMD to wipe peer (e.g. ssh root@{{host}} …) "
        f"or run weekly rebuild on that host'; exit 1"
    ).format(host=host)


def is_fleet_cycle_complete(
    completed: Iterable[str],
    *,
    catalog: Sequence[Any] | None = None,
) -> bool:
    order = fleet_country_codes(catalog)
    done = {str(c or "").strip().upper() for c in completed if c}
    return bool(order) and all(c in done for c in order)


def role_for_country_code(code: str) -> str:
    """Lock/role string for a country (lowercase catalog code)."""
    return (code or "").strip().lower()


# Bulk multi-node wipe roles — refuse before any country mapping
BULK_WIPE_ROLES = frozenset({"exit", "both", "all"})
AUTO_WIPE_ROLES = frozenset({"", "auto", "next", "fleet"})


def assert_raw_wipe_role_allowed(role: str | None) -> tuple[bool, str]:
    """Refuse bulk wipe roles **before** country mapping.

    ``exit`` / ``both`` / ``all`` must never become a sequential target
    (historically ``exit`` was wrongly mapped to RO). Accept auto selectors
    and single-peer roles (entry/is/ro/<cc>).
    """
    r = (role or "").strip().lower()
    if r in BULK_WIPE_ROLES:
        return (
            False,
            f"refusing wipe role={role!r}: sequential fleet wipe only "
            f"(never exit|both|all bulk); use auto|entry|is|ro|<country>",
        )
    return True, ""


def country_code_for_legacy_role(role: str) -> str:
    """Map legacy single-peer roles onto catalog codes.

    Only ``entry`` → IS. ``ro`` / ``romania`` → RO. **Never** map ``exit`` → RO
    (bulk ``exit`` is refused by :func:`assert_raw_wipe_role_allowed`).
    """
    r = (role or "").strip().lower()
    if r in ("entry", "is", "iceland"):
        return "IS"
    if r in ("ro", "romania"):
        return "RO"
    return (role or "").strip().upper()


# Durable fleet-cycle state (orchestrator host)
FLEET_STATE_REL = "var/rpt-fleet-wipe-state.json"


def fleet_state_path(install_root: str | None = None) -> str:
    root = (install_root or "/opt/restore-privacy").rstrip("/") or "/opt/restore-privacy"
    return f"{root}/{FLEET_STATE_REL}"


def load_fleet_wipe_state(
    install_root: str | None = None,
    *,
    raw: dict | None = None,
) -> dict[str, Any]:
    """Load fleet cycle state: completed codes + optional in_progress.

    Pure when *raw* is passed; otherwise reads JSON from install_root (best-effort).
    """
    if raw is not None:
        data = raw
    else:
        data = {}
        try:
            from pathlib import Path

            p = Path(fleet_state_path(install_root))
            if p.is_file():
                import json

                blob = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(blob, dict):
                    data = blob
        except Exception:  # noqa: BLE001
            data = {}
    completed = data.get("completed") or []
    if not isinstance(completed, list):
        completed = []
    completed_n = [str(c).strip().upper() for c in completed if c]
    prog = data.get("in_progress")
    prog_n = str(prog).strip().upper() if prog else None
    return {
        "completed": completed_n,
        "in_progress": prog_n,
        "cycle_id": str(data.get("cycle_id") or ""),
    }


def save_fleet_wipe_state(
    *,
    completed: Iterable[str],
    in_progress: str | None = None,
    install_root: str | None = None,
    cycle_id: str = "",
) -> dict[str, Any]:
    """Write fleet state JSON (side effect — used by live orchestrator)."""
    import json
    from pathlib import Path

    payload = {
        "completed": [str(c).strip().upper() for c in completed if c],
        "in_progress": (in_progress or "").strip().upper() or None,
        "cycle_id": cycle_id or "",
    }
    path = Path(fleet_state_path(install_root))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def resolve_weekly_target(
    *,
    completed: Iterable[str] = (),
    in_progress: str | None = None,
    role_hint: str | None = None,
    catalog: Sequence[Any] | None = None,
    cycle_id: str = "",
) -> FleetWipeDecision:
    """Pick next fleet wipe target for weekly orchestrator.

    - Raw bulk roles (``exit``/``both``/``all``) refused **before** country map.
    - Auto: when the cycle is complete, **roll** completed → [] and target IS again.
    - Forced country (is/ro/entry) still sequential-gated (no out-of-order).
    """
    ok_raw, raw_msg = assert_raw_wipe_role_allowed(role_hint)
    if not ok_raw:
        return FleetWipeDecision(
            allow=False,
            target_code=None,
            reason=raw_msg,
            completed=tuple(
                str(c).strip().upper() for c in completed if c
            ),
            in_progress=(in_progress or "").strip().upper() or None,
        )

    order = fleet_country_codes(catalog)
    done = [c for c in order if c in {str(x).strip().upper() for x in completed if x}]
    prog = (in_progress or "").strip().upper() or None
    hint = (role_hint or "").strip().lower()
    auto = hint in AUTO_WIPE_ROLES

    if not auto:
        code = country_code_for_legacy_role(role_hint or "")
        return assert_sequential_fleet_start(
            code, completed=done, in_progress=prog, catalog=catalog
        )

    nxt = next_wipe_target(completed=done, in_progress=prog, catalog=catalog)
    if nxt is None:
        # Cycle complete → roll and start IS again (auto only)
        rolled: list[str] = []
        nxt = next_wipe_target(completed=rolled, in_progress=None, catalog=catalog)
        if nxt is None:
            return FleetWipeDecision(
                allow=False,
                target_code=None,
                reason="empty fleet catalog — no wipe target",
                completed=(),
                in_progress=None,
            )
        return FleetWipeDecision(
            allow=True,
            target_code=nxt,
            reason=(
                f"fleet cycle complete — rolled completed→[] for new cycle; "
                f"next target {nxt}"
            ),
            completed=(),
            in_progress=None,
            next_after_complete=(
                order[1] if len(order) > 1 else None
            ),
        )
    return assert_sequential_fleet_start(
        nxt, completed=done, in_progress=prog, catalog=catalog
    )
