"""Authenticated admin: Node Operator console (project residual + package deploy).

Embeds the same controller helpers as ``node_operator`` (inventory, upload dry-run,
priority, update-push, residual dial) behind admin auth. Public ``/status`` stays
title-only.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

# Stable admin paths / nav ids (tests + sidebar).
ADMIN_NODE_OPERATOR_PATH = "/admin/node-operator"
ADMIN_NODE_OPERATOR_POST_PATH = "/admin/node-operator/action"
ADMIN_NAV_NODE_OPERATOR_ID = "admin-nav-node-operator"
# Full-page auto-reload for Node Operator is off (operators refresh manually).
# Kept as a named constant so tests/callers can assert the feature is disabled.
ADMIN_NODE_OPERATOR_AUTO_REFRESH_SEC = 0


def monorepo_root() -> Path:
    """Repo root that contains ``node/``, ``client/``, ``node_operator/``.

    On Render, ``rootDir`` is ``status_page`` so process cwd is not the monorepo
    root — resolve from this file's parent instead of relying on PYTHONPATH.
    """
    here = Path(__file__).resolve().parent
    # status_page/admin_node_operator.py → parents[0]=status_page, [1]=repo root
    candidate = here.parent
    if (candidate / "node" / "operator_admin.py").is_file():
        return candidate
    # Fallback: cwd walk (local monorepo runs)
    cwd = Path.cwd().resolve()
    for p in (cwd, *cwd.parents):
        if (p / "node" / "operator_admin.py").is_file():
            return p
    return candidate


def ensure_monorepo_on_path() -> Path:
    """Insert monorepo root at front of ``sys.path`` so ``import node`` works."""
    root = monorepo_root()
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)
    return root


def node_operator_auto_refresh_meta(node_id: str = "") -> str:
    """Optional CSP-safe meta refresh for Node Operator (no inline script).

    Auto-refresh is **disabled** (``ADMIN_NODE_OPERATOR_AUTO_REFRESH_SEC`` ≤ 0).
    Returns an empty string so the admin page does not full-reload on a timer.
    *node_id* is accepted for API compat (selected node survives manual GET).
    """
    _ = node_id  # retained for call-site API compatibility
    sec = int(ADMIN_NODE_OPERATOR_AUTO_REFRESH_SEC)
    if sec < 1:
        return ""
    # Defensive: only emit meta if a positive interval is re-enabled later.
    nid = "".join(
        c for c in (node_id or "").strip() if c.isalnum() or c in "-_"
    )
    if nid:
        content = f"{sec};url={ADMIN_NODE_OPERATOR_PATH}?node={nid}"
    else:
        content = str(sec)
    return (
        f'<meta http-equiv="refresh" content="{content}" '
        f'id="admin-node-op-auto-refresh" '
        f'data-auto-refresh-sec="{sec}" '
        f'data-auto-refresh-node="{nid}"/>'
    )


def _esc(s: Any) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def list_operable_nodes() -> list[dict[str, Any]]:
    """Product residual + local lab + package store — not free-form external hosts.

    Built from the project’s own catalog peers and known operator targets.
    """
    nodes: list[dict[str, Any]] = [
        {
            "id": "lab",
            "code": "LAB",
            "label": "Local lab (this operator host)",
            "kind": "lab",
            "host": "127.0.0.1",
            "port": 0,
            "operable": True,
        }
    ]
    try:
        from client.multihop import product_country_catalog

        for n in product_country_catalog():
            code = str(getattr(n, "code", "") or "").strip().upper()
            if not code:
                continue
            nodes.append(
                {
                    "id": code,
                    "code": code,
                    "label": f"{getattr(n, 'name', code)} ({code})",
                    "kind": "residual",
                    "host": str(getattr(n, "host", "") or ""),
                    "port": int(getattr(n, "port", 44044) or 44044),
                    "operable": True,
                }
            )
    except Exception:  # noqa: BLE001
        nodes.extend(
            [
                {
                    "id": "IS",
                    "code": "IS",
                    "label": "Iceland (IS)",
                    "kind": "residual",
                    "host": "82.221.101.241",
                    "port": 44044,
                    "operable": True,
                },
                {
                    "id": "DE",
                    "code": "DE",
                    "label": "Germany (DE)",
                    "kind": "residual",
                    "host": "178.105.187.178",
                    "port": 44044,
                    "operable": True,
                },
            ]
        )
    # Package store (Helsinki) — deploy target the project already operates
    try:
        from payments import DEFAULT_VPS_ASSET_HOST
        host = str(DEFAULT_VPS_ASSET_HOST or "135.181.152.10").strip()
    except Exception:  # noqa: BLE001
        host = "135.181.152.10"
    nodes.append(
        {
            "id": "helsinki-store",
            "code": "HEL",
            "label": "Package store (HEL1)",
            "kind": "package_store",
            "host": host,
            "port": 0,
            "operable": True,
        }
    )
    return nodes


def resolve_operable_node(node_id: str | None) -> dict[str, Any]:
    """Return operable node dict for *node_id*, defaulting to first residual (IS)."""
    nodes = list_operable_nodes()
    want = (node_id or "").strip()
    if want:
        for n in nodes:
            if n["id"] == want or n.get("code") == want.upper():
                return dict(n)
    for n in nodes:
        if n.get("kind") == "residual" and n.get("code") == "IS":
            return dict(n)
    for n in nodes:
        if n.get("kind") == "residual":
            return dict(n)
    return dict(nodes[0]) if nodes else {"id": "lab", "code": "LAB", "kind": "lab", "host": "127.0.0.1", "operable": True}


_OPERATOR_CTRL = None


def get_operator_controller():
    """Process-wide controller so admin pages share lab sessions / inventory."""
    global _OPERATOR_CTRL

    root = ensure_monorepo_on_path()
    from node.operator_admin import NodeOperatorController

    if _OPERATOR_CTRL is None:
        _OPERATOR_CTRL = NodeOperatorController(repo_root=root)
    return _OPERATOR_CTRL


def reset_operator_controller_for_tests():
    """Drop shared controller (tests only)."""
    global _OPERATOR_CTRL
    if _OPERATOR_CTRL is not None:
        try:
            _OPERATOR_CTRL.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            _OPERATOR_CTRL.disconnect_residual()
        except Exception:  # noqa: BLE001
            pass
    _OPERATOR_CTRL = None


def render_admin_node_operator_page_html(
    *,
    selected_node: str | None = None,
    message: str = "",
    error: str = "",
) -> bytes:
    """Full admin page: node selector tabs + operator controls + package inventory."""
    try:
        from admin_panel import _admin_page_shell, _escape, admin_section_top_link_html
    except ImportError:  # pragma: no cover
        from status_page.admin_panel import (  # type: ignore
            _admin_page_shell,
            _escape,
            admin_section_top_link_html,
        )

    ensure_monorepo_on_path()
    node = resolve_operable_node(selected_node)
    nodes = list_operable_nodes()
    load_err = ""
    try:
        ctrl = get_operator_controller()
        catalog_ver = ctrl.catalog_version_default()
        inv = ctrl.list_local_packages(version=catalog_ver)
        st = ctrl.get_state()
        residual = ctrl.residual_connect_status()
        sessions = ctrl.list_sessions_admin()
        prio_map = ctrl.priority.as_dict()
    except Exception as exc:  # noqa: BLE001
        # Fail-soft: still show operable shell so admin is not a bare 500.
        load_err = f"Node Operator backend failed to load: {type(exc).__name__}: {exc}"
        catalog_ver = "1.0.0"
        inv = {"packages": [], "version": catalog_ver}
        st = {"error": load_err}
        residual = {"connected": False, "error": load_err}
        sessions = []
        prio_map = {}
        if (error or "").strip():
            error = f"{error.strip()} | {load_err}"
        else:
            error = load_err

    flash = ""
    if (message or "").strip():
        flash += (
            f'<p class="ok-msg" id="admin-node-op-flash-ok" role="status">'
            f"{_escape(message.strip())}</p>"
        )
    if (error or "").strip():
        flash += (
            f'<p class="err-msg" id="admin-node-op-flash-err" role="alert">'
            f"{_escape(error.strip())}</p>"
        )

    # Top-of-page operable node tabs
    tab_parts: list[str] = []
    for n in nodes:
        nid = _escape(n["id"])
        active = " is-active" if n["id"] == node["id"] else ""
        tab_parts.append(
            f'<a class="node-op-tab{active}" id="admin-node-tab-{nid}" '
            f'href="{ADMIN_NODE_OPERATOR_PATH}?node={nid}" '
            f'data-node-id="{nid}" data-node-kind="{_escape(n.get("kind") or "")}" '
            f'data-node-host="{_escape(n.get("host") or "")}">'
            f'{_escape(n.get("label") or nid)}</a>'
        )
    tabs_html = (
        f'<nav class="node-op-tabs" id="admin-node-op-tabs" '
        f'data-selected-node="{_escape(node["id"])}" '
        f'aria-label="Operable nodes">{"".join(tab_parts)}</nav>'
    )

    # Package inventory rows
    pkg_rows: list[str] = []
    for p in inv.get("packages") or []:
        present = "yes" if p.get("present") else "no"
        staged = "yes" if p.get("staged") else "no"
        size = int(p.get("size") or 0)
        size_s = (
            f"{size // 1_000_000} MB"
            if size >= 1_000_000
            else (f"{size} B" if size else "—")
        )
        pkg_rows.append(
            "<tr>"
            f"<td>{_escape(p.get('platform'))}</td>"
            f"<td><code>{_escape(p.get('filename'))}</code></td>"
            f"<td data-present=\"{present}\">{present}</td>"
            f"<td data-staged=\"{staged}\">{staged}</td>"
            f"<td>{_escape(size_s)}</td>"
            "</tr>"
        )
    pkg_table = (
        "\n".join(pkg_rows)
        if pkg_rows
        else '<tr id="admin-node-op-packages-empty"><td colspan="5">No packages listed</td></tr>'
    )

    ensure_monorepo_on_path()
    try:
        from node_operator.client_visuals import render_connected_clients_visual_html

        clients_visual = render_connected_clients_visual_html(
            sessions,
            id_prefix="admin-node-op-client",
            update_push={
                "form_action": ADMIN_NODE_OPERATOR_POST_PATH,
                "version": catalog_ver,
                "url": "https://restoreprivacy.online/",
                "message": "",
                "hidden_fields": {
                    "node": node["id"],
                    "action": "push_update",
                },
            },
        )
    except Exception as exc:  # noqa: BLE001
        clients_visual = (
            f'<p class="muted" id="admin-node-op-clients-fallback">'
            f"Connected clients visual unavailable: {_esc(type(exc).__name__)}: {_esc(exc)}</p>"
        )
    try:
        from node_operator.update_delivery import (
            build_update_delivery_matrix,
            render_update_delivery_matrix_html,
        )
    except ImportError:  # pragma: no cover
        root = monorepo_root()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from node_operator.update_delivery import (
            build_update_delivery_matrix,
            render_update_delivery_matrix_html,
        )
    delivery_html = render_update_delivery_matrix_html(
        build_update_delivery_matrix(
            sessions=sessions,
            packages=inv.get("packages") or [],
            catalog_version=catalog_ver,
        ),
        id_prefix="admin-delivery",
    )
    sess_rows: list[str] = []
    for s in sessions:
        ver_raw = str(s.get("product_version") or "").strip()
        ver_disp = ver_raw if ver_raw else "unknown"
        ver_attr = _escape(ver_raw)
        unknown_attr = ' data-client-version-unknown="1"' if not ver_raw else ""
        sess_rows.append(
            "<tr>"
            f"<td><code>{_escape(s.get('client_id'))}</code></td>"
            f"<td data-client-version=\"{ver_attr}\"{unknown_attr}>"
            f"<code>{_escape(ver_disp)}</code></td>"
            f"<td>{_escape(s.get('vpn_ip'))}</td>"
            f"<td>{_escape(s.get('client_addr'))}</td>"
            f"<td>{int(s.get('priority') or 0)}</td>"
            "</tr>"
        )
    sess_table = (
        "\n".join(sess_rows)
        if sess_rows
        else '<tr id="admin-node-op-sessions-empty"><td colspan="5">No lab sessions</td></tr>'
    )

    residual_peer_default = (
        node["code"]
        if node.get("kind") == "residual"
        else "IS"
    )
    action = ADMIN_NODE_OPERATOR_POST_PATH
    node_q = _escape(node["id"])

    main = f"""
