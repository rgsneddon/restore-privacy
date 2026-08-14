"""Public Settings / product guide - human how-to for the dedicated VPN app.

Pure HTML builders (no live server required for unit tests). Framed for
**Restore Privacy**: free install, KEYGEN unlock, residual Connect, and Settings
controls in plain language.
"""

from __future__ import annotations

from typing import Any

# Public path served by the status host
SETTINGS_EXPLAINER_PATH = "/settings-explainer"
SETTINGS_EXPLAINER_ALIASES = (
    "/settings",
    "/settings-help",
    "/client-settings",
    "/docs/settings-explainer",
    "/sdk",
)
# Hard link to the corporate / SDK retainer box (also the main-menu SDK target).
CORPORATE_CLIENTS_HREF = "/settings-explainer#corporate-clients"

# Homepage banner target (same path)
HOMEPAGE_SETTINGS_BANNER_ID = "settings-explainer-banner"
HOMEPAGE_SETTINGS_BANNER_HREF = SETTINGS_EXPLAINER_PATH

# Page structure markers (tests + progressive hooks)
SUITE_GUIDE_INTRO_ID = "suite-guide-intro"
SUITE_HOWTO_PARTS_ID = "suite-howto-parts"
SUITE_HOWTO_PARTS_LIST_ID = "suite-howto-parts-list"
SETTINGS_EXPLAINERS_BOX_ID = "settings-explainers-box"
INSTALL_HOWTO_BOX_ID = "install-run-howto-box"
CORPORATE_CLIENTS_BOX_ID = "corporate-clients"

CORPORATE_CLIENTS_HEADING = "Corporate clients"
CORPORATE_CLIENTS_BODY = (
    "A corporate client gets their own branded admin guide like MISHI: "
    "a software-development-kit blank canvas that grows into a full "
    "organisational structure, with up to 5 dedicated databases, a fully "
    "branded VPN network, and a dedicated server for a year, for £30,000."
)
CORPORATE_CLIENTS_AI = (
    "If a corporate client wants dedicated branded AI to learn from their "
    "organisation's workflow and workforce, that is another £27,000 on top "
    "of the £30,000."
)
CORPORATE_CLIENTS_FOOT = "This is a yearly subscription."

SUITE_GUIDE_INTRO_HEADING = "How to use Restore Privacy"
SUITE_GUIDE_INTRO_BODY = (
    "This VPN guide is short. Download free, try three days, then enter a "
    "KEYGEN to keep connecting. Use Connect on the main screen; open Settings "
    "from the gear."
)
# One short line — no second trial/KEYGEN lecture (body already covers the path).
SUITE_GUIDE_INTRO_FOOT = (
    "This page is a user guide, not an operator console. "
    "Monthly KEYGEN starts at £3."
)


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def suite_howto_parts_catalog() -> list[dict[str, str]]:
    """How to utilise each major VPN surface (human cadence).

    Keys: id, title, what, how, default.
    """
    return [
        {
            "id": "suite-unlock",
            # Intro already covers free download + trial path — this part is unlock only.
            "title": "KEYGEN unlock",
            "what": (
                "Paste the code from your fulfilment email when you want Connect "
                "to keep working past the free trial."
            ),
            "how": (
                "Use the unlock screen or Settings → Payment. Paste the KEYGEN "
                "(RPT-KEY-…). Monthly from £3; yearly on /pay."
            ),
            "default": "Paste KEYGEN when the trial ends",
        },
        {
            "id": "suite-vpn",
            "title": "Main screen — Connect",
            "what": (
                "Start and stop protection. See status, a short log, and entry country."
            ),
            "how": (
                "Press Connect and approve any system VPN prompt. Wait until status "
                "shows connected. Disconnect when finished — minimizing does not stop "
                "the tunnel. Quit (lower-left) disconnects, then exits."
            ),
            "default": "Manual Connect · entry Germany (DE) or Singapore (SG)",
        },
        {
            "id": "suite-settings-gear",
            "title": "Settings (gear)",
            "what": (
                "Startup options, privacy extras, local log, leak test, and legal links."
            ),
            "how": (
                "Defaults stay lean (startup, autoconnect, and auto-connect-if-idle "
                "off; shaping, obfuscation, multi-hop, and kill-switch off). Turn on "
                "only what you need — details for each control are listed below. "
                "Updates are always a free manual download."
            ),
            "default": "Lean off until you opt in",
        },
    ]


