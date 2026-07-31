"""Local HTTP GUI shell for the node operator (works without Tk on Mac)."""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

if TYPE_CHECKING:
    from node.operator_admin import NodeOperatorController


def render_operator_page(ctrl: "NodeOperatorController", *, flash: str = "") -> str:
    from node_operator.client_visuals import render_connected_clients_visual_html
    from node_operator.update_delivery import (
        build_update_delivery_matrix,
        render_update_delivery_matrix_html,
    )

    st = ctrl.get_state()
    sessions = ctrl.list_sessions_admin()
    prio_map = ctrl.priority.as_dict()
    catalog_ver = ctrl.catalog_version_default()
    inv = ctrl.list_local_packages(version=catalog_ver)
    flash_html = (
        f'<p class="flash" id="op-flash">{html.escape(flash)}</p>' if flash else ""
    )
    clients_visual = render_connected_clients_visual_html(
        sessions,
        id_prefix="op-client",
        update_push={
            "form_action": "/op/push-update",
            "version": catalog_ver,
            "url": "https://restoreprivacy.online/",
            "message": "",
            "hidden_fields": {},
        },
    )
    matrix = build_update_delivery_matrix(
        sessions=sessions,
        packages=inv.get("packages") or [],
        catalog_version=catalog_ver,
    )
    delivery_html = render_update_delivery_matrix_html(
        matrix, id_prefix="op-delivery"
    )
    sess_rows = []
    for s in sessions:
        cid = html.escape(s["client_id"])
        ver_raw = str(s.get("product_version") or "").strip()
        ver_disp = ver_raw if ver_raw else "unknown"
        ver_attr = html.escape(ver_raw)
        unknown_attr = ' data-client-version-unknown="1"' if not ver_raw else ""
        sess_rows.append(
            "<tr>"
            f"<td><code>{cid}</code></td>"
            f'<td data-client-version="{ver_attr}"{unknown_attr}>'
            f"<code>{html.escape(ver_disp)}</code></td>"
            f"<td>{html.escape(str(s.get('vpn_ip') or ''))}</td>"
            f"<td>{html.escape(str(s.get('client_addr') or ''))}</td>"
            f"<td>{int(s.get('priority') or 0)}</td>"
            "</tr>"
        )
    table = (
        "\n".join(sess_rows)
        if sess_rows
        else '<tr id="op-sessions-empty"><td colspan="5">No connected clients</td></tr>'
    )
    pkg_rows = []
    for p in inv.get("packages") or []:
        present = "yes" if p.get("present") else "no"
        staged = "yes" if p.get("staged") else "no"
        size = int(p.get("size") or 0)
        size_s = f"{size // 1_000_000} MB" if size >= 1_000_000 else (f"{size} B" if size else "—")
        pkg_rows.append(
            "<tr>"
            f"<td>{html.escape(str(p.get('platform') or ''))}</td>"
            f"<td><code>{html.escape(str(p.get('filename') or ''))}</code></td>"
            f"<td data-present=\"{present}\">{present}</td>"
            f"<td data-staged=\"{staged}\">{staged}</td>"
            f"<td>{html.escape(size_s)}</td>"
            "</tr>"
        )
    pkg_table = (
        "\n".join(pkg_rows)
        if pkg_rows
        else '<tr id="op-packages-empty"><td colspan="5">No catalog packages listed</td></tr>'
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
  <p class="muted">Graphic tiles ordered by priority (higher first). Not on public /status.</p>
  {clients_visual}
  <details id="op-sessions-table-details" class="muted">
    <summary>Table detail</summary>
  <table id="op-sessions-table">
    <thead><tr><th>Client id</th><th>Version</th><th>VPN IP</th><th>Addr</th><th>Priority</th></tr></thead>
    <tbody>
{table}
    </tbody>
  </table>
  </details>
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

<section class="card" id="op-deploy-packages" data-deploy-packages="1" data-helsinki-upload="1">
  <h2>Upload packages to host</h2>
  <p class="muted" id="op-deploy-blurb">
    After you build monopin installers, <strong>stage and upload</strong> them to the Helsinki
    paid store host from this GUI — no terminal required. Uses
    <code>scripts/host_paid_assets_vps.py</code> (SSH key needed for a real upload).
    Prefer <strong>Dry-run</strong> first; use <strong>Allow missing platforms</strong> for partial ships.
  </p>
  <p id="op-deploy-inventory">
    <strong>Catalog:</strong> <code id="op-catalog-version">{html.escape(catalog_ver)}</code>
    · present {int(inv.get('present_count') or 0)}/{int(inv.get('total') or 0)}
    · staged {int(inv.get('staged_count') or 0)}/{int(inv.get('total') or 0)}
  </p>
  <table id="op-packages-table">
    <thead><tr><th>Platform</th><th>Filename</th><th>Local</th><th>Staged</th><th>Size</th></tr></thead>
    <tbody>
{pkg_table}
    </tbody>
  </table>
  <form method="post" action="/op/upload-packages" id="op-upload-packages-form"
        data-helsinki-upload="1">
    <label for="deploy_version">Monopin version</label>
    <input id="deploy_version" name="version" required value="{html.escape(catalog_ver)}"
           placeholder="{html.escape(catalog_ver)}"/>
    <label><input type="checkbox" name="stage" value="1" checked id="op-deploy-stage"/> Stage local assets</label>
    <label><input type="checkbox" name="upload" value="1" checked id="op-deploy-upload"/> Upload to Helsinki paid_assets</label>
    <label><input type="checkbox" name="allow_missing" value="1" checked id="op-deploy-allow-missing"/> Allow missing platforms</label>
    <label><input type="checkbox" name="force" value="1" id="op-deploy-force"/> Force re-upload</label>
    <label><input type="checkbox" name="dry_run" value="1" id="op-deploy-dry-run"/> Dry-run (no SSH write)</label>
    <label><input type="checkbox" name="install_serve" value="1" id="op-deploy-install-serve"/> Restart store serve</label>
    <button type="submit" id="op-upload-packages-btn" class="primary-upload">
      Upload packages to Helsinki
    </button>
  </form>
  <form method="post" action="/op/list-packages" id="op-list-packages-form" style="margin-top:0.4rem">
    <input type="hidden" name="version" value="{html.escape(catalog_ver)}"/>
    <button type="submit" class="secondary" id="op-list-packages-btn">Refresh package inventory</button>
  </form>
</section>

<section class="card" id="op-update-push" data-push-update="1">
  <h2>Push update to clients</h2>
  <p class="muted" id="op-push-blurb">
    Residual <strong>UPDATE_PUSH</strong> directive (version/url/message) to connected clients.
    Upload packages above first so the download URL resolves. Clients apply when Settings
    <strong>CHECK BREADCRUMBS</strong> is on.
  </p>
  <form method="post" action="/op/push-update" id="op-push-form">
    <label for="version">Update directive version</label>
    <input id="version" name="version" required placeholder="{html.escape(catalog_ver)}" value="{html.escape(catalog_ver)}"/>
    <label for="url">Download / notes URL (optional)</label>
    <input id="url" name="url" placeholder="https://restoreprivacy.online/"/>
    <label for="message">Message (optional)</label>
    <input id="message" name="message" placeholder="Please upgrade"/>
    <label for="target_client_id">Target client id (empty = all connected)</label>
    <input id="target_client_id" name="target_client_id" placeholder=""/>
    <button type="submit" id="op-push-btn">Push update to clients</button>
  </form>
</section>

<section class="card" id="op-delivery-section">
  {delivery_html}
</section>
</main>
</body></html>
<style>
button.primary-upload,#op-upload-packages-btn{{
  background:#0d9488!important;font-size:1rem;padding:0.65rem 1.1rem!important;
  margin-top:0.5rem}}
