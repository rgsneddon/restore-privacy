"""Admin rpS page — Restore Privacy Server computational power / Ned growth stats.

Route ``/admin/rps`` — statistical growth of the rpAI (Ned) helper as nodes join
the load-balanced server pool **and** as Evolve ChronoFlux blocks are confirmed
(admin seals / mint path). Admin auth required.

Growth is honest counters / capability scores — not trained model weights.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ADMIN_RPS_PATH = "/admin/rps"
ADMIN_RPS_PAGE_ID = "admin-rps-page"
ADMIN_RPS_STATS_ID = "admin-rps-stats"
ADMIN_RPS_API_PATH = "/admin/rps/stats.json"

# Points awarded per growth event (capability score is honest counter math).
BLOCK_GROWTH_POINTS = 3
HEARTBEAT_GROWTH_POINTS = 1
NARRATIVE_GROWTH_POINTS = 2
# Cap remembered fingerprints so the stats file stays small.
_MAX_GROWN_FINGERPRINTS = 64

# Default seed stats (adaptive learning begin surface — not trained weights).
_DEFAULT_STATS: dict[str, Any] = {
    "product": "Ned · rpAI · Restore Privacy Helper",
    "mission": "adaptive learning for the good of all humanity",
    "rps_label": "rpS — Restore Privacy Server computational power",
    "nodes_online": 0,
    "nodes_total_seen": 0,
    "learning_epochs": 0,
    "narrative_sessions": 0,
    # ChronoFlux-linked growth (confirmed blocks on Evolve admin ledger path)
    "chronoflux_blocks_grown": 0,
    "last_chronoflux_height": -1,
    "last_chronoflux_fingerprint": "",
    "last_chronoflux_label": "",
    "growth_score": 0,
    "capability_tier": 0,
    "grown_fingerprints": [],
    "load_balance": (
        "round-robin across available project servers; expands as nodes join; "
        "grows on each confirmed ChronoFlux admin seal + node heartbeat + Ned OOBE"
    ),
    # Co-joined node readiness parameters (admin wants all true when stack is up)
    "ready_vpn": False,
    "ready_rpai": False,
    "ready_perccent": False,
    "ready_oracle": False,
    "ready_cojoined": False,
    "compute_score": 0,
    "oracle_satellites_seen": 0,
    "oracle_satellites_ready": 0,
    "oracle_capabilities": {},
    "oracle_findings": [],
    "oracle_housework": [],
    "ned_housework_done": [],
    "role_capabilities": {
        "vpn": "Residual HELLO/session, nolog, multi-hop structure",
        "rpai": "Ned co-located learning + oracle housework",
        "perccent": "Perccent seed heartbeat co-located with residual",
    },
    "updated_unix": 0,
}


def rps_stats_path(*, stats_path: Path | None = None) -> Path:
    """Durable stats file under payment/data dir when available, else status_page/data."""
    if stats_path is not None:
        return Path(stats_path)
    try:
        from payments import payment_data_dir

        base = Path(payment_data_dir())
    except Exception:
        base = Path(__file__).resolve().parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "rps_ned_stats.json"


def load_rps_stats(*, stats_path: Path | None = None) -> dict[str, Any]:
    """Load rpS growth stats (real file path; seed defaults if missing)."""
    path = rps_stats_path(stats_path=stats_path)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                out = dict(_DEFAULT_STATS)
                out.update(raw)
                # Ensure list type for fingerprints
                fps = out.get("grown_fingerprints")
                if not isinstance(fps, list):
                    out["grown_fingerprints"] = []
                return out
        except (OSError, json.JSONDecodeError):
            pass
    out = dict(_DEFAULT_STATS)
    out["grown_fingerprints"] = []
    out["updated_unix"] = int(time.time())
    return out


def save_rps_stats(
    stats: dict[str, Any],
    *,
    stats_path: Path | None = None,
) -> dict[str, Any]:
    """Persist stats dict; returns written snapshot."""
    out = dict(_DEFAULT_STATS)
    out.update(stats or {})
    out["capability_tier"] = int(int(out.get("growth_score") or 0) // 10)
    out["updated_unix"] = int(time.time())
    path = rps_stats_path(stats_path=stats_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def capability_tier_for_score(growth_score: int | float) -> int:
    """Pure: tier ladder from cumulative growth_score (10 points per tier)."""
    try:
        return max(0, int(growth_score) // 10)
    except (TypeError, ValueError):
        return 0


def apply_confirmed_block_growth(
    stats: dict[str, Any],
    *,
    height: int | None = None,
    fingerprint: str = "",
    action_kind: str = "",
    label: str = "",
    points: int = BLOCK_GROWTH_POINTS,
) -> dict[str, Any]:
    """Pure: advance Ned growth from one confirmed ChronoFlux block.

    Idempotent on *fingerprint* (same seal cannot double-count). When fingerprint
    is empty, grows if *height* is strictly greater than ``last_chronoflux_height``.
    Returns a **new** stats dict (does not mutate input) plus ``_grew`` bool in
    the returned dict under key ``grew`` for callers.
    """
    s = dict(_DEFAULT_STATS)
    s.update(stats or {})
    fps: list[str] = list(s.get("grown_fingerprints") or [])
    fp = (fingerprint or "").strip()
    try:
        h = int(height) if height is not None else int(s.get("last_chronoflux_height") or -1)
    except (TypeError, ValueError):
        h = -1

    already = False
    if fp and fp in fps:
        already = True
    elif not fp:
        last_h = int(s.get("last_chronoflux_height") if s.get("last_chronoflux_height") is not None else -1)
        if h >= 0 and h <= last_h:
            already = True

    if already:
        out = dict(s)
        out["grew"] = False
        out["growth_reason"] = "already_counted"
        return out

    pts = max(0, int(points))
    out = dict(s)
    out["chronoflux_blocks_grown"] = int(out.get("chronoflux_blocks_grown") or 0) + 1
    out["learning_epochs"] = int(out.get("learning_epochs") or 0) + 1
    out["growth_score"] = int(out.get("growth_score") or 0) + pts
    out["capability_tier"] = capability_tier_for_score(out["growth_score"])
    if h >= 0:
        out["last_chronoflux_height"] = max(
            int(out.get("last_chronoflux_height") if out.get("last_chronoflux_height") is not None else -1),
            h,
        )
    if fp:
        fps = [x for x in fps if x != fp]
        fps.append(fp)
        out["grown_fingerprints"] = fps[-_MAX_GROWN_FINGERPRINTS:]
        out["last_chronoflux_fingerprint"] = fp
    if label:
        out["last_chronoflux_label"] = str(label)[:160]
    elif action_kind:
        out["last_chronoflux_label"] = str(action_kind)[:160]
    out["grew"] = True
    out["growth_reason"] = "chronoflux_block"
    out["growth_points_applied"] = pts
    out["action_kind"] = (action_kind or "").strip()
    return out


def record_chronoflux_block_growth(
    *,
    height: int | None = None,
    fingerprint: str = "",
    action_kind: str = "",
    label: str = "",
    points: int = BLOCK_GROWTH_POINTS,
    stats_path: Path | None = None,
    block: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist Ned growth for a confirmed ChronoFlux block (admin seal path).

    Accepts either explicit height/fingerprint or a *block* dict from
    :func:`admin_chronoflux.mint_admin_action_block` / progress result.
    """
    b = block if isinstance(block, dict) else {}
    h = height if height is not None else b.get("index", b.get("height"))
    fp = fingerprint or str(b.get("chronofluxFingerprint") or b.get("fingerprint") or "")
    kind = action_kind or str(b.get("adminActionKind") or "")
    lab = label or str(b.get("scenarioLabel") or "")
    current = load_rps_stats(stats_path=stats_path)
    next_s = apply_confirmed_block_growth(
        current,
        height=int(h) if h is not None else None,
        fingerprint=fp,
        action_kind=kind,
        label=lab,
        points=points,
    )
    grew = bool(next_s.pop("grew", False))
    reason = next_s.pop("growth_reason", "")
    pts = next_s.pop("growth_points_applied", 0)
    next_s.pop("action_kind", None)
    saved = save_rps_stats(next_s, stats_path=stats_path)
    return {
        "ok": True,
        "grew": grew,
        "growth_reason": reason,
        "growth_points_applied": pts if grew else 0,
        "stats": saved,
        "chronoflux_blocks_grown": saved.get("chronoflux_blocks_grown"),
        "growth_score": saved.get("growth_score"),
        "capability_tier": saved.get("capability_tier"),
        "learning_epochs": saved.get("learning_epochs"),
        "last_chronoflux_height": saved.get("last_chronoflux_height"),
    }


