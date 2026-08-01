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
        "growth_methods": [
            "chronoflux_confirmed_block",
            "node_heartbeat",
            "narrative_session",
        ],
    }


def render_admin_rps_stats_html(stats: dict[str, Any] | None = None) -> str:
    """Stats panel HTML for Ned / rpS growth."""
    s = stats if stats is not None else load_rps_stats()

    def esc(x: object) -> str:
        return (
            str(x)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

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
        ("Load balance", s.get("load_balance")),
        ("Updated (unix)", s.get("updated_unix")),
    ]
    trs = "".join(
        f"<tr><th scope='row'>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in rows
    )
    return f"""
<section class="admin-card" id="{ADMIN_RPS_STATS_ID}" data-admin-rps-stats="1"
         data-nodes-online="{esc(s.get('nodes_online'))}"
         data-learning-epochs="{esc(s.get('learning_epochs'))}"
         data-chronoflux-blocks-grown="{esc(s.get('chronoflux_blocks_grown'))}"
         data-growth-score="{esc(s.get('growth_score'))}"
         data-capability-tier="{esc(s.get('capability_tier'))}"
         data-narrative-sessions="{esc(s.get('narrative_sessions'))}">
  <h2>Ned · rpAI growth (rpS)</h2>
  <p>Statistical data for the Restore Privacy Helper. Growth advances when:
  <strong>confirmed ChronoFlux blocks</strong> are sealed (admin mutators),
  <strong>project/residual nodes</strong> heartbeat, and <strong>Ned OOBE</strong>
  narrative sessions complete. Adaptive learning <em>begins</em> here — counters
  and capability tiers only; no claim of a fully trained fleet model.</p>
  <table class="admin-table" id="admin-rps-stats-table">
    <tbody>{trs}</tbody>
  </table>
</section>
"""


def render_admin_rps_page_html() -> bytes:
    """Full admin rpS stats page."""
    try:
        from admin_panel import _admin_page_shell, admin_section_top_link_html
    except ImportError:  # pragma: no cover
        from status_page.admin_panel import (  # type: ignore
            _admin_page_shell,
            admin_section_top_link_html,
        )
    stats = load_rps_stats()
    body = f"""
<div id="{ADMIN_RPS_PAGE_ID}" data-admin-page="rps" class="admin-main-inner">
  <p class="admin-lead">Restore Privacy Server computational power · admin only.</p>
  {render_admin_rps_stats_html(stats)}
  {admin_section_top_link_html()}
</div>
"""
    return _admin_page_shell(
        title="rpS · Ned — Admin",
        active="rps",
        main_html=body,
    )