def settings_parts_catalog() -> list[dict[str, str]]:
    """Each separate part of the product client Settings tab (VPN gear).

    Keys: id, title, default, body. Sourced from shipped Settings UI + product_policy.
    """
    # Import EXPLAINER_* from product when monorepo is on path; fall back to inline.
    shape = obfs = multi = core = ""
    try:
        from client.product_policy import (
            EXPLAINER_CORE_VPN,
            EXPLAINER_MULTIHOP,
            EXPLAINER_OUTER_OBFUSCATION,
            EXPLAINER_TRAFFIC_SHAPE,
        )

        shape = EXPLAINER_TRAFFIC_SHAPE
        obfs = EXPLAINER_OUTER_OBFUSCATION
        multi = EXPLAINER_MULTIHOP
        core = EXPLAINER_CORE_VPN
    except Exception:  # noqa: BLE001
        shape = (
            "Traffic shaping pads packet sizes, adds small send jitter, and sends "
            "periodic cover frames. OFF (product default) = snappier browsing with "
            "weaker traffic-analysis resistance; ON = stronger fingerprint resistance."
        )
        obfs = (
            "Outer obfuscation wraps residual UDP in a QUIC-like shell. "
            "OFF (product default) = bare RPT frames; ON = better blend with encrypted UDP."
        )
        multi = (
            "Multi-hop residual routes via an exit hop so egress IP is the exit. "
            "OFF (default) = single hop to entry (Germany or Singapore). ON = exit path."
        )
        core = (
            "Always on once you Connect with a valid KEYGEN: cryptographic HELLO/session "
            "and the system residual tunnel. Those cannot be turned off in Settings."
        )

    return [
        {
            "id": "run-at-startup",
            "title": "Run at device startup",
            "default": "Off",
            "body": (
                "When ON, the app can open at sign-in (platform startup hooks). "
                "Default OFF - it only runs when you launch it. This does not Connect "
                "the VPN by itself."
            ),
        },
        {
            "id": "autoconnect-on-launch",
            "title": "Autoconnect on launch",
            "default": "Off",
            "body": (
                "When ON, opening the app starts Connect automatically after licence "
                "and KEYGEN unlock. Default OFF - Connect is manual. Unlock is never skipped."
            ),
        },
        {
            "id": "auto-connect-if-idle",
            "title": "Auto connect if idle",
            "default": "Off",
            "body": (
                "When ON, the VPN service tries to re-open protection if the tunnel "
                "drops while you still wanted it (for example after a long idle gap "
                "or a brief network blip). Retries use a gentle backoff so the phone "
                "is not hammered. Default OFF. Disconnect, Quit, and system VPN "
                "revocation still stop fully and do not re-connect."
            ),
        },
        {
            "id": "suite-manual-update",
            "title": "App updates (manual only)",
            "default": "Manual free download",
            "body": (
                "Operators do not remote-install packages onto your device. "
                "When a newer build is available, the app shows a discrete "
                "“new version available” notice. Download the free package for "
                "your platform from the public shop and install it yourself - "
                "nothing is auto-applied over residual."
            ),
        },
        {
            "id": "core-vpn",
            "title": "Residual VPN core (always required)",
            "default": "Always on",
            "body": core,
        },
        {
            "id": "protect-ipv4-ipv6",
            "title": "IPv4 residual (always on) & IPv6 residual",
            "default": "IPv4 always on; IPv6 on by default",
            "body": (
                "IPv4 residual capture is always on (full-tunnel dual /1 routes) and "
                "cannot be turned off in Settings. IPv6 residual ISP-leak protection "
                "defaults ON and remains optional - turning IPv6 residual OFF means "
                "IPv6 may use the ISP and Connected status will not claim IPv6 is "
                "protected. Using IPv4 only may cause data leaks on dual-stack networks. "
                "Changing IPv6 Settings while residual is connected disconnects first, "
                "then saves for the next Connect."
            ),
        },
        {
            "id": "traffic-shaping",
            "title": "Traffic shaping (pad / jitter / cover)",
            "default": "Off",
            "body": shape,
        },
        {
            "id": "outer-obfuscation",
            "title": "Outer obfuscation (QUIC-mimic wrap)",
            "default": "Off",
            "body": obfs,
        },
        {
            "id": "multihop",
            "title": "Multi-hop residual (exit path)",
            "default": "Off",
            "body": multi,
        },
        {
            "id": "ping-statistics",
            "title": "Ping statistics (device → node)",
            "default": "Measure on demand",
            "body": (
                "Settings can show best-effort RTT from your device toward product "
                "entry (and exit when multi-hop is ON). Tap Measure ping when you want "
                "a rough sense of path health - not a speedbench SLA. Values may show "
                "n/a if the host is unreachable from your network."
            ),
        },
        {
            "id": "licence",
            "title": "End-user licence",
            "default": "Must accept before Connect",
            "body": (
                "Connect stays blocked until you accept the end-user licence on "
                "this device. Acceptance is stored only locally (not uploaded to "
                "the node). After accept, enter the fulfilment KEYGEN to unlock "
                "residual VPN."
            ),
        },
        {
            "id": "keygen",
            "title": "Payment entitlement / KEYGEN unlock",
            "default": "Required after the free trial",
            "body": (
                "Paste RPT-KEY-… from your email on the unlock screen or under "
                "Settings → Payment. Connect needs an active KEYGEN after the free "
                "trial; refunds or failed charges stop Connect until you renew."
            ),
        },
        {
            "id": "connection-log",
            "title": "Local connection log",
            "default": "On-device only",
            "body": (
                "Settings can show and export a local connection log. Events stay on "
                "your device - they are not uploaded to the node. Export only if you "
                "choose to email support yourself."
            ),
        },
        {
            "id": "leak-test",
            "title": "Leak test",
            "default": "Optional diagnostic",
            "body": (
                "Optional residual honesty checks from Settings (capture / DNS). "
                "Local diagnostic only - not a third-party leak site."
            ),
        },
        {
            "id": "kill-switch-opt-in",
            "title": "Kill switch (opt-in)",
            "default": "Off",
            "body": (
                "Optional fail-closed behaviour if residual drops while you wanted "
                "protection. Default OFF. Enabling requires an explicit confirm "
                "step in Settings so it is never flipped by accident. Read the "
                "in-app warning carefully before opting in."
            ),
        },
        {
            "id": "docs-links",
            "title": "Audit, privacy policy, and licence links",
            "default": "Open in browser",
            "body": (
                "Opens the public security audit, privacy policy, and licence on the "
                "status host so you can read them without a public source tree."
            ),
        },
    ]