<section class="card" id="admin-node-operator" data-admin-node-operator="1"
         data-selected-node="{_escape(node['id'])}"
         data-selected-kind="{_escape(node.get('kind') or '')}"
         data-selected-host="{_escape(node.get('host') or '')}">
  <h2 id="admin-node-operator-heading">Node Operator</h2>
  <p class="muted" id="admin-node-operator-blurb">
    Project residual peers, local lab, and package store — same work as the Mac
    node GUI, under admin auth. Public node <code>/status</code> stays title-only.
    Select an operable node above to scope residual dial and context.
  </p>
  {tabs_html}
  <p id="admin-node-op-selected" class="muted">
    <strong>Selected:</strong>
    <span id="admin-node-op-selected-label">{_escape(node.get('label'))}</span>
    · kind=<code id="admin-node-op-selected-kind">{_escape(node.get('kind'))}</code>
    · host=<code id="admin-node-op-selected-host">{_escape(node.get('host'))}</code>
  </p>
  {flash}

  <div class="node-op-grid">
  <section class="card nested" id="admin-node-op-lab">
    <h3>Local lab stack</h3>
    <p id="admin-node-op-lab-state">
      State: <strong>{_escape(st.state)}</strong> · mode={_escape(st.mode)}
      · pid={_escape(str(st.pid) if st.pid is not None else '—')}
    </p>
    <p class="muted">{_escape(st.detail)}</p>
    <form method="post" action="{action}" id="admin-node-op-start-form">
      <input type="hidden" name="node" value="{node_q}"/>
      <input type="hidden" name="action" value="start_lab"/>
      <button type="submit" id="admin-node-op-start-btn">Start lab node</button>
    </form>
    <form method="post" action="{action}" id="admin-node-op-stop-form" style="display:inline">
      <input type="hidden" name="node" value="{node_q}"/>
      <input type="hidden" name="action" value="stop_lab"/>
      <button type="submit" id="admin-node-op-stop-btn">Stop lab</button>
    </form>
    <form method="post" action="{action}" id="admin-node-op-lab-session-form" style="display:inline">
      <input type="hidden" name="node" value="{node_q}"/>
      <input type="hidden" name="action" value="lab_session"/>
      <button type="submit" id="admin-node-op-lab-session-btn">Add lab session</button>
    </form>
  </section>

  <section class="card nested" id="admin-node-op-residual">
    <h3>Residual connect (selected peer)</h3>
    <p class="muted">Shipped CLIENT_HELLO to residual catalog peer. Scoped by operable node when kind=residual.</p>
    <p id="admin-node-op-residual-status">
      Residual: {_escape(residual.get('state'))}
      · peer={_escape(residual.get('peer') or '—')}
      · vpn_ip={_escape(residual.get('vpn_ip') or '—')}
    </p>
    <form method="post" action="{action}" id="admin-node-op-connect-form">
      <input type="hidden" name="node" value="{node_q}"/>
      <input type="hidden" name="action" value="connect_residual"/>
      <label for="admin-node-op-peer">Peer</label>
      <select name="peer" id="admin-node-op-peer">
        <option value="IS"{" selected" if residual_peer_default == "IS" else ""}>Iceland (IS)</option>
        <option value="DE"{" selected" if residual_peer_default == "DE" else ""}>Germany (DE)</option>
      </select>
      <button type="submit" id="admin-node-op-connect-btn">Connect residual</button>
    </form>
    <form method="post" action="{action}" id="admin-node-op-disconnect-form" style="margin-top:0.4rem">
      <input type="hidden" name="node" value="{node_q}"/>
      <input type="hidden" name="action" value="disconnect_residual"/>
      <button type="submit" id="admin-node-op-disconnect-btn">Disconnect residual</button>
    </form>
  </section>
  </div>

  <section class="card nested" id="admin-node-op-sessions">
    <h3>Connected clients (graphic)</h3>
    <p class="muted">Chronoflux-style pyramid of animated blob tiles from the real lab
      session list (apex = higher priority). Each blob shows product version (or unknown)
      and can push residual UPDATE_PUSH to that client only. Not public.</p>
    {clients_visual}
    <details id="admin-node-op-sessions-table-details" class="muted">
      <summary>Table detail</summary>
    <table id="admin-node-op-sessions-table">
      <thead><tr><th>Client id</th><th>Version</th><th>VPN IP</th><th>Addr</th><th>Priority</th></tr></thead>
      <tbody>{sess_table}</tbody>
    </table>
    </details>
  </section>

  <section class="card nested" id="admin-node-op-priority">
    <h3>Prioritise clients</h3>
    <form method="post" action="{action}" id="admin-node-op-priority-form">
      <input type="hidden" name="node" value="{node_q}"/>
      <input type="hidden" name="action" value="set_priority"/>
      <label for="admin-node-op-client-id">Client id</label>
      <input id="admin-node-op-client-id" name="client_id" required/>
      <label for="admin-node-op-priority">Priority</label>
      <input id="admin-node-op-priority" name="priority" type="number" value="10" required/>
      <button type="submit" id="admin-node-op-priority-btn">Set priority</button>
    </form>
    <p class="muted">Stored: <code id="admin-node-op-priority-map">{_escape(json.dumps(prio_map))}</code></p>
  </section>

  <section class="card nested" id="admin-node-op-deploy-packages"
           data-deploy-packages="1" data-helsinki-upload="1" data-suite-push-upload="1"
           data-suite-version="{_escape(catalog_ver)}">
    <h3 id="admin-node-op-suite-push-heading">Push Suite packages</h3>
    <p class="muted" id="admin-node-op-deploy-blurb">
      Stage + upload <strong>Restore Privacy Suite v{_escape(catalog_ver)}</strong>
      installers to the Helsinki paid store. Drives
      <code>scripts/host_paid_assets_vps.py</code> (SSH key for real upload).
      Store host: <code>{_escape(next((n['host'] for n in nodes if n['id']=='helsinki-store'), '135.181.152.10'))}</code>.
    </p>
    <p id="admin-node-op-deploy-inventory">
      <span class="suite-badge" id="admin-node-op-suite-badge">Restore Privacy Suite v{_escape(catalog_ver)}</span>
      · catalog <code id="admin-node-op-catalog-version">{_escape(catalog_ver)}</code>
      · present {int(inv.get('present_count') or 0)}/{int(inv.get('total') or 0)}
      · staged {int(inv.get('staged_count') or 0)}/{int(inv.get('total') or 0)}
    </p>
    <table id="admin-node-op-packages-table" data-suite-packages="1">
      <thead><tr><th>Platform</th><th>Filename</th><th>Local</th><th>Staged</th><th>Size</th></tr></thead>
      <tbody>{pkg_table}</tbody>
    </table>
    <form method="post" action="{action}" id="admin-node-op-upload-form"
          data-helsinki-upload="1" data-suite-push-form="1">
      <input type="hidden" name="node" value="{node_q}"/>
      <input type="hidden" name="action" value="push_suite_packages"/>
      <label for="admin-node-op-deploy-version">Suite catalog version</label>
      <input id="admin-node-op-deploy-version" name="version" required value="{_escape(catalog_ver)}"/>
      <label><input type="checkbox" name="stage" value="1" checked id="admin-node-op-deploy-stage"/> Stage</label>
      <label><input type="checkbox" name="upload" value="1" checked id="admin-node-op-deploy-upload"/> Upload to Helsinki</label>
      <label><input type="checkbox" name="allow_missing" value="1" checked id="admin-node-op-deploy-allow-missing"/> Allow missing</label>
      <label><input type="checkbox" name="force" value="1" id="admin-node-op-deploy-force"/> Force</label>
      <label><input type="checkbox" name="dry_run" value="1" id="admin-node-op-deploy-dry-run"/> Dry-run</label>
      <label><input type="checkbox" name="install_serve" value="1" id="admin-node-op-deploy-install-serve"/> Install serve</label>
      <button type="submit" id="admin-node-op-upload-btn" class="primary-upload">Push Suite packages to Helsinki</button>
    </form>
    <hr style="border:0;border-top:1px solid var(--border,#333);margin:1rem 0"/>
    <h4 id="admin-node-op-path-upload-heading">Upload by file path</h4>
    <p class="muted" id="admin-node-op-path-upload-blurb">
      Stage + upload one local monopin installer by absolute/relative filesystem path.
    </p>
    <form method="post" action="{action}" id="admin-node-op-path-upload-form" data-path-upload="1">
      <input type="hidden" name="node" value="{node_q}"/>
      <input type="hidden" name="action" value="upload_by_path"/>
      <label for="admin-node-op-path-input">Local package path</label>
      <input id="admin-node-op-path-input" name="path" required
             placeholder="/path/to/restore-privacy-client-{_escape(catalog_ver)}-linux-x64.tar.gz"/>
      <label><input type="checkbox" name="stage" value="1" checked id="admin-node-op-path-stage"/> Stage</label>
      <label><input type="checkbox" name="upload" value="1" checked id="admin-node-op-path-upload"/> Upload to Helsinki</label>
      <label><input type="checkbox" name="dry_run" value="1" id="admin-node-op-path-dry-run"/> Dry-run</label>
      <label><input type="checkbox" name="force" value="1" id="admin-node-op-path-force"/> Force</label>
      <button type="submit" id="admin-node-op-path-upload-btn">Browse files and Upload</button>
    </form>
  </section>

  <section class="card nested" id="admin-node-op-push" data-push-update="1">
    <h3>Push update to clients</h3>
    <p class="muted" id="admin-node-op-push-blurb">
      Residual <strong>UPDATE_PUSH</strong> directive after packages are on the host.
      Clients apply when Settings has <strong>CHECK BREADCRUMBS</strong> enabled.
    </p>
    <form method="post" action="{action}" id="admin-node-op-push-form">
      <input type="hidden" name="node" value="{node_q}"/>
      <input type="hidden" name="action" value="push_update"/>
      <label for="admin-node-op-push-version">Update directive version</label>
      <input id="admin-node-op-push-version" name="version" required value="{_escape(catalog_ver)}"/>
      <label for="admin-node-op-push-url">URL</label>
      <input id="admin-node-op-push-url" name="url" placeholder="https://restoreprivacy.online/"/>
      <label for="admin-node-op-push-message">Message</label>
      <input id="admin-node-op-push-message" name="message"/>
      <label for="admin-node-op-push-target">Target client (empty = all lab sessions)</label>
      <input id="admin-node-op-push-target" name="target_client_id"/>
      <button type="submit" id="admin-node-op-push-btn">Push update to clients</button>
    </form>
  </section>

  <section class="card nested" id="admin-node-op-delivery">
    {delivery_html}
  </section>

  {admin_section_top_link_html()}
