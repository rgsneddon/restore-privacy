"""Public Settings / Suite guide — human how-to for every Suite part.

Pure HTML builders (no live server required for unit tests). Framed for
**Restore Privacy Suite**: free install, KEYGEN unlock, VPN / % / EVOLVE tabs,
and VPN Settings controls in plain language.
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
)

# Homepage banner target (same path)
HOMEPAGE_SETTINGS_BANNER_ID = "settings-explainer-banner"
HOMEPAGE_SETTINGS_BANNER_HREF = SETTINGS_EXPLAINER_PATH

# Page structure markers (tests + progressive hooks)
SUITE_GUIDE_INTRO_ID = "suite-guide-intro"
SUITE_HOWTO_PARTS_ID = "suite-howto-parts"
SUITE_HOWTO_PARTS_LIST_ID = "suite-howto-parts-list"
SETTINGS_EXPLAINERS_BOX_ID = "settings-explainers-box"
INSTALL_HOWTO_BOX_ID = "install-run-howto-box"

SUITE_GUIDE_INTRO_HEADING = "How to use Restore Privacy Suite"
SUITE_GUIDE_INTRO_BODY = (
    "This guide walks you through the whole app in everyday language. "
    "Download the Suite for free. Residual Connect includes a free 3-day "
    "(72-hour) trial on this device (no card). After the trial ends, enter a "
    "KEYGEN to continue. Then use the three tabs — VPN, %, and EVOLVE — and the "
    "Settings that sit behind the gear on the VPN tab."
)
SUITE_GUIDE_INTRO_FOOT = (
    "Nothing here is an operator console. Installers are free; residual Connect "
    "has a free 3-day (72-hour) trial, then needs a paid KEYGEN / active "
    "subscription (monthly from £3). The unlock screen is for your KEYGEN after "
    "the trial — not for card details before you try residual Connect."
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
    """How to utilise each major Suite surface (human cadence).

    Keys: id, title, what, how, default.
    """
    return [
        {
            "id": "suite-unlock",
            "title": "Free install, 3-day trial, then KEYGEN",
            "what": (
                "You install Restore Privacy Suite without paying for the package. "
                "Residual Connect includes a free 3-day (72-hour) trial on this "
                "device (no card). After the trial ends, enter a KEYGEN from your "
                "fulfilment email to keep connecting."
            ),
            "how": (
                "Download your platform build from the homepage free installer grid "
                "(or /suite/download). Open the app, accept the end-user licence, "
                "use the free residual trial, then when it ends enter the KEYGEN "
                "(RPT-KEY-…) on the unlock screen or under Settings → Payment "
                "entitlement. A monthly licence starts at £3; yearly residual plans "
                "remain on /pay if you prefer that option."
            ),
            "default": "Download free; 72h residual trial; then KEYGEN",
        },
        {
            "id": "suite-vpn",
            "title": "VPN tab — residual Connect",
            "what": (
                "The VPN tab is where you start and stop residual protection. "
                "It shows connection status, a short local log, entry country, "
                "and a discrete notice when a newer Suite monopin is available "
                "(manual free download)."
            ),
            "how": (
                "Choose an entry country if you like (Germany is the product default), "
                "then press Connect and approve any system VPN prompt. Wait until "
                "status is honestly connected before you rely on residual IP. "
                "Press Disconnect when you are done — minimize does not stop the tunnel."
            ),
            "default": "Manual Connect; entry Germany (DE)",
        },
        {
            "id": "suite-wallet",
            "title": "% tab — private wallet",
            "what": (
                "The % tab is Perccent wallet inside the Suite shell. It is a separate "
                "surface for wallet work — not a second residual tunnel."
            ),
            "how": (
                "Open the % tab from the bottom navigation. Use the wallet UI there for "
                "local wallet actions. Residual Connect still lives only on the VPN tab; "
                "your KEYGEN story is shared across the Suite."
            ),
            "default": "Available after unlock; not residual Connect",
        },
        {
            "id": "suite-evolve",
            "title": "EVOLVE tab — analysis",
            "what": (
                "EVOLVE is the analysis surface in the same Suite app. It sits beside "
                "VPN and % so you do not juggle three installers."
            ),
            "how": (
                "Select EVOLVE from the bottom navigation and use the tools shown there. "
                "It does not replace Connect; for residual public IP, return to VPN and "
                "Connect while your KEYGEN is active."
            ),
            "default": "Available after unlock; analysis only",
        },
        {
            "id": "suite-settings-gear",
            "title": "VPN Settings (gear on the VPN tab)",
            "what": (
                "Settings under the VPN gear cover power-up, residual privacy scale, "
                "KEYGEN fallback, local log, leak test, and legal links."
            ),
            "how": (
                "Tap the gear on the VPN tab. Defaults are lean: startup and autoconnect "
                "off, traffic shaping / outer obfuscation / multi-hop off. "
                "Turn on only what you understand. Each control is listed below. "
                "Suite updates are always manual (free download) when a new monopin ships."
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
            "OFF (default) = single hop to entry (default Germany). ON = exit path."
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
                "Default OFF — it only runs when you launch it. This does not Connect "
                "the VPN by itself."
            ),
        },
        {
            "id": "autoconnect-on-launch",
            "title": "Autoconnect on launch",
            "default": "Off",
            "body": (
                "When ON, opening the app starts Connect automatically after licence "
                "and KEYGEN unlock. Default OFF — Connect is manual. Unlock is never skipped."
            ),
        },
        {
            "id": "suite-manual-update",
            "title": "Suite updates (manual only)",
            "default": "Manual free download",
            "body": (
                "Operators do not remote-install Suite packages onto your device. "
                "When a newer Suite monopin is available, the app shows a discrete "
                "“new version available” notice. Download the free Suite package for "
                "your platform from the public shop and install it yourself — "
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
                "defaults ON and remains optional — turning IPv6 residual OFF means "
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
                "a rough sense of path health — not a speedbench SLA. Values may show "
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
            "default": "Required for Connect",
            "body": (
                "Installers are free. Residual Connect needs a KEYGEN after you take "
                "a monthly licence (from £3) on restoreprivacy.online — email delivers "
                "RPT-KEY-…. Enter it on the unlock screen or Settings → Payment "
                "entitlement. Download alone does not unlock residual HELLO. Connect "
                "only works while the subscription is active; refunds or failed charges "
                "stop Connect until you renew."
            ),
        },
        {
            "id": "connection-log",
            "title": "Local connection log",
            "default": "On-device only",
            "body": (
                "Settings can show and export a local connection log. Events stay on "
                "your device — they are not uploaded to the node. Export only if you "
                "choose to email support yourself."
            ),
        },
        {
            "id": "leak-test",
            "title": "Leak test",
            "default": "Optional diagnostic",
            "body": (
                "Optional residual honesty checks from Settings (capture / DNS). "
                "Local diagnostic only — not a third-party leak site."
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
    return f"""    <aside class="panel-card settings-banner" id="{HOMEPAGE_SETTINGS_BANNER_ID}" aria-label="Suite Settings guide">
      <p class="settings-banner-kicker">New to the Suite?</p>
      <p class="settings-banner-title">How to use every part</p>
      <p class="settings-banner-blurb">
        Free install, KEYGEN unlock, VPN / % / EVOLVE, and every Settings control —
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
.footer-nav {
  text-align: center; font-size: 0.88rem; color: var(--rb-muted);
}
.footer-nav a { color: var(--rb-link); font-weight: 600; text-decoration: none; }
/* Light mode: --rb-soft stays pale for panel tints — force dark lead text */
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
    """Lead block: human Suite narrative (not residual inventory)."""
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
    """How-to blocks for free install, VPN, %, EVOLVE, Settings gear."""
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
      <h2 class="panel-title" id="suite-howto-parts-heading">Each part of the Suite</h2>
      <ul class="suite-howto-list" id="{SUITE_HOWTO_PARTS_LIST_ID}">
{inner}
      </ul>
    </section>