def render_settings_explainer_banner_html() -> str:
    """Optional banner (homepage no longer injects it; kept for legacy callers)."""
    href = _esc(HOMEPAGE_SETTINGS_BANNER_HREF)
    return f"""    <aside class="panel-card settings-banner" id="{HOMEPAGE_SETTINGS_BANNER_ID}" aria-label="VPN Settings guide">
      <p class="settings-banner-kicker">New to Restore Privacy?</p>
      <p class="settings-banner-title">How to use the VPN</p>
      <p class="settings-banner-blurb">
        Free install, KEYGEN unlock, residual Connect, and every Settings control  - 
        plain language, step by step.
      </p>
      <p class="settings-banner-actions">
        <a class="settings-banner-link" id="settings-explainer-banner-link" href="{href}">Browse Settings guide →</a>
      </p>
    </aside>
"""


def homepage_settings_banner_css() -> str:
    """Banner styles live in shared public_chrome; keep empty for import compat."""
    return "/* settings banner styles: public_chrome.public_site_css */\n"


def corporate_clients_css() -> str:
    """Corporate retainer box styles — used on Settings guide and homepage."""
    return """
.corporate-clients { overflow: hidden; }
.corporate-clients .corp-lead {
  margin: 0 0 1rem; font-size: 0.95rem; line-height: 1.55; color: var(--rb-muted);
  text-align: left; max-width: 46rem;
}
.corporate-clients .corporate-clients-foot {
  margin: 1rem 0 0; font-weight: 800; letter-spacing: 0.04em;
  text-transform: uppercase; font-size: 0.82rem; color: var(--rb-cream);
}
[data-theme="light"] .corporate-clients .corporate-clients-foot,
[data-theme="light"] .corp-card h3,
[data-theme="light"] .corp-price-n { color: #0a2348; }
.corp-icon-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(9.6rem, 1fr));
  gap: 0.75rem; margin: 0 0 1.15rem;
}
.corp-card {
  border: 1px solid var(--rb-card-border); border-radius: 12px;
  padding: 0.85rem 0.75rem 0.75rem; text-align: left;
  background: color-mix(in srgb, var(--rb-accent-sky, #3ec6ff) 8%, transparent);
}
.corp-card .corp-ico { display: block; width: 42px; height: 42px; margin: 0 0 0.55rem; }
.corp-card h3 {
  margin: 0 0 0.3rem; font-size: 0.92rem; color: var(--rb-cream); letter-spacing: 0.02em;
}
.corp-card p { margin: 0; font-size: 0.8rem; line-height: 1.4; color: var(--rb-muted); }
.corp-meters { margin: 0 0 1.1rem; }
.corp-meter-row { margin: 0 0 0.55rem; }
.corp-meter-lab {
  display: flex; justify-content: space-between; gap: 0.6rem;
  font-size: 0.72rem; font-weight: 800; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--rb-accent-sky, var(--rb-link));
  margin: 0 0 0.2rem;
}
.corp-meter-track {
  height: 10px; border-radius: 999px; overflow: hidden;
  background: color-mix(in srgb, var(--rb-card-border) 80%, #000);
}
.corp-meter-fill {
  display: block; height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, #1ec8a0, #3ec6ff 55%, #7b6cff);
}
.corp-price-row {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: 0.75rem; margin: 0.2rem 0 0.4rem;
}
.corp-price {
  border: 1px solid var(--rb-card-border); border-radius: 12px;
  padding: 0.85rem 0.9rem; text-align: left;
}
.corp-price-k {
  margin: 0 0 0.25rem; font-size: 0.7rem; font-weight: 800;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--rb-accent-sky, var(--rb-link));
}
.corp-price-n {
  margin: 0 0 0.35rem; font-size: 1.55rem; font-weight: 800; color: var(--rb-cream);
  letter-spacing: 0.02em;
}
.corp-price p { margin: 0; font-size: 0.82rem; line-height: 1.45; color: var(--rb-muted); }
"""