</section>
<style>
.node-op-tabs{{display:flex;flex-wrap:wrap;gap:0.4rem;margin:0.75rem 0 1rem}}
.node-op-tab{{display:inline-block;padding:0.45rem 0.75rem;border-radius:8px;
  border:1px solid var(--border,#333);background:var(--bg-elevated,#1a2433);
  color:inherit;text-decoration:none;font-size:0.85rem;font-weight:600}}
.node-op-tab.is-active{{background:var(--btn-bg,#1d6fd8);color:var(--btn-fg,#fff);border-color:transparent}}
.node-op-grid{{display:grid;grid-template-columns:1fr 1fr;gap:0.75rem}}
@media (max-width:900px){{.node-op-grid{{grid-template-columns:1fr}}}}
#admin-node-operator .nested{{margin:0.75rem 0}}
#admin-node-operator table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
#admin-node-operator th,#admin-node-operator td{{
  border:1px solid var(--border,#3333);padding:0.35rem 0.45rem;text-align:left}}
#admin-node-operator label{{display:block;margin:0.35rem 0 0.15rem;font-size:0.85rem}}
#admin-node-operator input[type=text],#admin-node-operator input[type=number],
#admin-node-operator input:not([type]),#admin-node-operator select{{
  width:100%;max-width:22rem;box-sizing:border-box;padding:0.35rem 0.45rem}}
#admin-node-operator button{{margin:0.35rem 0.35rem 0 0;padding:0.45rem 0.85rem;
  border:0;border-radius:8px;background:var(--btn-bg,#1d6fd8);color:var(--btn-fg,#fff);
  font-weight:600;cursor:pointer}}
#admin-node-operator button.primary-upload,#admin-node-op-upload-btn{{
  background:#0d9488;font-size:1rem;padding:0.65rem 1.1rem}}
.ok-msg{{color:var(--badge-ok-fg,#065f46);background:var(--badge-ok-bg,#ecfdf5);
  padding:0.5rem 0.75rem;border-radius:8px}}
.err-msg{{color:#fecaca;background:rgba(127,29,29,0.35);padding:0.5rem 0.75rem;border-radius:8px}}
</style>
"""
    return _admin_page_shell(
        title="Node Operator",
        active="node-operator",
        main_html=main,
        extra_head=node_operator_auto_refresh_meta(node["id"]),
    )


# Forced browser destination when package-host SSH keys are missing on this machine.
ADMIN_UPLOAD_MISSING_SSH_KEYS_URL = "https://restoreprivacy.online/app-testers"


def handle_admin_node_operator_action(
    form: dict[str, str],
) -> tuple[bool, str, str] | tuple[bool, str, str, str]:
    """Process POST action.

    Returns ``(ok, message_or_error, selected_node_id)`` normally.
    When package SSH upload is blocked for missing host access keys, returns a
    fourth element: absolute redirect URL (``https://restoreprivacy.online/app-testers``)
    so the status host can force browser navigation.
    """
    ensure_monorepo_on_path()
    node_id = (form.get("node") or "").strip() or "IS"
    action = (form.get("action") or "").strip()
    node = resolve_operable_node(node_id)
    try:
        ctrl = get_operator_controller()
    except Exception as exc:  # noqa: BLE001
        return (
            False,
            f"Node Operator backend unavailable: {type(exc).__name__}: {exc}",
            node["id"],
        )

    if action == "start_lab":
        st = ctrl.start(mode="lab")
        return True, f"Lab start → {st.state}: {st.detail}", node["id"]
    if action == "stop_lab":
        st = ctrl.stop()
        return True, f"Lab stop → {st.state}", node["id"]
    if action == "lab_session":
        row = ctrl.inject_lab_session()
        return True, f"Lab session {row.get('client_id', '')[:16]}…", node["id"]
    if action == "connect_residual":
        peer = (form.get("peer") or "").strip().upper()
        if node.get("kind") == "residual" and node.get("code"):
            peer = str(node["code"]).upper()
        if not peer:
            peer = "IS"
        r = ctrl.connect_residual_peer(peer=peer, timeout=15.0)
        if r.get("ok"):
            return (
                True,
                f"Connected residual to {r.get('peer')} ({r.get('host')}) "
                f"vpn_ip={r.get('vpn_ip')}",
                node["id"],
            )
        return (
            False,
            f"Connect failed: {r.get('error') or r.get('message') or 'error'}",
            node["id"],
        )
    if action == "disconnect_residual":
        ctrl.disconnect_residual()
        return True, "Residual disconnected", node["id"]
    if action == "set_priority":
        cid = (form.get("client_id") or "").strip()
        try:
            prio = int(form.get("priority") or "0")
        except ValueError:
            return False, "priority must be an integer", node["id"]
        try:
            r = ctrl.set_client_priority(cid, prio)
        except ValueError as exc:
            return False, str(exc), node["id"]
        return True, f"Priority set → {r['priority']}", node["id"]
    if action == "push_update":
        r = ctrl.push_update(
            version=form.get("version") or "",
            url=form.get("url") or "",
            message=form.get("message") or "",
            target_client_id=form.get("target_client_id") or "",
        )
        if not r.get("ok"):
            return False, str(r.get("error") or "push failed"), node["id"]
        return True, f"Pushed to {r.get('count')} target(s)", node["id"]
    if action in ("upload_packages", "push_suite_packages"):
        ver = (form.get("version") or "").strip() or ctrl.catalog_version_default()
        if action == "push_suite_packages":
            r = ctrl.push_suite_packages(
                version=ver,
                stage=form.get("stage") == "1",
                upload=form.get("upload") == "1",
                dry_run=form.get("dry_run") == "1",
                force=form.get("force") == "1",
                allow_missing=form.get("allow_missing") == "1",
                install_serve=form.get("install_serve") == "1",
            )
            if r.get("missing_ssh_keys") and r.get("redirect"):
                return (
                    False,
                    str(r.get("error") or "SSH access keys missing"),
                    node["id"],
                    str(r.get("redirect") or ADMIN_UPLOAD_MISSING_SSH_KEYS_URL),
                )
            if not r.get("ok"):
                return (
                    False,
                    str(r.get("error") or "suite push failed"),
                    node["id"],
                )
            return (
                True,
                f"Pushed {r.get('suite')} present={r.get('present_count')}/"
                f"{r.get('total')} dry_run={r.get('dry_run')} "
                f"upload_code={r.get('upload_code')}",
                node["id"],
            )
        r = ctrl.upload_catalog_packages(
            version=ver,
            stage=form.get("stage") == "1",
            upload=form.get("upload") == "1",
            dry_run=form.get("dry_run") == "1",
            force=form.get("force") == "1",
            allow_missing=form.get("allow_missing") == "1",
            install_serve=form.get("install_serve") == "1",
        )
        if r.get("missing_ssh_keys") and r.get("redirect"):
            return (
                False,
                str(r.get("error") or "SSH access keys missing"),
                node["id"],
                str(r.get("redirect") or ADMIN_UPLOAD_MISSING_SSH_KEYS_URL),
            )
        if not r.get("ok"):
            return False, str(r.get("error") or "deploy failed"), node["id"]
        return (
            True,
            f"Deploy {r.get('version')} dry_run={r.get('dry_run')} "
            f"upload_code={r.get('upload_code')}",
            node["id"],
        )
    if action == "upload_by_path":
        path = (form.get("path") or "").strip()
        r = ctrl.upload_package_by_path(
            path,
            stage=form.get("stage") == "1",
            upload=form.get("upload") == "1",
            dry_run=form.get("dry_run") == "1",
            force=form.get("force") == "1",
            install_serve=form.get("install_serve") == "1",
        )
        if r.get("missing_ssh_keys") and r.get("redirect"):
            return (
                False,
                str(r.get("error") or "SSH access keys missing"),
                node["id"],
                str(r.get("redirect") or ADMIN_UPLOAD_MISSING_SSH_KEYS_URL),
            )
        if not r.get("ok"):
            return False, str(r.get("error") or "path upload failed"), node["id"]
        return (
            True,
            f"Path upload {r.get('filename')} v{r.get('version')} "
            f"platform={r.get('platform')} staged={r.get('staged_to') or '—'} "
            f"dry_run={r.get('dry_run')} upload_code={r.get('upload_code')}",
            node["id"],
        )
    return False, f"unknown action {action!r}", node["id"]