</style>
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
    if path in ("/op/list-packages", "/op/list-packages/"):
        ver = (form.get("version") or "").strip() or ctrl.catalog_version_default()
        inv = ctrl.list_local_packages(version=ver)
        if not inv.get("ok"):
            return 400, str(inv.get("error") or "inventory failed")
        return (
            200,
            f"Inventory {inv.get('version')}: "
            f"present {inv.get('present_count')}/{inv.get('total')}, "
            f"staged {inv.get('staged_count')}/{inv.get('total')}",
        )
    if path in ("/op/upload-packages", "/op/upload-packages/"):
        ver = (form.get("version") or "").strip() or ctrl.catalog_version_default()
        stage = form.get("stage") == "1"
        upload = form.get("upload") == "1"
        dry_run = form.get("dry_run") == "1"
        force = form.get("force") == "1"
        allow_missing = form.get("allow_missing") == "1"
        install_serve = form.get("install_serve") == "1"
        r = ctrl.upload_catalog_packages(
            version=ver,
            stage=stage,
            upload=upload,
            dry_run=dry_run,
            force=force,
            allow_missing=allow_missing,
            install_serve=install_serve,
        )
        if not r.get("ok"):
            return 400, str(r.get("error") or "deploy failed")
        parts = [
            f"Deploy {r.get('version')}",
            f"stage={'yes' if stage else 'no'}",
            f"upload={'yes' if upload else 'no'}",
            f"dry_run={'yes' if dry_run else 'no'}",
        ]
        if r.get("staged"):
            parts.append(f"staged={len(r['staged'])}")
        if r.get("upload_code") is not None:
            parts.append(f"upload_code={r['upload_code']}")
        return 200, " · ".join(parts)
    return 404, "unknown action"