def _shared_shell_css() -> str:
    """Page-specific explainer CSS (shared shell CSS comes from public_head_open)."""
    return """
.suite-guide-intro { text-align: center; }
.suite-guide-intro .suite-guide-lead {
  margin: 0 auto 0.75rem; max-width: 40rem; line-height: 1.55;
  font-size: clamp(0.95rem, 2.2vw, 1.08rem); color: var(--rb-soft, #aed0ea);
  font-weight: 500;
}
.suite-guide-intro .suite-guide-foot {
  margin: 0 auto; max-width: 36rem; font-size: 0.9rem;
  color: var(--rb-muted); line-height: 1.45;
}
.suite-howto-list { margin: 0; padding: 0; list-style: none; }
.suite-howto-item {
  border-top: 1px solid var(--rb-card-border);
  padding: 0.95rem 0.15rem;
  text-align: left;
}
.suite-howto-item:first-child { border-top: none; padding-top: 0.15rem; }
.suite-howto-item h3 {
  margin: 0 0 0.35rem; font-size: 1.05rem; color: var(--rb-cream);
  letter-spacing: 0.02em;
}
.suite-howto-item .howto-label {
  margin: 0.35rem 0 0.15rem; font-size: 0.72rem; font-weight: 800;
  letter-spacing: 0.07em; text-transform: uppercase;
  color: var(--rb-accent-sky, var(--rb-link));
}
.suite-howto-item p {
  margin: 0 0 0.35rem; font-size: 0.92rem; line-height: 1.5; color: var(--rb-muted);
}
.explainer-list { margin: 0; padding: 0; list-style: none; }
.explainer-item {
  border-top: 1px solid var(--rb-card-border);
  padding: 0.85rem 0.15rem;
}
.explainer-item:first-child { border-top: none; padding-top: 0.15rem; }
.explainer-item h3 {
  margin: 0 0 0.25rem; font-size: 1rem; color: var(--rb-cream);
  letter-spacing: 0.02em;
}
.explainer-default {
  margin: 0 0 0.4rem; font-size: 0.75rem; font-weight: 700;
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--rb-accent-sky, var(--rb-link));
}
.explainer-item p {
  margin: 0; font-size: 0.9rem; line-height: 1.5; color: var(--rb-muted);
}
.howto-steps { margin: 0; padding-left: 1.2rem; color: var(--rb-muted); }
.howto-steps li { margin: 0.55rem 0; line-height: 1.5; font-size: 0.92rem; }
.howto-steps strong { color: var(--rb-cream); }
.howto-note {
  margin: 1rem 0 0; font-size: 0.82rem; line-height: 1.45; color: var(--rb-muted);
}
""" + corporate_clients_css() + """
.footer-nav {
  text-align: center; font-size: 0.88rem; color: var(--rb-muted);
}
.footer-nav a { color: var(--rb-link); font-weight: 600; text-decoration: none; }
/* Light mode: --rb-soft stays pale for panel tints - force dark lead text */
[data-theme="light"] .suite-guide-intro .suite-guide-lead,
[data-theme="light"] #suite-guide-lead {
  color: #0f2340;
  font-weight: 600;
}
[data-theme="light"] .suite-guide-intro .suite-guide-foot,
[data-theme="light"] #suite-guide-foot {
  color: #0a2348;
}
[data-theme="light"] .suite-howto-item h3,
[data-theme="light"] .explainer-item h3,
[data-theme="light"] .howto-steps strong {
  color: #0a2348;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]):not([data-theme="light"]) .suite-guide-intro .suite-guide-lead {
    color: #0f2340;
    font-weight: 600;
  }
  :root:not([data-theme="dark"]):not([data-theme="light"]) .suite-howto-item h3,
  :root:not([data-theme="dark"]):not([data-theme="light"]) .explainer-item h3 {
    color: #0a2348;
  }
}
"""


