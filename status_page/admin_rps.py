"""Admin rpS page — Restore Privacy Server computational power / Ned growth stats.

Route ``/admin/rps`` — statistical growth of the rpAI (Ned) helper as nodes join
the load-balanced server pool. Admin auth required.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ADMIN_RPS_PATH = "/admin/rps"
ADMIN_RPS_PAGE_ID = "admin-rps-page"
ADMIN_RPS_STATS_ID = "admin-rps-stats"

# Default seed stats (adaptive learning begin surface — not trained weights).
_DEFAULT_STATS: dict[str, Any] = {
    "product": "Ned · rpAI · Restore Privacy Helper",
    "mission": "adaptive learning for the good of all humanity",
    "rps_label": "rpS — Restore Privacy Server computational power",
    "nodes_online": 0,
    "nodes_total_seen": 0,
    "learning_epochs": 0,
    "narrative_sessions": 0,
    "load_balance": "round-robin across available project servers; expands as nodes join",
    "updated_unix": 0,
}


def rps_stats_path() -> Path:
    """Durable stats file under payment/data dir when available, else status_page/data."""
    try:
        from payments import payment_data_dir

        base = Path(payment_data_dir())
    except Exception:
        base = Path(__file__).resolve().parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "rps_ned_stats.json"


def load_rps_stats() -> dict[str, Any]:
    """Load rpS growth stats (real file path; seed defaults if missing)."""
    path = rps_stats_path()
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                out = dict(_DEFAULT_STATS)
                out.update(raw)
                return out
        except (OSError, json.JSONDecodeError):
            pass
    out = dict(_DEFAULT_STATS)
    out["updated_unix"] = int(time.time())
    return out


def save_rps_stats(stats: dict[str, Any]) -> dict[str, Any]:
    """Persist stats dict; returns written snapshot."""
    out = dict(_DEFAULT_STATS)
    out.update(stats or {})
    out["updated_unix"] = int(time.time())
    path = rps_stats_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def record_rps_heartbeat(*, nodes_online: int | None = None) -> dict[str, Any]:
    """Increment growth counters (called when a project server reports in)."""
    s = load_rps_stats()
    if nodes_online is not None:
        s["nodes_online"] = max(0, int(nodes_online))
        s["nodes_total_seen"] = max(int(s.get("nodes_total_seen") or 0), int(nodes_online))
    s["learning_epochs"] = int(s.get("learning_epochs") or 0) + 1
    return save_rps_stats(s)


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
        ("Load balance", s.get("load_balance")),
        ("Updated (unix)", s.get("updated_unix")),
    ]
    trs = "".join(
        f"<tr><th scope='row'>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in rows
    )
    return f"""
<section class="admin-card" id="{ADMIN_RPS_STATS_ID}" data-admin-rps-stats="1"
         data-nodes-online="{esc(s.get('nodes_online'))}"
         data-learning-epochs="{esc(s.get('learning_epochs'))}">
  <h2>Ned · rpAI growth (rpS)</h2>
  <p>Statistical data for the Restore Privacy Helper as project servers join the
  load-balanced pool. Adaptive learning <em>begins</em> here — no claim of a fully
  trained fleet model in this surface.</p>
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