"""


def render_explainers_box_html(parts: list[dict[str, str]] | None = None) -> str:
    """VPN Settings controls — every control under the gear."""
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
      <h2 class="panel-title" id="settings-explainers-heading">VPN Settings — every control</h2>
      <ul class="explainer-list" id="settings-explainer-list">
{inner}
      </ul>
    </section>
"""


def render_install_howto_box_html() -> str:
    """How to install and run: free Suite download + KEYGEN + Connect."""
    return f"""    <section class="panel-card" id="{INSTALL_HOWTO_BOX_ID}" aria-labelledby="install-howto-heading">
      <h2 class="panel-title" id="install-howto-heading">How to install and run</h2>
      <ol class="howto-steps" id="install-howto-steps">
        <li><strong>Download the Suite for free.</strong> Open
          <a href="/" style="color:var(--rb-link);font-weight:700;">restoreprivacy.online</a>
          and pick your platform from the free installer grid (or use
          <code>/suite/download</code>). You do not pay for the package itself.</li>
        <li><strong>Install for your OS.</strong>
          Windows: run the setup exe (Admin may be needed later for residual).
          Android: allow the APK source, then install.
          Linux: extract the tar.gz and run the entry script.
          macOS / iOS: follow the package notes (signed / sideload).</li>
        <li><strong>Accept the end-user licence</strong> on first use. Acceptance is local only —
          Connect stays blocked until you accept.</li>
        <li><strong>Free residual trial — 3 days (72 hours).</strong>
          After first-run setup, residual Connect can run without a card or KEYGEN
          for 72 hours on this device. No payment details are required to start
          the trial.</li>
        <li><strong>Get a KEYGEN when the trial ends</strong> (or anytime you prefer).
          Take a monthly licence from £3 on the site (or a yearly residual plan on
          <code>/pay</code>). Email delivers KEYGEN (<code>RPT-KEY-…</code>) after checkout.</li>
        <li><strong>Enter the KEYGEN</strong> on the unlock screen (or Settings → Payment entitlement)
          after the free trial if you want to continue residual Connect.</li>
        <li><strong>Press Connect</strong> on the VPN tab. Approve elevation / VPN permission when asked
          so residual public IP uses the product path. Wait until status is honestly connected.</li>
        <li><strong>Optional Settings.</strong> Traffic shaping / outer obfuscation OFF feels
          snappier (weaker traffic-analysis resistance). Multi-hop ON uses the exit path
          (higher latency). Suite updates are always <strong>manual</strong> — when a new
          monopin is available, download free from the shop (no operator push packages).</li>
        <li><strong>Use % and EVOLVE</strong> from the bottom tabs when you need wallet or analysis.
          They share the same unlock story; residual traffic still starts on VPN → Connect.</li>
        <li><strong>Disconnect</strong> when finished. Residual routing stops on Disconnect
          (or Quit, depending on platform). Minimize keeps the tunnel until you Disconnect.</li>
      </ol>
      <p class="howto-note" id="install-howto-note">
        If Connect fails after KEYGEN: re-enter the key, confirm the subscription is
        still active, check firewall / UDP path, and open the
        <a href="/AUDIT.md" style="color:var(--rb-link);">security audit</a>.
        Privacy policy and licence are linked from the homepage and Settings.
      </p>
    </section>
"""


def render_settings_explainer_page_html(*, title: str | None = None) -> bytes:
    """Full Suite settings guide: intro, how-to parts, Settings controls, install steps."""
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
    css = _shared_shell_css()
    header = public_brand_header_html(
        title=brand,
        active="settings",
    )
    page_title = f"Settings guide — {brand}"
    body = f"""{public_head_open(title=page_title, extra_css=css)}
  <div class="page-shell" id="settings-explainer-page" data-product="suite">
{header}
{intro}
{howto_parts}
{explainers}
{howto}
    <section class="panel-card footer-nav" id="settings-explainer-footer">
      <p style="margin:0;">Use <strong>Home</strong> in the header for free Suite downloads and KEYGEN checkout.</p>
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
    """Structural honesty for tests: Suite story present; forbidden wording banned."""
    blob = (html_or_text or "").lower()
    if "paywall" in blob:
        return False
    # Prefer full page; also allow checking intro constants alone.
    sample = blob if blob.strip() else (
        f"{SUITE_GUIDE_INTRO_BODY} {SUITE_GUIDE_INTRO_FOOT}".lower()
    )
    if "paywall" in sample:
        return False
    need = ("keygen", "free", "vpn", "evolve")
    return all(n in sample for n in need)
