"""Clients × packages × multi-hoppable residual peers for operator update delivery.

Pure presentation helpers: no invented clients or packages.
"""

from __future__ import annotations

from typing import Any, Sequence


def multihoppable_peers() -> list[dict[str, Any]]:
    """Product residual peers clients may dial (IS/DE)."""
    try:
        from client.multihop import product_country_catalog

        out = []
        for n in product_country_catalog():
            out.append(
                {
                    "code": str(n.code).upper(),
                    "name": str(n.name),
                    "host": str(n.host),
                    "port": int(n.port or 44044),
                    "multihop_capable": True,
                }
            )
        return out
    except Exception:  # noqa: BLE001
        return [
            {
                "code": "IS",
                "name": "Iceland",
                "host": "82.221.101.241",
                "port": 44044,
                "multihop_capable": True,
            },
            {
                "code": "DE",
                "name": "Germany",
                "host": "178.105.187.178",
                "port": 44044,
                "multihop_capable": True,
            },
        ]


def build_update_delivery_matrix(
    *,
    sessions: Sequence[dict[str, Any]] | None,
    packages: Sequence[dict[str, Any]] | None,
    catalog_version: str,
) -> dict[str, Any]:
    """Matrix of connected clients, monopin packages, and multihop peers."""
    peers = multihoppable_peers()
    clients = list(sessions or [])
    pkgs = list(packages or [])
    return {
        "catalog_version": (catalog_version or "").strip(),
        "clients": clients,
        "packages": pkgs,
        "peers": peers,
        "client_count": len(clients),
        "package_count": len(pkgs),
        "peer_codes": [p["code"] for p in peers],
    }


def _esc(s: Any) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_update_delivery_matrix_html(
    matrix: dict[str, Any],
    *,
    id_prefix: str = "op-delivery",
) -> str:
    """HTML: all clients + all packages + multihop peers for update path."""
    prefix = (id_prefix or "op-delivery").strip() or "op-delivery"
    ver = _esc(matrix.get("catalog_version") or "")
    clients = matrix.get("clients") or []
    packages = matrix.get("packages") or []
    peers = matrix.get("peers") or []

    peer_chips = "".join(
        f'<span class="{_esc(prefix)}-peer" data-peer-code="{_esc(p.get("code"))}" '
        f'data-multihop-capable="1">{_esc(p.get("code"))} '
        f'{_esc(p.get("name"))} <code>{_esc(p.get("host"))}</code></span>'
        for p in peers
    )
    if not peer_chips:
        peer_chips = f'<span class="{_esc(prefix)}-peer-empty">No multihop peers</span>'

    pkg_rows = []
    for p in packages:
        pkg_rows.append(
            f'<tr data-package-row="1" data-platform="{_esc(p.get("platform"))}">'
            f"<td>{_esc(p.get('platform'))}</td>"
            f"<td><code>{_esc(p.get('filename'))}</code></td>"
            f"<td>{'yes' if p.get('present') else 'no'}</td>"
            f"<td>{'yes' if p.get('staged') else 'no'}</td>"
            f"</tr>"
        )
    pkg_body = (
        "\n".join(pkg_rows)
        if pkg_rows
        else f'<tr id="{_esc(prefix)}-packages-empty"><td colspan="4">No catalog packages</td></tr>'
    )

    client_rows = []
    for s in clients:
        client_rows.append(
            f'<tr data-client-row="1" data-client-id="{_esc(s.get("client_id"))}">'
            f"<td><code>{_esc(str(s.get('client_id') or '')[:16])}…</code></td>"
            f"<td>{_esc(s.get('vpn_ip'))}</td>"
            f"<td>{int(s.get('priority') or 0)}</td>"
            f"<td>Manual free Suite download (catalog monopin)</td>"
            f"</tr>"
        )
    client_body = (
        "\n".join(client_rows)
        if client_rows
        else f'<tr id="{_esc(prefix)}-clients-empty"><td colspan="4">No connected clients</td></tr>'
    )

    return f"""
<section class="{_esc(prefix)}-matrix" id="{_esc(prefix)}-matrix" data-update-delivery-matrix="1"
         data-catalog-version="{ver}">
  <h3 id="{_esc(prefix)}-matrix-heading">Clients · packages · multihop nodes</h3>
  <p class="muted" id="{_esc(prefix)}-matrix-blurb">
    Residual client update push is <strong>disabled</strong>. Host Suite packages on
    Helsinki; users update manually from free Suite download when a newer monopin
    is available (discrete in-app notice only). Packages listed below are monopin
    <code>{ver}</code> installers. Multihop peers are dial targets for residual Connect —
    not an update-apply path.
  </p>
  <div id="{_esc(prefix)}-peers" data-multihop-peers="1" class="{_esc(prefix)}-peer-row">
    <strong>Multihop residual peers:</strong> {peer_chips}
  </div>
  <h4>Connected clients ({len(clients)})</h4>
  <table id="{_esc(prefix)}-clients-table">
    <thead><tr><th>Client</th><th>VPN IP</th><th>Priority</th><th>Update path</th></tr></thead>
    <tbody>{client_body}</tbody>
  </table>
  <h4>Catalog packages ({len(packages)})</h4>
  <table id="{_esc(prefix)}-packages-table">
    <thead><tr><th>Platform</th><th>Filename</th><th>Local</th><th>Staged</th></tr></thead>
    <tbody>{pkg_body}</tbody>
  </table>
</section>
<style>
.{_esc(prefix)}-peer-row{{margin:0.5rem 0 0.75rem;display:flex;flex-wrap:wrap;gap:0.4rem;align-items:center}}
.{_esc(prefix)}-peer{{display:inline-block;padding:0.25rem 0.55rem;border-radius:999px;
  background:rgba(34,197,94,0.12);border:1px solid #2a6a4a;font-size:0.78rem}}
.{_esc(prefix)}-matrix table{{width:100%;border-collapse:collapse;font-size:0.8rem;margin:0.35rem 0 0.75rem}}
.{_esc(prefix)}-matrix th,.{_esc(prefix)}-matrix td{{
  border:1px solid #2a3a50;padding:0.3rem 0.4rem;text-align:left}}
</style>
"""