def render_suite_guide_intro_html() -> str:
    """Lead block: human VPN narrative (not residual inventory)."""
    return f"""    <section class="panel-card suite-guide-intro" id="{SUITE_GUIDE_INTRO_ID}"
             aria-labelledby="suite-guide-intro-heading" data-product="suite">
      <h1 class="panel-title" id="suite-guide-intro-heading">{_esc(SUITE_GUIDE_INTRO_HEADING)}</h1>
      <p class="suite-guide-lead" id="suite-guide-lead">{_esc(SUITE_GUIDE_INTRO_BODY)}</p>
      <p class="suite-guide-foot" id="suite-guide-foot">{_esc(SUITE_GUIDE_INTRO_FOOT)}</p>
    </section>
"""


def render_suite_howto_parts_html(
    parts: list[dict[str, str]] | None = None,
) -> str:
    """How-to blocks for free install, residual Connect, Settings gear."""
    items = parts if parts is not None else suite_howto_parts_catalog()
    rows: list[str] = []
    for p in items:
        rows.append(
            f"""      <li class="suite-howto-item" id="howto-{_esc(p['id'])}">
        <h3>{_esc(p['title'])}</h3>
        <p class="explainer-default">Default: {_esc(p['default'])}</p>
        <p class="howto-label">What it is</p>
        <p>{_esc(p['what'])}</p>
        <p class="howto-label">How to use it</p>
        <p>{_esc(p['how'])}</p>
      </li>"""
        )
    inner = "\n".join(rows)
    return f"""    <section class="panel-card" id="{SUITE_HOWTO_PARTS_ID}"
             aria-labelledby="suite-howto-parts-heading" data-product="suite">
      <h2 class="panel-title" id="suite-howto-parts-heading">Using the VPN</h2>
      <ul class="suite-howto-list" id="{SUITE_HOWTO_PARTS_LIST_ID}">
{inner}
      </ul>
    </section>
"""


