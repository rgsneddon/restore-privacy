"""Graphic visuals of connected residual clients (admin-only surfaces).

ChronofluxAtlas-style **pyramid of animated blob tiles** driven by
``list_sessions_admin`` rows. Does not invent clients; empty list → empty-state
only. Per-client residual UPDATE_PUSH forms are product-disabled (update_push=None).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


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


def product_version_label(session: Mapping[str, Any] | None) -> tuple[str, str]:
    """Return (raw_version, display_label) for a session admin row.

    Empty/missing product_version → honest ``unknown`` display (never invent monopin).
    """
    raw = ""
    if session is not None:
        raw = str(
            session.get("product_version")
            or session.get("client_version")
            or ""
        ).strip()
    if raw:
        return raw, raw
    return "", "unknown"


def pyramid_row_sizes(n: int) -> list[int]:
    """Row widths for a descending pyramid: 1 at apex, wider toward base.

    Higher-priority sessions (list head) fill the apex first. Empty → [].
    """
    count = max(0, int(n))
    if count <= 0:
        return []
    rows: list[int] = []
    remaining = count
    width = 1
    while remaining > 0:
        take = min(width, remaining)
        rows.append(take)
        remaining -= take
        width += 1
    return rows


def _blob_palette(row_index: int, row_count: int, t_prio: float) -> tuple[str, str, str]:
    """Chronoflux-like recoverability gradient: apex gold → mid cyan → base ember.

    Returns (fill_css, glow_css, accent_css).
    """
    # Base hue by pyramid depth (0 = apex)
    depth = 0.0 if row_count <= 1 else row_index / float(row_count - 1)
    # Slight priority bias within row
    d = min(1.0, max(0.0, depth * 0.85 + (1.0 - t_prio) * 0.15))
    if d < 0.33:
        # Gold / yellow (high recoverability apex)
        u = d / 0.33
        r = int(255 - 20 * u)
        g = int(220 - 40 * u)
        b = int(60 + 40 * u)
    elif d < 0.66:
        # Green → cyan mid band
        u = (d - 0.33) / 0.33
        r = int(80 + 20 * u)
        g = int(200 - 40 * u)
        b = int(120 + 100 * u)
    else:
        # Blue → orange ember at base
        u = (d - 0.66) / 0.34
        r = int(40 + 200 * u)
        g = int(140 - 40 * u)
        b = int(220 - 160 * u)
    fill = f"rgb({r},{g},{b})"
    glow = f"rgba({r},{g},{b},0.55)"
    accent = f"rgba({min(255, r + 40)},{min(255, g + 40)},{min(255, b + 40)},0.9)"
    return fill, glow, accent


def render_connected_clients_visual_html(
    sessions: Sequence[dict[str, Any]] | None,
    *,
    id_prefix: str = "op-client",
    update_push: Mapping[str, Any] | None = None,
) -> str:
    """Build Chronoflux-style pyramid of blob tiles for *sessions*.

    *id_prefix* scopes element ids for standalone (``op-client``) vs admin
    (``admin-node-op-client``) so both pages can embed the fragment.

    *update_push* is ignored/removed for product; leave None:
      form_action (required), version (directive monopin), url, message,
      hidden_fields (dict of extra form fields, e.g. admin action/node).
    """
    rows = list(sessions or [])
    prefix = (id_prefix or "op-client").strip() or "op-client"
    push = dict(update_push or {}) if update_push else None
    push_action = str((push or {}).get("form_action") or "").strip() if push else ""
    can_push = bool(push and push_action)
    p = _esc(prefix)

    css = f"""
<style id="{p}-visual-css">
.{p}-visuals{{
  margin:0.75rem 0 1rem;min-height:5rem;
  --pyramid-bg0:#050a14;--pyramid-bg1:#0a1628;--pyramid-grid:rgba(80,120,180,0.08);
  --pyramid-line:rgba(160,100,255,0.35)}}