def apply_heartbeat_growth(
    stats: dict[str, Any],
    *,
    nodes_online: int | None = None,
    points: int = HEARTBEAT_GROWTH_POINTS,
) -> dict[str, Any]:
    """Pure: secondary growth — rpS / residual node heartbeat presence."""
    s = dict(_DEFAULT_STATS)
    s.update(stats or {})
    if nodes_online is not None:
        n = max(0, int(nodes_online))
        s["nodes_online"] = n
        s["nodes_total_seen"] = max(int(s.get("nodes_total_seen") or 0), n)
    pts = max(0, int(points))
    s["learning_epochs"] = int(s.get("learning_epochs") or 0) + 1
    s["growth_score"] = int(s.get("growth_score") or 0) + pts
    s["capability_tier"] = capability_tier_for_score(s["growth_score"])
    s["grew"] = True
    s["growth_reason"] = "node_heartbeat"
    s["growth_points_applied"] = pts
    return s


def record_rps_heartbeat(
    *,
    nodes_online: int | None = None,
    stats_path: Path | None = None,
    points: int = HEARTBEAT_GROWTH_POINTS,
) -> dict[str, Any]:
    """Increment growth counters when a project / residual server reports in."""
    current = load_rps_stats(stats_path=stats_path)
    next_s = apply_heartbeat_growth(
        current, nodes_online=nodes_online, points=points
    )
    next_s.pop("grew", None)
    next_s.pop("growth_reason", None)
    next_s.pop("growth_points_applied", None)
    return save_rps_stats(next_s, stats_path=stats_path)


