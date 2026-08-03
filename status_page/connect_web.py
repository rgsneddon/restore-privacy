"""Connect-via-web panel for the public Restore Privacy storefront.

A normal browser tab cannot create a full OS TUN / system-wide residual path.
This module ships the maximum honest path: a clear Connect via web control that
explains that limit and routes the user to real native VPN clients.
"""

from __future__ import annotations

from downloads import RELEASE_VERSION, available_downloads


CONNECT_HEADING = "Connect via web"
HONESTY_LINE = (
    "A normal web page cannot install a full system-wide residual tunnel on your "
    "device (browsers do not allow creating an OS tunnel from a tab alone)."
)
ACTION_LINE = (
    "For full Restore Privacy residual Connect, download the native app for your "
    "platform below. Those are the real VPN clients - catalog "
    f"v{RELEASE_VERSION}."
)


def recommended_download_actions() -> list[dict[str, str]]:
    """Primary actions: storefront package paths (catalog monopin)."""
    actions: list[dict[str, str]] = []
    for asset in available_downloads():
        actions.append(
            {
                "platform": asset.platform,
                "label": f"Get {asset.label}",
                "href": asset.pay_path,
                "filename": asset.filename,
            }
        )
    return actions


def render_connect_via_web_html() -> str:
    """HTML fragment: Connect via web control + honesty + working client actions."""
    actions = recommended_download_actions()
    buttons = []
    for a in actions:
        buttons.append(
            f'      <a class="connect-btn" id="connect-web-{a["platform"]}" '
            f'href="{a["href"]}" data-catalog-version="{RELEASE_VERSION}" '
            f'data-filename="{a["filename"]}">{a["label"]}</a>'
        )
    buttons_html = "\n".join(buttons)
    # Limited in-page demo: only checks live status API - clearly not full residual
    return f"""
  <section class="connect-web" id="connect-via-web" aria-label="Connect via web"
           data-product="suite" data-catalog-version="{RELEASE_VERSION}">
    <h2>{CONNECT_HEADING}</h2>
    <p class="connect-honest">{HONESTY_LINE}</p>
    <p class="connect-action">{ACTION_LINE}</p>
    <div class="connect-actions">
{buttons_html}
    </div>
    <details class="connect-limited">
      <summary>Limited web check (not full-device residual Connect)</summary>
      <p class="connect-limited-note">
        This only contacts the shop&rsquo;s live status API. It does
        <strong>not</strong> route your device traffic or replace the native
        VPN client for Windows, Android, macOS, iOS, or Linux.
      </p>
      <button type="button" class="connect-probe" id="connect-web-probe">Run web status check</button>
      <p class="connect-probe-out" id="connect-web-probe-out" aria-live="polite"></p>
    </details>
  </section>
"""


def connect_via_web_css() -> str:
    return """
    .connect-web {
      margin-top: 2.25rem; text-align: center; max-width: 36rem; padding: 0 1rem;
    }
    .connect-web h2 {
      font-size: 1.15rem; letter-spacing: 0.08em; font-weight: 600; margin: 0 0 0.75rem;
    }
    .connect-honest, .connect-action {
      opacity: 0.9; font-size: 0.95rem; line-height: 1.45; margin: 0 0 0.75rem;
    }
    .connect-honest { color: #fbbf24; }
    .connect-actions {
      display: flex; flex-direction: column; gap: 0.55rem; align-items: center; margin: 1rem 0;
    }
    a.connect-btn {
      display: inline-block; min-width: 16rem; padding: 0.7rem 1.2rem;
      background: #047857; color: #fff; text-decoration: none; border-radius: 6px;
      font-weight: 600; font-size: 0.92rem;
    }
    a.connect-btn:hover { background: #059669; }
    .connect-limited {
      margin-top: 1rem; text-align: left; opacity: 0.9; font-size: 0.88rem;
    }
    .connect-limited summary { cursor: pointer; color: #93c5fd; }
    .connect-limited-note { margin: 0.6rem 0; line-height: 1.4; opacity: 0.85; }
    .connect-probe {
      cursor: pointer; border: 1px solid #334155; background: #0f172a; color: #e2e8f0;
      padding: 0.45rem 0.9rem; border-radius: 4px; font-size: 0.88rem;
    }
    .connect-probe-out { margin-top: 0.5rem; font-family: ui-monospace, monospace; font-size: 0.85rem; color: #6ee7b7; }
"""


def connect_via_web_script() -> str:
    """JS for the limited web status probe only (not full VPN)."""
    return """
(function () {
  var btn = document.getElementById('connect-web-probe');
  var out = document.getElementById('connect-web-probe-out');
  if (!btn || !out) return;
  btn.addEventListener('click', function () {
    out.textContent = 'Checking live status…';
    fetch('/api/status', { cache: 'no-store', credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var n = (data && typeof data.clients_connected === 'number') ? data.clients_connected : 0;
        out.textContent = 'Web check OK - currently connected clients: ' + n
          + '. Full VPN still requires the native client download above.';
      })
      .catch(function () {
        out.textContent = 'Web check failed. Use a native client download for full VPN.';
      });
  });
})();
"""