.{p}-visual-empty{{
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  width:100%;min-height:5.5rem;border:1px dashed #3a4d66;border-radius:12px;
  background:rgba(15,22,34,0.55);color:#8aa0b8;padding:1rem;text-align:center}}
.{p}-visual-empty-icon{{
  width:3rem;height:3rem;border-radius:50%;border:2px dashed #4a6080;
  margin-bottom:0.5rem;opacity:0.7;position:relative}}
.{p}-visual-empty-icon::before{{
  content:"";position:absolute;inset:0.65rem;border-radius:50%;
  border:2px solid #4a6080;opacity:0.5}}
.{p}-hub{{
  width:100%;display:flex;align-items:center;justify-content:center;gap:0.5rem;
  margin-bottom:0.5rem;font-size:0.72rem;opacity:0.75}}
.{p}-hub-dot{{
  width:0.55rem;height:0.55rem;border-radius:50%;background:#22c55e;
  box-shadow:0 0 8px #22c55e;animation:{p}-hub-pulse 2s ease-in-out infinite}}
.{p}-pyramid{{
  position:relative;display:flex;flex-direction:column;align-items:center;
  gap:0.55rem;padding:1.25rem 0.75rem 1.5rem;border-radius:16px;
  background:
    radial-gradient(ellipse 70% 55% at 50% 18%,rgba(255,210,80,0.12),transparent 55%),
    radial-gradient(ellipse 90% 70% at 50% 100%,rgba(120,60,220,0.1),transparent 60%),
    linear-gradient(180deg,var(--pyramid-bg1) 0%,var(--pyramid-bg0) 100%);
  border:1px solid rgba(60,90,140,0.35);overflow:hidden;
  box-shadow:inset 0 0 60px rgba(0,20,40,0.5)}}
.{p}-pyramid::before{{
  content:"";position:absolute;inset:0;pointer-events:none;opacity:0.45;
  background-image:
    linear-gradient(var(--pyramid-grid) 1px,transparent 1px),
    linear-gradient(90deg,var(--pyramid-grid) 1px,transparent 1px);
  background-size:28px 28px;
  mask-image:radial-gradient(ellipse 80% 70% at 50% 55%,#000 20%,transparent 75%)}}
.{p}-pyramid-spine{{
  position:absolute;left:50%;top:8%;bottom:10%;width:2px;margin-left:-1px;
  background:linear-gradient(180deg,
    rgba(255,210,80,0.55),rgba(160,100,255,0.45),rgba(255,120,60,0.25));
  opacity:0.55;pointer-events:none;z-index:0;
  animation:{p}-spine-shimmer 4s ease-in-out infinite}}
.{p}-pyramid-row{{
  position:relative;z-index:1;display:flex;flex-wrap:nowrap;justify-content:center;
  align-items:flex-start;gap:0.55rem;width:100%;
  max-width:calc(100% - 0.5rem)}}
.{p}-pyramid-row[data-pyramid-row="0"]{{z-index:3}}
.{p}-blob,.{p}-tile{{
  /* organic Chronoflux node (blob), not a rectangular card */
  position:relative;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:0.2rem;
  width:5.4rem;min-width:5.4rem;max-width:5.4rem;height:5.4rem;
  padding:0.45rem 0.35rem 0.4rem;margin:0;
  border:1.5px solid var(--blob-accent,#fde68a);
  border-radius:58% 42% 55% 45% / 48% 52% 48% 52%;
  background:
    radial-gradient(circle at 32% 28%,rgba(255,255,255,0.55),transparent 42%),
    radial-gradient(circle at 50% 55%,var(--blob-fill,#fbbf24),#0a1220 78%);
  box-shadow:
    0 0 0 1px rgba(0,0,0,0.35),
    0 0 14px var(--blob-glow,rgba(251,191,36,0.5)),
    0 4px 12px rgba(0,0,0,0.45);
  color:#f8fafc;text-align:center;font:inherit;cursor:default;
  overflow:hidden;
  animation:
    {p}-blob-float 3.2s ease-in-out infinite,
    {p}-blob-pulse 2.6s ease-in-out infinite,
    {p}-blob-morph 7s ease-in-out infinite;
  animation-delay:var(--blob-delay,0s),var(--blob-delay,0s),var(--blob-delay,0s);
  transform-origin:center center}}
.{p}-blob.is-pushable{{cursor:pointer}}
.{p}-blob.is-pushable:hover{{
  border-color:#fff;
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.25),
    0 0 22px var(--blob-glow),
    0 0 36px var(--blob-glow),
    0 6px 16px rgba(0,0,0,0.5);
  filter:brightness(1.12)}}
.{p}-blob.is-pushable:focus-within{{
  outline:2px solid #a78bfa;outline-offset:3px}}
.{p}-blob-core{{
  width:1.55rem;height:1.55rem;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-size:0.62rem;font-weight:800;letter-spacing:0.02em;color:#0b1220;
  background:radial-gradient(circle at 35% 30%,#fff,var(--blob-fill,#fbbf24));
  box-shadow:0 0 8px var(--blob-glow);flex-shrink:0}}
.{p}-blob-id{{
  font-family:ui-monospace,monospace;font-size:0.58rem;font-weight:700;
  max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  opacity:0.95;text-shadow:0 1px 2px rgba(0,0,0,0.8)}}
.{p}-blob-meta{{
  font-size:0.52rem;line-height:1.2;opacity:0.88;max-width:100%;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  text-shadow:0 1px 2px rgba(0,0,0,0.75)}}
.{p}-tile-version,.{p}-blob-version{{
  display:inline-block;margin-top:0.05rem;padding:0.05rem 0.28rem;border-radius:999px;
  font-size:0.52rem;font-weight:700;font-family:ui-monospace,monospace;
  background:rgba(0,0,0,0.35);color:#e2e8f0;max-width:100%;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.{p}-tile-version.is-unknown,.{p}-blob-version.is-unknown{{
  font-family:inherit;font-weight:600;opacity:0.8}}
.{p}-tile-prio,.{p}-blob-prio{{
  position:absolute;top:0.2rem;right:0.25rem;
  font-size:0.48rem;font-weight:800;opacity:0.85;
  background:rgba(0,0,0,0.4);padding:0.05rem 0.22rem;border-radius:999px}}
.{p}-tile-update,.{p}-blob-update{{
  position:absolute;left:50%;bottom:0.15rem;transform:translateX(-50%);
  margin:0;padding:0.12rem 0.35rem;border:0;border-radius:999px;
  background:rgba(15,23,42,0.85);color:#e2e8f0;font-size:0.48rem;font-weight:700;
  cursor:pointer;white-space:nowrap;max-width:92%;
  box-shadow:0 1px 4px rgba(0,0,0,0.4)}}
.{p}-blob-update:hover{{background:#1d6fd8;color:#fff}}
/* hide dense meta on tiny blobs — version chip remains */
.{p}-blob-vpn{{display:none}}
@keyframes {p}-blob-float{{
  0%,100%{{transform:translateY(0)}}
  50%{{transform:translateY(-5px)}}}}
@keyframes {p}-blob-pulse{{
  0%,100%{{box-shadow:0 0 0 1px rgba(0,0,0,0.35),0 0 12px var(--blob-glow),0 4px 12px rgba(0,0,0,0.45)}}
  50%{{box-shadow:0 0 0 1px rgba(255,255,255,0.15),0 0 22px var(--blob-glow),0 0 36px var(--blob-glow),0 4px 14px rgba(0,0,0,0.5)}}}}
@keyframes {p}-blob-morph{{
  0%,100%{{border-radius:58% 42% 55% 45% / 48% 52% 48% 52%}}
  33%{{border-radius:45% 55% 48% 52% / 55% 45% 55% 45%}}
  66%{{border-radius:52% 48% 42% 58% / 45% 55% 48% 52%}}}}
@keyframes {p}-hub-pulse{{
  0%,100%{{opacity:1;transform:scale(1)}}
  50%{{opacity:0.55;transform:scale(1.25)}}}}
@keyframes {p}-spine-shimmer{{
  0%,100%{{opacity:0.4}}
  50%{{opacity:0.75}}}}
@media (max-width:520px){{
  .{p}-blob,.{p}-tile{{width:4.6rem;min-width:4.6rem;max-width:4.6rem;height:4.6rem}}
}}
</style>
"""
    if not rows:
        return (
            css
            + f'<div class="{p}-visuals" id="{p}-visuals" '
            f'data-client-visuals="1" data-client-count="0" data-client-pyramid="0">'
            f'<div class="{p}-visual-empty" id="{p}-visual-empty" '
            f'data-client-visual-empty="1" role="status">'
            f'<div class="{p}-visual-empty-icon" aria-hidden="true"></div>'
            f"<p><strong>No connected clients</strong></p>"
            f"<p>When clients residual-connect, each appears here as a blob in the pyramid.</p>"
            f"</div></div>"
        )

    prios = [int(s.get("priority") or 0) for s in rows]
    max_p = max(prios) if prios else 0
    min_p = min(prios) if prios else 0

    push_ver = str((push or {}).get("version") or "").strip() if push else ""
    push_url = str((push or {}).get("url") or "").strip() if push else ""
    push_msg = str((push or {}).get("message") or "").strip() if push else ""
    hidden = dict((push or {}).get("hidden_fields") or {}) if push else {}

    sizes = pyramid_row_sizes(len(rows))
    # Slice sessions into pyramid rows (list order = priority order → apex first)
    packed: list[list[dict[str, Any]]] = []
    idx = 0
    for sz in sizes:
        packed.append(rows[idx : idx + sz])
        idx += sz

    pyramid_rows_html: list[str] = []
    global_i = 0
    for ri, row_sessions in enumerate(packed):
        blobs: list[str] = []
        for s in row_sessions:
            cid = str(s.get("client_id") or "")
            short = short_client_id(cid)
            prio = int(s.get("priority") or 0)
            vpn = str(s.get("vpn_ip") or "—")
            addr = str(s.get("client_addr") or "—")
            ver_raw, ver_label = product_version_label(s)
            ver_unknown = not ver_raw
            initials = (cid[:2] or "??").upper()
            if max_p > min_p:
                t_prio = (prio - min_p) / float(max_p - min_p)
            else:
                t_prio = 1.0
            fill, glow, accent = _blob_palette(ri, len(packed), t_prio)
            tid = f"{prefix}-tile-{global_i}"
            delay = f"{(global_i % 8) * 0.18:.2f}s"
            ver_cls = "is-unknown" if ver_unknown else ""
            ver_attr = _esc(ver_raw)
            unknown_attr = ' data-client-version-unknown="1"' if ver_unknown else ""
            body = (
                f'<span class="{p}-blob-prio" title="Priority">{prio}</span>'
                f'<div class="{p}-blob-core" aria-hidden="true">{_esc(initials)}</div>'
                f'<div class="{p}-blob-id {_esc(prefix)}-tile-id" title="{_esc(cid)}">'
                f"{_esc(short)}</div>"
                f'<div class="{p}-blob-version {_esc(prefix)}-tile-version {_esc(ver_cls)}" '
                f'data-client-version-label="1">Version {_esc(ver_label)}</div>'
                f'<span class="{p}-blob-vpn" data-client-vpn-text="1">{_esc(vpn)}</span>'
            )
            style = (
                f"--client-prio-color:{fill};--blob-fill:{fill};"
                f"--blob-glow:{glow};--blob-accent:{accent};--blob-delay:{delay}"
            )
            tile_attrs = (
                f'id="{_esc(tid)}" data-client-tile="1" data-client-blob="1" '
                f'data-client-id="{_esc(cid)}" data-client-priority="{prio}" '
                f'data-client-vpn-ip="{_esc(vpn)}" data-client-version="{ver_attr}"'
                f'{unknown_attr} data-pyramid-row="{ri}" data-pyramid-index="{global_i}" '
                f'style="{style}"'
            )
            if can_push:
                hidden_html = "".join(
                    f'<input type="hidden" name="{_esc(k)}" value="{_esc(v)}"/>'
                    for k, v in hidden.items()
                )
                blobs.append(
                    f'<form method="post" action="{_esc(push_action)}" '
                    f'class="{p}-tile {p}-blob is-pushable" {tile_attrs} '
                    f'data-client-tile-push="1" data-client-update-target="{_esc(cid)}" '
                    f'title="{_esc(cid)} · {_esc(addr)}">'
                    f"{hidden_html}"
                    f'<input type="hidden" name="version" value="{_esc(push_ver)}"/>'
                    f'<input type="hidden" name="url" value="{_esc(push_url)}"/>'
                    f'<input type="hidden" name="message" value="{_esc(push_msg)}"/>'
                    f'<input type="hidden" name="target_client_id" value="{_esc(cid)}"/>'
                    f"{body}"
                    f'<button type="submit" class="{p}-tile-update {p}-blob-update" '
                    f'id="{_esc(tid)}-update" data-client-tile-update="1" '
                    f'title="Client update push disabled — manual Suite download only">'
                    f"Update</button>"
                    f"</form>"
                )
            else:
                blobs.append(
                    f'<article class="{p}-tile {p}-blob" {tile_attrs} '
                    f'title="{_esc(cid)} · {_esc(addr)}">'
                    f"{body}"
                    f"</article>"
                )
            global_i += 1

        pyramid_rows_html.append(
            f'<div class="{p}-pyramid-row" id="{p}-pyramid-row-{ri}" '
            f'data-pyramid-row="{ri}" data-pyramid-row-count="{len(row_sessions)}" '
            f'data-client-pyramid-row="1">'
            + "".join(blobs)
            + "</div>"
        )

    hub_extra = " · click blob to push update" if can_push else ""
    hub = (
        f'<div class="{p}-hub" id="{p}-visual-hub" data-client-hub="1">'
        f'<span class="{p}-hub-dot" aria-hidden="true"></span>'
        f"<span>{len(rows)} connected client(s) · pyramid (apex = higher priority)"
        f"{hub_extra}</span>"
        f"</div>"
    )
    pyramid = (
        f'<div class="{p}-pyramid" id="{p}-pyramid" data-client-pyramid-stack="1" '
        f'data-pyramid-rows="{len(packed)}" role="group" '
        f'aria-label="Connected clients pyramid">'
        f'<div class="{p}-pyramid-spine" data-pyramid-spine="1" aria-hidden="true"></div>'
        + "".join(pyramid_rows_html)
        + "</div>"
    )
    return (
        css
        + f'<div class="{p}-visuals" id="{p}-visuals" '
        f'data-client-visuals="1" data-client-count="{len(rows)}" '
        f'data-client-pyramid="1" data-client-tiles-pushable="{"1" if can_push else "0"}" '
        f'data-pyramid-row-sizes="{_esc(",".join(str(x) for x in sizes))}">'
        + hub
        + pyramid
        + "</div>"
    )