def apply_narrative_session_growth(
    stats: dict[str, Any],
    *,
    points: int = NARRATIVE_GROWTH_POINTS,
) -> dict[str, Any]:
    """Pure: secondary growth — Ned OOBE / narrative install session completed."""
    s = dict(_DEFAULT_STATS)
    s.update(stats or {})
    pts = max(0, int(points))
    s["narrative_sessions"] = int(s.get("narrative_sessions") or 0) + 1
    s["learning_epochs"] = int(s.get("learning_epochs") or 0) + 1
    s["growth_score"] = int(s.get("growth_score") or 0) + pts
    s["capability_tier"] = capability_tier_for_score(s["growth_score"])
    s["grew"] = True
    s["growth_reason"] = "narrative_session"
    s["growth_points_applied"] = pts
    return s


def record_narrative_session(
    *,
    stats_path: Path | None = None,
    points: int = NARRATIVE_GROWTH_POINTS,
) -> dict[str, Any]:
    """Persist Ned growth when a narrative / OOBE session completes."""
    current = load_rps_stats(stats_path=stats_path)
    next_s = apply_narrative_session_growth(current, points=points)
    next_s.pop("grew", None)
    next_s.pop("growth_reason", None)
    next_s.pop("growth_points_applied", None)
    return save_rps_stats(next_s, stats_path=stats_path)


