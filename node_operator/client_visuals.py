"""Graphic visuals of connected residual clients (admin-only surfaces).

Pure HTML/CSS fragment builder driven by ``list_sessions_admin`` rows.
Does not invent clients; empty list → empty-state graphic only.
"""

from __future__ import annotations

from typing import Any, Sequence


def _esc(s: Any) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def short_client_id(client_id: str, *, n: int = 10) -> str:
    """Stable short form of session hex id for visual labels."""
    cid = (client_id or "").strip()
    if len(cid) <= n:
        return cid or "—"
    return cid[:n] + "…"


def render_connected_clients_visual_html(
    sessions: Sequence[dict[str, Any]] | None,
    *,
    id_prefix: str = "op-client",
) -> str:
    """Build graphic tiles for *sessions* (already priority-ordered if desired).

    *id_prefix* scopes element ids for standalone (``op-client``) vs admin
    (``admin-node-op-client``) so both pages can embed the fragment.
    """
    rows = list(sessions or [])
    prefix = (id_prefix or "op-client").strip() or "op-client"
    css = f"""
<style id="{_esc(prefix)}-visual-css">
.{_esc(prefix)}-visuals{{
  display:flex;flex-wrap:wrap;gap:0.75rem;margin:0.75rem 0 1rem;
  min-height:4.5rem;align-items:stretch}}
.{_esc(prefix)}-visual-empty{{
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  width:100%;min-height:5.5rem;border:1px dashed #3a4d66;border-radius:12px;
  background:rgba(15,22,34,0.55);color:#8aa0b8;padding:1rem;text-align:center}}
.{_esc(prefix)}-visual-empty-icon{{
  width:3rem;height:3rem;border-radius:50%;border:2px dashed #4a6080;
  margin-bottom:0.5rem;opacity:0.7;position:relative}}
.{_esc(prefix)}-visual-empty-icon::before{{
  content:"";position:absolute;inset:0.65rem;border-radius:50%;
  border:2px solid #4a6080;opacity:0.5}}
.{_esc(prefix)}-tile{{
  display:flex;flex-direction:column;gap:0.35rem;min-width:9.5rem;max-width:14rem;
  flex:1 1 9.5rem;padding:0.75rem 0.85rem;border-radius:12px;
  border:1px solid #2a4a6a;background:linear-gradient(160deg,#152033 0%,#0f1826 100%);
  box-shadow:0 2px 8px rgba(0,0,0,0.25);position:relative;overflow:hidden}}
.{_esc(prefix)}-tile::before{{
  content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
  background:var(--client-prio-color,#22c55e)}}
.{_esc(prefix)}-tile-avatar{{
  width:2.25rem;height:2.25rem;border-radius:50%;
  background:radial-gradient(circle at 35% 30%,#5eb0ff,#1d4f91 70%);
  border:2px solid #3d7ab8;box-shadow:0 0 0 3px rgba(30,100,180,0.2);
  display:flex;align-items:center;justify-content:center;font-size:0.7rem;
  font-weight:700;color:#e8f2ff;letter-spacing:0.02em}}
.{_esc(prefix)}-tile-row{{display:flex;align-items:center;gap:0.55rem}}
.{_esc(prefix)}-tile-id{{font-family:ui-monospace,monospace;font-size:0.78rem;
  font-weight:600;word-break:break-all}}
.{_esc(prefix)}-tile-meta{{font-size:0.75rem;opacity:0.85;line-height:1.35}}
.{_esc(prefix)}-tile-prio{{
  display:inline-block;margin-top:0.15rem;padding:0.15rem 0.45rem;border-radius:999px;
  font-size:0.72rem;font-weight:700;background:rgba(34,197,94,0.15);color:#86efac}}
.{_esc(prefix)}-tile-prio.is-high{{background:rgba(59,130,246,0.2);color:#93c5fd}}
.{_esc(prefix)}-tile-prio.is-low{{background:rgba(148,163,184,0.15);color:#cbd5e1}}
.{_esc(prefix)}-hub{{
  width:100%;display:flex;align-items:center;justify-content:center;gap:0.5rem;
  margin-bottom:0.35rem;font-size:0.72rem;opacity:0.7}}
.{_esc(prefix)}-hub-dot{{
  width:0.55rem;height:0.55rem;border-radius:50%;background:#22c55e;
  box-shadow:0 0 8px #22c55e}}
</style>
"""
    if not rows:
        return (
            css
            + f'<div class="{_esc(prefix)}-visuals" id="{_esc(prefix)}-visuals" '
            f'data-client-visuals="1" data-client-count="0">'
            f'<div class="{_esc(prefix)}-visual-empty" id="{_esc(prefix)}-visual-empty" '
            f'data-client-visual-empty="1" role="status">'
            f'<div class="{_esc(prefix)}-visual-empty-icon" aria-hidden="true"></div>'
            f"<p><strong>No connected clients</strong></p>"
            f"<p>When clients residual-connect, each appears here as a tile.</p>"
            f"</div></div>"
        )

    # Priority band for color accent
    prios = [int(s.get("priority") or 0) for s in rows]
    max_p = max(prios) if prios else 0
    min_p = min(prios) if prios else 0

    tiles: list[str] = []
    for i, s in enumerate(rows):
        cid = str(s.get("client_id") or "")
        short = short_client_id(cid)
        prio = int(s.get("priority") or 0)
        vpn = str(s.get("vpn_ip") or "—")
        addr = str(s.get("client_addr") or "—")
        # Avatar initials from hex
        initials = (cid[:2] or "??").upper()
        prio_cls = "is-high" if max_p > min_p and prio >= max_p else (
            "is-low" if max_p > min_p and prio <= min_p else ""
        )
        # Green → amber → blue by relative priority
        if max_p > min_p:
            t = (prio - min_p) / float(max_p - min_p)
            # low gray-green, high blue
            r = int(34 + (59 - 34) * t)
            g = int(197 + (130 - 197) * t)
            b = int(94 + (246 - 94) * t)
            color = f"rgb({r},{g},{b})"
        else:
            color = "#22c55e"
        tid = f"{prefix}-tile-{i}"
        tiles.append(
            f'<article class="{_esc(prefix)}-tile" id="{_esc(tid)}" '
            f'data-client-tile="1" data-client-id="{_esc(cid)}" '
            f'data-client-priority="{prio}" data-client-vpn-ip="{_esc(vpn)}" '
            f'style="--client-prio-color:{color}">'
            f'<div class="{_esc(prefix)}-tile-row">'
            f'<div class="{_esc(prefix)}-tile-avatar" aria-hidden="true">{_esc(initials)}</div>'
            f'<div class="{_esc(prefix)}-tile-id" title="{_esc(cid)}">{_esc(short)}</div>'
            f"</div>"
            f'<div class="{_esc(prefix)}-tile-meta">'
            f"<div>VPN <code>{_esc(vpn)}</code></div>"
            f"<div>Addr <code>{_esc(addr)}</code></div>"
            f'<span class="{_esc(prefix)}-tile-prio {_esc(prio_cls)}">Priority {prio}</span>'
            f"</div>"
            f"</article>"
        )

    hub = (
        f'<div class="{_esc(prefix)}-hub" id="{_esc(prefix)}-visual-hub" data-client-hub="1">'
        f'<span class="{_esc(prefix)}-hub-dot" aria-hidden="true"></span>'
        f"<span>{len(rows)} connected client(s) · higher priority left</span>"
        f"</div>"
    )
    return (
        css
        + f'<div class="{_esc(prefix)}-visuals" id="{_esc(prefix)}-visuals" '
        f'data-client-visuals="1" data-client-count="{len(rows)}">'
        + hub
        + "".join(tiles)
        + "</div>"
    )