def render_explainers_box_html(parts: list[dict[str, str]] | None = None) -> str:
    """VPN Settings controls - every control under the gear."""
    items = parts if parts is not None else settings_parts_catalog()
    rows: list[str] = []
    for p in items:
        rows.append(
            f"""      <li class="explainer-item" id="setting-{_esc(p['id'])}">
        <h3>{_esc(p['title'])}</h3>
        <p class="explainer-default">Default: {_esc(p['default'])}</p>
        <p>{_esc(p['body'])}</p>
      </li>"""
        )
    inner = "\n".join(rows)
    return f"""    <section class="panel-card" id="{SETTINGS_EXPLAINERS_BOX_ID}" aria-labelledby="settings-explainers-heading">
      <h2 class="panel-title" id="settings-explainers-heading">VPN Settings - every control</h2>
      <ul class="explainer-list" id="settings-explainer-list">
{inner}
      </ul>
    </section>
"""


def render_install_howto_box_html() -> str:
    """How to install and run — OS steps + Connect; trial/KEYGEN path is intro only."""
    return f"""    <section class="panel-card" id="{INSTALL_HOWTO_BOX_ID}" aria-labelledby="install-howto-heading">
      <h2 class="panel-title" id="install-howto-heading">How to install and run</h2>
      <ol class="howto-steps" id="install-howto-steps">
        <li><strong>Download free</strong> from
          <a href="/" style="color:var(--rb-link);font-weight:700;">restoreprivacy.online</a>
          (FREE DOWNLOAD, or <code>/suite/download</code>).</li>
        <li><strong>Install for your OS.</strong>
          Windows: run the setup exe.
          Android: allow the APK source, then install.
          Linux: extract the tar.gz and run the entry script.
          macOS / iOS: follow the package notes (signed / sideload).</li>
        <li><strong>Accept the end-user licence</strong> on first use
          (local only — Connect waits until you accept).</li>
        <li><strong>Press Connect</strong> on the main screen. Approve any system VPN
          prompt, then wait until status shows connected.</li>
        <li><strong>When you need a KEYGEN</strong> (after the free trial or anytime),
          buy on <code>/pay</code>, then paste the code on the unlock screen or under
          Settings → Payment.</li>
        <li><strong>Optional Settings</strong> for shaping, obfuscation, or multi-hop —
          defaults stay lean. App updates are always a free manual download from the shop.</li>
        <li><strong>Disconnect</strong> when finished. Minimize does not stop the tunnel.
          <strong>Quit</strong> (lower-left) disconnects, then exits the app.</li>
      </ol>
      <p class="howto-note" id="install-howto-note">
        If Connect fails after KEYGEN: re-enter the key, confirm the subscription is
        still active, check firewall / UDP path, and open the
        <a href="/AUDIT.md" style="color:var(--rb-link);">security audit</a>.
      </p>
    </section>
"""