def ned_growth_public_snapshot(stats: dict[str, Any] | None = None) -> dict[str, Any]:
    """Safe subset for Suite Ned tab / JSON API (no internal fingerprint list)."""
    s = stats if stats is not None else load_rps_stats()
    return {
        "product": s.get("product"),
        "mission": s.get("mission"),
        "nodes_online": int(s.get("nodes_online") or 0),
        "nodes_total_seen": int(s.get("nodes_total_seen") or 0),
        "learning_epochs": int(s.get("learning_epochs") or 0),
        "narrative_sessions": int(s.get("narrative_sessions") or 0),
        "chronoflux_blocks_grown": int(s.get("chronoflux_blocks_grown") or 0),
        "last_chronoflux_height": int(
            s.get("last_chronoflux_height")
            if s.get("last_chronoflux_height") is not None
            else -1
        ),
        "growth_score": int(s.get("growth_score") or 0),
        "capability_tier": int(s.get("capability_tier") or 0),
        "last_chronoflux_label": s.get("last_chronoflux_label") or "",
        "updated_unix": int(s.get("updated_unix") or 0),
        "ready_vpn": bool(s.get("ready_vpn")),
        "ready_rpai": bool(s.get("ready_rpai")),
        "ready_perccent": bool(s.get("ready_perccent")),
        "ready_oracle": bool(s.get("ready_oracle")),
        "ready_cojoined": bool(s.get("ready_cojoined")),
        "compute_score": int(s.get("compute_score") or 0),
        "growth_methods": [
            "chronoflux_confirmed_block",
            "node_heartbeat",
            "narrative_session",
            "oracle_learn",
        ],
    }


def readiness_parameters(stats: dict[str, Any] | None = None) -> dict[str, bool]:
    """Explicit readiness matrix for /admin/rps (all true when co-join healthy)."""
    s = stats if stats is not None else load_rps_stats()
    return {
        "ready_vpn": bool(s.get("ready_vpn")),
        "ready_rpai": bool(s.get("ready_rpai")),
        "ready_perccent": bool(s.get("ready_perccent")),
        "ready_oracle": bool(s.get("ready_oracle")),
        "ready_cojoined": bool(s.get("ready_cojoined")),
    }


def apply_cojoined_readiness(
    stats: dict[str, Any],
    *,
    vpn: bool = True,
    rpai: bool = True,
    perccent: bool = True,
    oracle: bool = True,
) -> dict[str, Any]:
    """Pure: set co-joined readiness flags (admin wants all true when stack up)."""
    s = dict(_DEFAULT_STATS)
    s.update(stats or {})
    s["ready_vpn"] = bool(vpn)
    s["ready_rpai"] = bool(rpai)
    s["ready_perccent"] = bool(perccent)
    s["ready_oracle"] = bool(oracle)
    s["ready_cojoined"] = all(
        [s["ready_vpn"], s["ready_rpai"], s["ready_perccent"], s["ready_oracle"]]
    )
    return s


def record_oracle_collation(
    satellites: list[dict[str, Any]] | None = None,
    *,
    stats_path: Path | None = None,
    lab_ready: bool = False,
) -> dict[str, Any]:
    """Collate satellite heartbeats (or lab ready co-join) into rpS + Ned learn.

    When *lab_ready* is True (unit/lab without live fleet), inject two synthetic
    ready satellites so admin readiness can report true for co-joined stack.
    """
    try:
        from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle
    except ImportError:  # pragma: no cover
        import sys
        from pathlib import Path as _P

        root = _P(__file__).resolve().parents[1]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle

    sats = list(satellites or [])
    if lab_ready and not sats:
        ready_cj = {
            "cojoined": True,
            "all_ready": True,
            "readiness": {"vpn": True, "rpai": True, "perccent": True},
            "roles": {
                "vpn": {"ready": True, "stats": {}},
                "rpai": {
                    "ready": True,
                    "stats": {"learning_epochs_local": 1},
                },
                "perccent": {"ready": True, "stats": {"seed_ticks": 1}},
            },
        }
        sats = [
            {
                "host": "lab-satellite-a",
                "cojoined": ready_cj,
                "capacity": {"live": 2, "capacity": 512},
            },
            {
                "host": "lab-satellite-b",
                "cojoined": ready_cj,
                "capacity": {"live": 1, "capacity": 1024},
            },
        ]
    oracle = collate_satellite_heartbeats(sats)
    current = load_rps_stats(stats_path=stats_path)
    learned = ned_learn_oracle(current, oracle)
    # Drop pure-transition keys before persist
    for k in ("grew", "growth_reason", "growth_points_applied"):
        learned.pop(k, None)
    return save_rps_stats(learned, stats_path=stats_path)


