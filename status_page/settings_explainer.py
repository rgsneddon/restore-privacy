"""Public Settings explainer page — homepage-style shell + install how-to.

Pure HTML builders (no live server required for unit tests). Content tracks
shipped Windows Settings surfaces and ``client.product_policy`` EXPLAINER_*
copy so the page stays aligned with the product client.
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


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def settings_parts_catalog() -> list[dict[str, str]]:
    """Each separate part of the product client Settings tab (Windows primary).

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
            "Always on: licence + keygen entitlement, cryptographic HELLO/session, "
            "and system residual tunnel. Those cannot be turned off in Settings."
        )

    return [
        {
            "id": "run-at-startup",
            "title": "Run at device startup",
            "default": "Off",
            "body": (
                "When ON, the app opens at Windows sign-in (Startup-folder shortcut). "
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
                "and keygen unlock. Default OFF — Connect is manual. Unlock is never skipped."
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
                "protected. USING IPV4 ONLY MAY CAUSE DATA LEAKS on dual-stack networks. "
                "Changing IPv6 Settings while residual is connected disconnects first, "
                "then saves for the next Connect (no mid-session hot-apply)."
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
                "Settings shows best-effort RTT from your device to the product "
                "entry node (Iceland) and, when multi-hop is ON, to the exit node "
                "(Germany exit when multi-hop is on). Uses a short UDP/TCP probe — not a browser speedbench "
                "SLA. Tap Measure ping now to refresh; values may show n/a if the "
                "host is unreachable from your network."
            ),
        },
        {
            "id": "licence",
            "title": "End-user licence",
            "default": "Must accept before Connect",
            "body": (
                "Connect stays blocked until you accept the end-user licence on "
                "this device. Acceptance is stored only locally (not uploaded to "
                "the node). After accept, enter the fulfilment keygen to unlock "
                "residual VPN."
            ),
        },
        {
            "id": "keygen",
            "title": "Payment entitlement / keygen unlock",
            "default": "Required for Connect",
            "body": (
                "After you pay on restoreprivacy.online, email delivers a keygen "
                "(RPT-KEY-…). Enter it in the forced unlock dialog (Settings → "
                "Payment entitlement is a fallback). Download alone does not unlock "
                "residual HELLO. Connect only works while the subscription is active; "
                "refunds or failed charges cancel Connect until you renew."
            ),
        },
        {
            "id": "connection-log",
            "title": "Local connection log",
            "default": "On-device only",
            "body": (
                "Settings can show and export a local connection log. Events stay on "
                "your device — they are not uploaded to the node."
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
    """Homepage banner between brand panel and downloads section."""
    href = _esc(HOMEPAGE_SETTINGS_BANNER_HREF)
    return f"""    <aside class="panel-card settings-banner" id="{HOMEPAGE_SETTINGS_BANNER_ID}" aria-label="Client Settings guide">
      <p class="settings-banner-kicker">New to the app?</p>
      <p class="settings-banner-title">Client Settings explained</p>
      <p class="settings-banner-blurb">
        Learn every Settings control — privacy scale, keygen unlock, ping stats, and more —
        plus a full install &amp; run guide.
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
"""


def render_explainers_box_html(parts: list[dict[str, str]] | None = None) -> str:
    """First box: full Settings tab part explainers."""
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
    return f"""    <section class="panel-card" id="settings-explainers-box" aria-labelledby="settings-explainers-heading">
      <h2 class="panel-title" id="settings-explainers-heading">Client Settings — every control</h2>
      <ul class="explainer-list" id="settings-explainer-list">
{inner}
      </ul>
    </section>
"""


def render_install_howto_box_html() -> str:
    """Second box: how to install and run (below explainers)."""
    return """    <section class="panel-card" id="install-run-howto-box" aria-labelledby="install-howto-heading">
      <h2 class="panel-title" id="install-howto-heading">How to install and run</h2>
      <ol class="howto-steps" id="install-howto-steps">
        <li><strong>Pay on the status page.</strong> Open
          <a href="/" style="color:var(--rb-link);font-weight:700;">restoreprivacy.online</a>,
          choose your platform and plan (Monthly £3.00 or Yearly £30.00), and
          complete Stripe Checkout.</li>
        <li><strong>Download after payment.</strong> Use the 1-hour download link on the success page
          (retry if the connection drops; email also has download + keygen).
          These are not free permanent GitHub installs.</li>
        <li><strong>Install for your OS.</strong>
          Windows: run the setup exe (Admin may be needed later for residual).
          Android: allow the APK source, then install.
          Linux: extract the tar.gz and run the entry script.
          macOS / iOS: follow the package notes (signed / sideload).</li>
        <li><strong>Accept the end-user licence</strong> on first use. Acceptance is local only —
          Connect stays blocked until you accept.</li>
        <li><strong>Enter the keygen</strong> from email (RPT-KEY-…).
          Use the forced unlock dialog — download alone does not unlock residual VPN.</li>
        <li><strong>Press Connect.</strong> Approve elevation when asked so residual public IP
          uses the VPN node. Wait until residual capture is active before relying on it.</li>
        <li><strong>Optional Settings.</strong> Traffic shaping / outer obfuscation OFF feels
          snappier (weaker traffic-analysis resistance). Multi-hop ON uses the exit path
          (higher latency). Measure ping shows device→entry (and exit when multi-hop is on) —
          not a speed SLA.</li>
        <li><strong>Disconnect</strong> when finished. Residual routing stops on Disconnect
          (or Quit, depending on platform).</li>
      </ol>
      <p class="howto-note" id="install-howto-note">
        If Connect fails after payment: re-enter the keygen, confirm the subscription is
        still active, check firewall / UDP path, and open the
        <a href="/AUDIT.md" style="color:var(--rb-link);">security audit</a>.
        Privacy policy and licence are linked from the homepage.
      </p>
    </section>
"""


def render_settings_explainer_page_html(*, title: str | None = None) -> bytes:
    """Full settings explainer page: shared brand header (no BUY NOW), explainers + how-to."""
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
    parts = settings_parts_catalog()
    explainers = render_explainers_box_html(parts)
    howto = render_install_howto_box_html()
    css = _shared_shell_css()
    header = public_brand_header_html(
        title=brand,
        active="settings",
        logo_size=112,
    )
    body = f"""{public_head_open(title=f"Client Settings guide — {brand}", extra_css=css)}
  <div class="page-shell" id="settings-explainer-page">
{header}
{explainers}
{howto}
    <section class="panel-card footer-nav" id="settings-explainer-footer">
      <p style="margin:0;">Use <strong>Home</strong> in the header to return to downloads and pay.</p>
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