def render_corporate_clients_html() -> str:
    """Yearly corporate retainers — branded admin, VPN, optional dedicated AI."""
    ico_sdk = (
        '<svg class="corp-ico" viewBox="0 0 48 48" aria-hidden="true">'
        '<rect x="6" y="8" width="36" height="32" rx="6" fill="none" stroke="#3ec6ff" stroke-width="2"/>'
        '<path d="M14 18h20M14 24h14M14 30h18" stroke="#1ec8a0" stroke-width="2" fill="none"/>'
        '</svg>'
    )
    ico_db = (
        '<svg class="corp-ico" viewBox="0 0 48 48" aria-hidden="true">'
        '<ellipse cx="24" cy="12" rx="14" ry="6" fill="none" stroke="#7b6cff" stroke-width="2"/>'
        '<path d="M10 12v10c0 3.3 6.3 6 14 6s14-2.7 14-6V12" fill="none" stroke="#7b6cff" stroke-width="2"/>'
        '<path d="M10 22v10c0 3.3 6.3 6 14 6s14-2.7 14-6V22" fill="none" stroke="#3ec6ff" stroke-width="2"/>'
        '</svg>'
    )
    ico_vpn = (
        '<svg class="corp-ico" viewBox="0 0 48 48" aria-hidden="true">'
        '<path d="M24 6l16 7v11c0 10-7 16-16 18C15 40 8 34 8 24V13z" fill="none" stroke="#1ec8a0" stroke-width="2"/>'
        '<path d="M16 24l5 5 11-12" fill="none" stroke="#3ec6ff" stroke-width="2.4"/>'
        '</svg>'
    )
    ico_srv = (
        '<svg class="corp-ico" viewBox="0 0 48 48" aria-hidden="true">'
        '<rect x="8" y="8" width="32" height="10" rx="2" fill="none" stroke="#3ec6ff" stroke-width="2"/>'
        '<rect x="8" y="21" width="32" height="10" rx="2" fill="none" stroke="#1ec8a0" stroke-width="2"/>'
        '<rect x="8" y="34" width="32" height="8" rx="2" fill="none" stroke="#7b6cff" stroke-width="2"/>'
        '<circle cx="14" cy="13" r="1.4" fill="#3ec6ff"/>'
        '<circle cx="14" cy="26" r="1.4" fill="#1ec8a0"/>'
        '</svg>'
    )
    ico_ai = (
        '<svg class="corp-ico" viewBox="0 0 48 48" aria-hidden="true">'
        '<circle cx="24" cy="24" r="8" fill="none" stroke="#7b6cff" stroke-width="2"/>'
        '<path d="M24 8v6M24 34v6M8 24h6M34 24h6M12 12l4 4M32 32l4 4M12 36l4-4M32 16l4-4" stroke="#3ec6ff" stroke-width="2"/>'
        '</svg>'
    )
    cards = (
        ("MISHI admin SDK", "Blank-canvas branded admin guide that grows into a full organisational structure.", ico_sdk),
        ("Up to 5 databases", "Dedicated data stores for the organisation — not shared tenant tables.", ico_db),
        ("Branded VPN", "A fully branded residual Packet Tunnel network for the corporate estate.", ico_vpn),
        ("Dedicated server", "Own server for the year — not a shared consumer node.", ico_srv),
        ("Branded AI add-on", "Optional model that learns from the organisation's workflow and workforce.", ico_ai),
    )
    card_html = []
    for title, body, ico in cards:
        card_html.append(
            f'        <article class="corp-card">'
            f"{ico}<h3>{_esc(title)}</h3><p>{_esc(body)}</p></article>"
        )
    meters = (
        ("Residual full tunnel", "98%"),
        ("Dual-stack residual capture", "96%"),
        ("No-log / local-only client", "99%"),
        ("Dedicated estate isolation", "95%"),
        ("Governance controls (admin + audit)", "94%"),
    )
    meter_html = []
    for lab, pct in meters:
        meter_html.append(
            f'        <div class="corp-meter-row">'
            f'<div class="corp-meter-lab"><span>{_esc(lab)}</span><span>{pct}</span></div>'
            f'<div class="corp-meter-track"><span class="corp-meter-fill" style="width:{pct}"></span></div>'
            f"</div>"
        )
    return f"""    <section class="panel-card corporate-clients" id="{CORPORATE_CLIENTS_BOX_ID}"
             aria-labelledby="corporate-clients-heading">
      <h2 class="panel-title" id="corporate-clients-heading">{_esc(CORPORATE_CLIENTS_HEADING)}</h2>
      <p class="corp-lead" id="corporate-clients-body">{_esc(CORPORATE_CLIENTS_BODY)}</p>
      <div class="corp-icon-grid" id="corporate-clients-icons">
{''.join(card_html)}
      </div>
      <div class="corp-meters" id="corporate-clients-graphs" aria-label="Privacy-preserving coverage">
{''.join(meter_html)}
      </div>
      <div class="corp-price-row" id="corporate-clients-pricing">
        <div class="corp-price">
          <p class="corp-price-k">Corporate retainer</p>
          <p class="corp-price-n">£30,000</p>
          <p>Branded admin (MISHI), up to 5 databases, branded VPN, dedicated server — one year.</p>
        </div>
        <div class="corp-price">
          <p class="corp-price-k">Dedicated branded AI</p>
          <p class="corp-price-n">+ £27,000</p>
          <p id="corporate-clients-ai">{_esc(CORPORATE_CLIENTS_AI)}</p>
        </div>
      </div>
      <p class="corporate-clients-foot" id="corporate-clients-foot">{_esc(CORPORATE_CLIENTS_FOOT)}</p>
    </section>
    <script>
    (function () {{
      var box = document.getElementById({CORPORATE_CLIENTS_BOX_ID!r});
      if (!box) return;
      if (location.pathname === "/sdk" || location.hash === "#corporate-clients") {{
        box.scrollIntoView({{behavior: "smooth", block: "start"}});
      }}
    }})();
    </script>
"""