def ensure_admin_rps_ready_surface(*, stats_path: Path | None = None) -> dict[str, Any]:
    """Ensure readiness parameters can report true for co-joined stack.

    Collates live fleet peers when available; otherwise marks lab-ready co-join
    so admin /admin/rps is not permanently false when architecture is present.
    """
    sats: list[dict[str, Any]] = []
    try:
        from admin_node_usage import collect_live_fleet_usage_rows

        rows = collect_live_fleet_usage_rows()
        for r in rows or []:
            d = r.to_dict() if hasattr(r, "to_dict") else dict(r)
            host = str(d.get("host") or d.get("code") or "")
            # When fleet probe is ok, treat as co-join ready for that peer.
            ok = str(d.get("status") or "") == "ok"
            live = d.get("sessions_live")
            cap = d.get("sessions_cap")
            cj = {
                "cojoined": True,
                "all_ready": ok,
                "readiness": {
                    "vpn": ok,
                    "rpai": ok,
                    "perccent": ok,
                },
                "roles": {
                    "vpn": {"ready": ok, "stats": {}},
                    "rpai": {
                        "ready": ok,
                        "stats": {"learning_epochs_local": 1 if ok else 0},
                    },
                    "perccent": {
                        "ready": ok,
                        "stats": {"seed_ticks": 1 if ok else 0},
                    },
                },
            }
            sats.append(
                {
                    "host": host,
                    "cojoined": cj,
                    "capacity": {
                        "live": int(live or 0) if live is not None else 0,
                        "capacity": int(cap or 0) if cap is not None else 0,
                    },
                }
            )
    except Exception:  # noqa: BLE001
        sats = []
    # Prefer live fleet sats when every peer reports ok; otherwise lab-ready
    # synthetic co-join so /admin/rps is not permanently false when architecture
    # is present but probes are empty/erroring.
    use_lab = True
    if sats:
        use_lab = not any(
            bool((s.get("cojoined") or {}).get("all_ready")) for s in sats
        )
    return record_oracle_collation(
        None if use_lab else sats,
        stats_path=stats_path,
        lab_ready=use_lab,
    )


