"""Local HTTP GUI shell for the node operator (works without Tk on Mac)."""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

if TYPE_CHECKING:
    from node.operator_admin import NodeOperatorController


def render_operator_page(ctrl: "NodeOperatorController", *, flash: str = "") -> str:
    st = ctrl.get_state()
    sessions = ctrl.list_sessions_admin()
    prio_map = ctrl.priority.as_dict()
    flash_html = (
        f'<p class="flash" id="op-flash">{html.escape(flash)}</p>' if flash else ""
    )
    sess_rows = []
    for s in sessions:
        cid = html.escape(s["client_id"])
        sess_rows.append(
            "<tr>"
            f"<td><code>{cid}</code></td>"
            f"<td>{html.escape(str(s.get('vpn_ip') or ''))}</td>"
            f"<td>{html.escape(str(s.get('client_addr') or ''))}</td>"
            f"<td>{int(s.get('priority') or 0)}</td>"
            "</tr>"
        )
    table = (
        "\n".join(sess_rows)
        if sess_rows
        else '<tr id="op-sessions-empty"><td colspan="4">No connected clients</td></tr>'
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Restore Privacy — Node Operator</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#0b0f14;color:#e8eef5}}
header{{padding:1rem 1.25rem;border-bottom:1px solid #243044;background:#121a24}}
h1{{margin:0;font-size:1.15rem;letter-spacing:0.04em}}
.tag{{opacity:0.75;font-size:0.85rem;margin-top:0.25rem}}
main{{padding:1rem 1.25rem;max-width:52rem}}
.card{{background:#151d28;border:1px solid #2a3a50;border-radius:10px;padding:1rem;margin:0 0 1rem}}
label{{display:block;margin:0.4rem 0 0.15rem;font-size:0.85rem;opacity:0.9}}
input,select,button,textarea{{font:inherit}}
input,select,textarea{{width:100%;max-width:28rem;box-sizing:border-box;padding:0.4rem 0.5rem;
  border-radius:6px;border:1px solid #3a4d66;background:#0d141e;color:#e8eef5}}
button{{margin:0.35rem 0.35rem 0 0;padding:0.45rem 0.85rem;border-radius:8px;border:0;
  background:#1d6fd8;color:#fff;cursor:pointer;font-weight:600}}
button.secondary{{background:#2a3a50}}
button.danger{{background:#8b1e1e}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
th,td{{border:1px solid #2a3a50;padding:0.35rem 0.45rem;text-align:left;vertical-align:top}}
th{{background:#1a2433}}
.flash{{background:#14301f;color:#9ae6b4;padding:0.5rem 0.75rem;border-radius:8px}}
.muted{{opacity:0.75;font-size:0.85rem}}
code{{font-size:0.8rem}}
</style>
</head><body>
<header>
  <h1 id="op-app-title">Restore Privacy — Node Operator</h1>
  <p class="tag" id="op-app-subtitle">This Mac as residual node host · admin only · public status stays title-only</p>
</header>
<main id="op-main">
{flash_html}
<section class="card" id="op-node-state" data-node-state="{html.escape(st.state)}">
  <h2>Local node stack</h2>
  <p id="op-state-line"><strong>State:</strong> {html.escape(st.state)}
    · <strong>Mode:</strong> {html.escape(st.mode)}
    · <strong>PID:</strong> {html.escape(str(st.pid or '—'))}</p>
  <p class="muted" id="op-state-detail">{html.escape(st.detail or '')}</p>
  <form method="post" action="/op/start" id="op-start-form">
    <label for="mode">Start mode</label>
    <select name="mode" id="mode">
      <option value="lab" selected>lab (Mac-honest: sessions + admin, no Linux TUN)</option>
      <option value="full">full (spawn python -m node; needs Linux TUN)</option>
    </select>
    <button type="submit" id="op-start-btn">Start local node</button>
  </form>
  <form method="post" action="/op/stop" id="op-stop-form" style="display:inline">
    <button type="submit" class="danger" id="op-stop-btn">Stop local node</button>
  </form>
</section>

<section class="card" id="op-residual-connect" data-residual-connect="1">
  <h2>Residual connect (test dial)</h2>
  <p class="muted" id="op-residual-blurb">
    Run the shipped client residual <strong>HELLO</strong> from this Mac to a live catalog peer.
    Default for testing: <strong>Iceland (IS)</strong> <code>82.221.101.241:44044</code>.
    This is residual crypto connect — not full system VPN TUN on macOS.
  </p>
  <p id="op-residual-status"><strong>Residual:</strong>
    {html.escape(str(ctrl.residual_connect_status().get('state') or 'idle'))}
    · peer={html.escape(str(ctrl.residual_connect_status().get('peer') or '—'))}
    · vpn_ip={html.escape(str(ctrl.residual_connect_status().get('vpn_ip') or '—'))}
  </p>
  <form method="post" action="/op/connect-peer" id="op-connect-peer-form">
    <label for="peer">Catalog peer</label>
    <select name="peer" id="peer">
      <option value="IS" selected>Iceland (IS) — 82.221.101.241</option>
      <option value="DE">Germany (DE) — 178.105.187.178</option>
    </select>
    <button type="submit" id="op-connect-is-btn" name="peer" value="IS">Connect to Iceland</button>
    <button type="submit" class="secondary" id="op-connect-de-btn" formaction="/op/connect-peer" name="peer" value="DE">Connect to Germany</button>
  </form>
  <form method="post" action="/op/disconnect-residual" id="op-disconnect-residual-form" style="margin-top:0.5rem">
    <button type="submit" class="danger" id="op-disconnect-residual-btn">Disconnect residual</button>
  </form>
</section>

<section class="card" id="op-sessions">
  <h2>Connected clients (admin)</h2>
  <p class="muted">Ordered by priority (higher first). Not published on public /status.</p>
  <table id="op-sessions-table">
    <thead><tr><th>Client id</th><th>VPN IP</th><th>Addr</th><th>Priority</th></tr></thead>
    <tbody>
{table}
    </tbody>
  </table>
  <form method="post" action="/op/lab-session" id="op-lab-session-form">
    <p class="muted">Lab: inject a synthetic session for admin testing</p>
    <button type="submit" class="secondary" id="op-lab-session-btn">Add lab session</button>
  </form>
</section>

<section class="card" id="op-priority">
  <h2>Prioritise clients</h2>
  <form method="post" action="/op/priority" id="op-priority-form">
    <label for="client_id">Client id (session hex)</label>
    <input id="client_id" name="client_id" required placeholder="session hex id"/>
    <label for="priority">Priority (higher = preferred under contention)</label>
    <input id="priority" name="priority" type="number" value="10" required/>
    <button type="submit" id="op-priority-btn">Set priority</button>
  </form>
  <p class="muted">Stored priorities: <code id="op-priority-map">{html.escape(json.dumps(prio_map))}</code></p>
</section>

<section class="card" id="op-update-push">
  <h2>Push update to clients</h2>
  <form method="post" action="/op/push-update" id="op-push-form">
    <label for="version">Version</label>
    <input id="version" name="version" required placeholder="0.5.9"/>
    <label for="url">Download / notes URL (optional)</label>
    <input id="url" name="url" placeholder="https://restoreprivacy.online/"/>
    <label for="message">Message (optional)</label>
    <input id="message" name="message" placeholder="Please upgrade"/>
    <label for="target_client_id">Target client id (empty = all connected)</label>
    <input id="target_client_id" name="target_client_id" placeholder=""/>
    <button type="submit" id="op-push-btn">Push update</button>
  </form>
</section>
</main>
</body></html>
"""


def handle_operator_post(
    ctrl: "NodeOperatorController",
    path: str,
    body: bytes,
) -> tuple[int, str]:
    """Process GUI form POST; returns (status, flash message)."""
    form = {
        k: (v[0] if v else "")
        for k, v in parse_qs(body.decode("utf-8", "replace")).items()
    }
    if path in ("/op/start", "/op/start/"):
        mode = (form.get("mode") or "lab").strip()
        st = ctrl.start(mode=mode)
        return 200, f"Start → {st.state} ({st.mode}): {st.detail}"
    if path in ("/op/stop", "/op/stop/"):
        st = ctrl.stop()
        return 200, f"Stop → {st.state}"
    if path in ("/op/lab-session", "/op/lab-session/"):
        row = ctrl.inject_lab_session()
        return 200, f"Lab session {row['client_id'][:16]}…"
    if path in ("/op/priority", "/op/priority/"):
        cid = (form.get("client_id") or "").strip()
        try:
            prio = int(form.get("priority") or "0")
        except ValueError:
            return 400, "priority must be an integer"
        try:
            r = ctrl.set_client_priority(cid, prio)
        except ValueError as exc:
            return 400, str(exc)
        return 200, f"Priority {r['client_id'][:16]}… = {r['priority']}"
    if path in ("/op/push-update", "/op/push-update/"):
        r = ctrl.push_update(
            version=form.get("version") or "",
            url=form.get("url") or "",
            message=form.get("message") or "",
            target_client_id=form.get("target_client_id") or "",
        )
        if not r.get("ok"):
            return 400, str(r.get("error") or "push failed")
        return 200, f"Pushed to {r.get('count')} target(s): {r.get('delivered_to')}"
    if path in ("/op/connect-peer", "/op/connect-peer/"):
        peer = (form.get("peer") or "IS").strip().upper() or "IS"
        r = ctrl.connect_residual_peer(peer=peer, timeout=15.0)
        if r.get("ok"):
            return (
                200,
                f"Connected residual to {r.get('peer')} ({r.get('host')}) "
                f"vpn_ip={r.get('vpn_ip')} — {r.get('message')}",
            )
        err = r.get("error") or r.get("message") or "connect failed"
        return 400, f"Connect to {peer} failed: {err}"
    if path in ("/op/disconnect-residual", "/op/disconnect-residual/"):
        ctrl.disconnect_residual()
        return 200, "Residual disconnected"
    return 404, "unknown action"