def render_settings_explainer_page_html(
    *, title: str | None = None, active: str = "settings"
) -> bytes:
    """Full VPN settings guide: intro, how-to parts, Settings controls, install steps."""
    try:
        from public_chrome import (
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_display_title,
            public_head_open,
            public_page_close,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_display_title,
            public_head_open,
            public_page_close,
        )

    brand = public_display_title(title if title is not None else PUBLIC_BRAND_TITLE)
    intro = render_suite_guide_intro_html()
    howto_parts = render_suite_howto_parts_html()
    explainers = render_explainers_box_html(settings_parts_catalog())
    howto = render_install_howto_box_html()
    corporate = render_corporate_clients_html()
    css = _shared_shell_css()
    header = public_brand_header_html(
        title=brand,
        active=active if active in {"settings", "sdk"} else "settings",
    )
    page_title = f"Settings guide - {brand}"
    body = f"""{public_head_open(title=page_title, extra_css=css)}
  <div class="page-shell" id="settings-explainer-page" data-product="suite">
{header}
{intro}
{howto_parts}
{explainers}
{howto}
{corporate}
    <section class="panel-card footer-nav" id="settings-explainer-footer">
      <p style="margin:0;">Use <strong>Home</strong> in the header for free downloads and KEYGEN checkout.</p>
    </section>
  </div>
{public_page_close()}
"""
    return body.encode("utf-8")


def settings_explainer_paths() -> frozenset[str]:
    """All URL paths that serve the settings explainer page."""
    return frozenset({SETTINGS_EXPLAINER_PATH, *SETTINGS_EXPLAINER_ALIASES})


def catalog_ids() -> list[str]:
    return [p["id"] for p in settings_parts_catalog()]


def suite_howto_ids() -> list[str]:
    return [p["id"] for p in suite_howto_parts_catalog()]


def suite_guide_copy_is_valid(html_or_text: str = "") -> bool:
    """Structural honesty for tests: VPN story present; forbidden wording banned."""
    blob = (html_or_text or "").lower()
    if "paywall" in blob:
        return False
    # Prefer full page; also allow checking intro constants alone.
    sample = blob if blob.strip() else (
        f"{SUITE_GUIDE_INTRO_BODY} {SUITE_GUIDE_INTRO_FOOT}".lower()
    )
    if "paywall" in sample:
        return False
    # Dedicated VPN product - no multi-product wallet/analysis pitch required.
    need = ("keygen", "free", "vpn")
    if not all(n in sample for n in need):
        return False
    for banned in ("perccent", "evolve tab", "vpn, %, and evolve", "% tab"):
        if banned in sample:
            return False
    return True