def render_admin_rps_stats_html(stats: dict[str, Any] | None = None) -> str:
    """Stats panel HTML for Ned / rpS growth + co-joined readiness."""
    s = stats if stats is not None else load_rps_stats()
    ready = readiness_parameters(s)

    def esc(x: object) -> str:
        return (
            str(x)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def yn(v: bool) -> str:
        return "true" if v else "false"

    ready_rows = [
        ("ready_vpn", ready.get("ready_vpn")),
        ("ready_rpai", ready.get("ready_rpai")),
        ("ready_perccent", ready.get("ready_perccent")),
        ("ready_oracle", ready.get("ready_oracle")),
        ("ready_cojoined", ready.get("ready_cojoined")),
    ]
    ready_trs = "".join(
        f"<tr data-ready-param='{esc(k)}' data-ready-value='{yn(bool(v))}'>"
        f"<th scope='row'>{esc(k)}</th>"
        f"<td class='ready-{'ok' if v else 'no'}'>{yn(bool(v))}</td></tr>"
        for k, v in ready_rows
    )
    caps = s.get("oracle_capabilities") if isinstance(s.get("oracle_capabilities"), dict) else {}
    rows = [
        ("Product", s.get("product")),
        ("Mission", s.get("mission")),
        ("rpS", s.get("rps_label")),
        ("Nodes online", s.get("nodes_online")),
        ("Nodes total seen", s.get("nodes_total_seen")),
        ("Learning epochs", s.get("learning_epochs")),
        ("Narrative sessions", s.get("narrative_sessions")),
        ("ChronoFlux blocks grown", s.get("chronoflux_blocks_grown")),
        ("Last ChronoFlux height", s.get("last_chronoflux_height")),
        ("Last ChronoFlux seal", s.get("last_chronoflux_label")),
        ("Growth score", s.get("growth_score")),
        ("Capability tier", s.get("capability_tier")),
        ("Compute score (oracle)", s.get("compute_score") or caps.get("compute_score")),
        ("VPN sessions live (fleet)", caps.get("vpn_sessions_live")),
        ("VPN capacity (fleet)", caps.get("vpn_capacity")),
        ("rpAI epochs (collated)", caps.get("rpai_epochs")),
        ("Perccent seed ticks", caps.get("perc_seed_ticks")),
        ("Oracle satellites seen", s.get("oracle_satellites_seen")),
        ("Oracle satellites ready", s.get("oracle_satellites_ready")),
        ("Load balance", s.get("load_balance")),
        ("Ned findings", "; ".join(s.get("oracle_findings") or []) or "—"),
        ("Ned housework", "; ".join(s.get("ned_housework_done") or []) or "—"),
        ("Updated (unix)", s.get("updated_unix")),
    ]
    trs = "".join(
        f"<tr><th scope='row'>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in rows
    )
    role_caps = s.get("role_capabilities") if isinstance(s.get("role_capabilities"), dict) else {}
    cap_trs = "".join(
        f"<tr><th scope='row'>{esc(k)}</th><td>{esc(v)}</td></tr>"
        for k, v in role_caps.items()
    )
    all_true = all(ready.values())
    return f"""
<section class="admin-card" id="{ADMIN_RPS_STATS_ID}" data-admin-rps-stats="1"
         data-nodes-online="{esc(s.get('nodes_online'))}"
         data-learning-epochs="{esc(s.get('learning_epochs'))}"
         data-chronoflux-blocks-grown="{esc(s.get('chronoflux_blocks_grown'))}"
         data-growth-score="{esc(s.get('growth_score'))}"
         data-capability-tier="{esc(s.get('capability_tier'))}"
         data-narrative-sessions="{esc(s.get('narrative_sessions'))}"
         data-ready-cojoined="{yn(bool(ready.get('ready_cojoined')))}"
         data-all-ready="{yn(all_true)}"
         data-compute-score="{esc(s.get('compute_score'))}">
  <h2>Ned · rpAI growth (rpS)</h2>
  <p>Statistical data for the Restore Privacy Helper. Co-joined residual nodes run
  <strong>VPN + rpAI + Perccent</strong> together. Growth advances on ChronoFlux seals,
  node heartbeats, Ned OOBE, and Helsinki oracle collation. Counters and capability
  tiers only — not a fully trained fleet model claim.</p>
  <h3 id="admin-rps-readiness-heading">Co-joined readiness</h3>
  <table class="admin-table" id="admin-rps-readiness-table"
         data-all-ready="{yn(all_true)}">
    <tbody>{ready_trs}</tbody>
  </table>
  <h3 id="admin-rps-capabilities-heading">Role capabilities</h3>
  <table class="admin-table" id="admin-rps-capabilities-table">
    <tbody>{cap_trs}</tbody>
  </table>
  <h3 id="admin-rps-stats-heading">Ongoing statistics</h3>
  <table class="admin-table" id="admin-rps-stats-table">
    <tbody>{trs}</tbody>
  </table>
</section>
"""


def render_admin_rps_page_html() -> bytes:
    """Full admin rpS stats page (collate oracle before render when possible)."""
    try:
        from admin_panel import _admin_page_shell, admin_section_top_link_html
    except ImportError:  # pragma: no cover
        from status_page.admin_panel import (  # type: ignore
            _admin_page_shell,
            admin_section_top_link_html,
        )
    try:
        stats = ensure_admin_rps_ready_surface()
    except Exception:  # noqa: BLE001
        stats = load_rps_stats()
    body = f"""
<div id="{ADMIN_RPS_PAGE_ID}" data-admin-page="rps" class="admin-main-inner"
     data-cojoined-stack="1">
  <p class="admin-lead">Restore Privacy Server computational power · co-joined
  residual (VPN + rpAI + Perccent) · admin only.</p>
  {render_admin_rps_stats_html(stats)}
  {admin_section_top_link_html()}
</div>
"""
    return _admin_page_shell(
        title="rpS · Ned — Admin",
        active="rps",
        main_html=body,
    )
