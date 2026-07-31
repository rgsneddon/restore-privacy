"""Admin Perc / network explorer section (auth-gated on the status host).

Shows a live snapshot of the public Perccent internet-node health/network JSON
and links to the public explorer under /perc/. No secrets; operators only.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# Public Helsinki explorer + API (path-mounted under nginx /perc/)
DEFAULT_PERC_PUBLIC_BASE = "https://135.181.152.10.sslip.io/perc"
DEFAULT_PERC_NETWORK_PATH = "/api/network"
DEFAULT_PERC_HEALTH_PATH = "/health"

ADMIN_PERC_PATH = "/admin/perc"
ADMIN_PERC_NAV_ID = "admin-nav-perc"
ADMIN_PERC_PAGE_ID = "admin-perc-page"
ADMIN_PERC_STATUS_ID = "admin-perc-status"
ADMIN_PERC_SNAPSHOT_ID = "admin-perc-network-snapshot"


def perc_public_base_url() -> str:
    """Configured public Perc base (no trailing slash)."""
    raw = (
        os.environ.get("RPT_PERC_PUBLIC_BASE")
        or os.environ.get("PERC_PUBLIC_BASE")
        or DEFAULT_PERC_PUBLIC_BASE
    ).strip()
    return raw.rstrip("/")


def perc_explorer_url() -> str:
    base = perc_public_base_url()
    return base + "/"


def perc_network_api_url() -> str:
    return perc_public_base_url() + DEFAULT_PERC_NETWORK_PATH


def perc_health_api_url() -> str:
    return perc_public_base_url() + DEFAULT_PERC_HEALTH_PATH


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fetch_perc_json(
    url: str,
    *,
    timeout: float = 8.0,
    opener: Any | None = None,
) -> dict[str, Any]:
    """GET JSON from a Perc public API URL. Pure enough for injectible opener."""
    if opener is not None:
        return opener(url)
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "rpt-admin-perc/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            code = getattr(resp, "status", None) or resp.getcode()
            if int(code) < 200 or int(code) >= 300:
                return {
                    "ok": False,
                    "error": f"HTTP {code}",
                    "url": url,
                }
            data = json.loads(raw.decode("utf-8", errors="replace") or "{}")
            if not isinstance(data, dict):
                return {"ok": False, "error": "non-object JSON", "url": url}
            data.setdefault("ok", True)
            data["_fetch_url"] = url
            return data
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}", "url": url}
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if len(msg) > 200:
            msg = msg[:200]
        return {"ok": False, "error": msg or "fetch failed", "url": url}


def fetch_perc_network_snapshot(
    *,
    opener: Any | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Live network JSON used by the admin Perc panel."""
    return fetch_perc_json(
        perc_network_api_url(),
        timeout=timeout,
        opener=opener,
    )


def render_admin_perc_main_html(
    *,
    snapshot: dict[str, Any] | None = None,
    opener: Any | None = None,
) -> str:
    """Main pane HTML for Perc network (inside admin shell)."""
    snap = snapshot if snapshot is not None else fetch_perc_network_snapshot(opener=opener)
    online = bool(snap.get("ok")) and (
        str(snap.get("nodeStatus") or "").lower() == "online" or snap.get("ok") is True
    )
    status_label = "Online" if online and "error" not in snap else "Unavailable"
    if snap.get("error"):
        status_label = f"Error: {_esc(str(snap.get('error')))}"
    elif str(snap.get("nodeStatus") or "").lower() == "online":
        status_label = "Online"
    elif snap.get("ok"):
        status_label = "OK"
    else:
        status_label = "Unavailable"

    height = snap.get("blockHeight") or snap.get("networkHeight") or "—"
    peers = snap.get("peers") if isinstance(snap.get("peers"), dict) else {}
    peers_line = (
        f"{peers.get('online', '—')} / {peers.get('total', '—')}"
        if peers
        else "—"
    )
    chain = snap.get("chainId") or "—"
    explorer = perc_explorer_url()
    api_net = perc_network_api_url()
    api_health = perc_health_api_url()

    pretty = json.dumps(snap, indent=2, sort_keys=True)[:12000]
    pretty = _esc(pretty)

    return f"""
<section class="card" id="{ADMIN_PERC_PAGE_ID}" data-admin-perc="1">
  <h2 id="admin-perc-heading">Perc network</h2>
  <p class="muted">
    Live snapshot from the public Perccent internet node (path-mounted explorer).
    Anonymous visitors use the public explorer only — this page is admin-only.
  </p>
  <p id="{ADMIN_PERC_STATUS_ID}" data-perc-status="{_esc(status_label)}">
    <strong>Status:</strong> {_esc(status_label)}
  </p>
  <ul class="admin-perc-meta" id="admin-perc-meta">
    <li><strong>Explorer:</strong>
      <a href="{_esc(explorer)}" target="_blank" rel="noopener noreferrer"
         id="admin-perc-explorer-link">{_esc(explorer)}</a></li>
    <li><strong>Network API:</strong>
      <a href="{_esc(api_net)}" target="_blank" rel="noopener noreferrer"
         id="admin-perc-network-link">{_esc(api_net)}</a></li>
    <li><strong>Health:</strong>
      <a href="{_esc(api_health)}" target="_blank" rel="noopener noreferrer"
         id="admin-perc-health-link">{_esc(api_health)}</a></li>
    <li><strong>Seed / network height:</strong> {_esc(str(height))}</li>
    <li><strong>Peers online:</strong> {_esc(str(peers_line))}</li>
    <li><strong>Chain:</strong> <code>{_esc(str(chain))}</code></li>
  </ul>
  <h3>Network JSON</h3>
  <pre class="mono" id="{ADMIN_PERC_SNAPSHOT_ID}" style="max-height:28rem;overflow:auto;white-space:pre-wrap">{pretty}</pre>
</section>
"""


def render_admin_perc_page_html(
    *,
    snapshot: dict[str, Any] | None = None,
    opener: Any | None = None,
) -> bytes:
    """Full admin document for /admin/perc."""
    from admin_panel import _admin_page_shell  # local import avoids cycles

    main = render_admin_perc_main_html(snapshot=snapshot, opener=opener)
    return _admin_page_shell(
        title="Perc network — Admin",
        active="perc",
        main_html=main,
    )
