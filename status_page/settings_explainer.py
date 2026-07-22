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
            "periodic cover frames. ON (default) = stronger fingerprint resistance; "
            "OFF = snappier browsing with weaker traffic-analysis resistance."
        )
        obfs = (
            "Outer obfuscation wraps residual UDP in a QUIC-like shell. "
            "ON (default) = better blend with encrypted UDP; OFF = bare RPT frames."
        )
        multi = (
            "Multi-hop residual routes via an exit hop so egress IP is the exit. "
            "OFF (default) = single hop to Iceland entry (lower lag). ON = exit path."
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
                "When ON, Privacy Restored opens when you sign in to Windows "
                "(Startup-folder shortcut). Default OFF so the app only runs when "
                "you open it. Does not by itself Connect residual VPN."
            ),
        },
        {
            "id": "autoconnect-on-launch",
            "title": "Autoconnect on launch",
            "default": "Off",
            "body": (
                "When ON, a cold start of the app starts Connect automatically "
                "(after licence + keygen unlock). Default OFF — Connect is manual. "
                "Autoconnect still respects licence acceptance and keygen entitlement; "
                "it never skips unlock."
            ),
        },
        {
            "id": "core-vpn",
            "title": "Residual VPN core (always required)",
            "default": "Always on",
            "body": core,
        },
        {
            "id": "traffic-shaping",
            "title": "Traffic shaping (pad / jitter / cover)",
            "default": "On",
            "body": shape,
        },
        {
            "id": "outer-obfuscation",
            "title": "Outer obfuscation (QUIC-mimic wrap)",
            "default": "On",
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
                "(Romania). Uses a short UDP/TCP probe — not a browser speedbench "
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
                "After paying on restoreprivacy.online, your email includes a keygen "
                "(format RPT-KEY-…) with USE THIS KEYGEN TO UNLOCK YOUR RESTORE "
                "PRIVACY TRIAL. Enter it in the forced unlock dialog (or Settings → "
                "Payment entitlement / keygen). Download alone does not unlock "
                "residual HELLO. Connect only works while your subscription/payment "
                "is active; refunds or failed charges cancel Connect for that install."
            ),
        },
        {
            "id": "connection-log",
            "title": "Local connection log",
            "default": "On-device only",
            "body": (
                "Settings can show and export a local connection event log for "
                "transparency. Events stay on your device — they are not shipped "
                "to the node as a user dossier."
            ),
        },
        {
            "id": "leak-test",
            "title": "Leak test",
            "default": "Optional diagnostic",
            "body": (
                "Optional product leak test from Settings checks residual honesty "
                "signals (e.g. capture / DNS expectations). It is a local diagnostic "
                "aid — not a third-party web leak site phone-home."
            ),
        },
        {
            "id": "docs-links",
            "title": "Audit, privacy policy, and licence links",
            "default": "Open in browser",
            "body": (
                "Settings links to the public security audit (AUDIT.md), privacy "
                "policy, and end-user licence on the status host so you can review "
                "product honesty documents without a public source tree."
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
      <p class="tagline" style="text-align:center;margin:0 auto 1rem;display:block;">
        Product Settings (Windows desktop primary; Linux mirrors privacy-scale where shipped).
        Optional privacy layers can be scaled for speed; residual VPN core and keygen stay required.
      </p>
      <ul class="explainer-list" id="settings-explainer-list">
{inner}
      </ul>
    </section>
"""


def render_install_howto_box_html() -> str:
    """Second box: detailed how-to install and run (below explainers)."""
    return """    <section class="panel-card" id="install-run-howto-box" aria-labelledby="install-howto-heading">
      <h2 class="panel-title" id="install-howto-heading">How to install and run Restore Privacy</h2>
      <ol class="howto-steps" id="install-howto-steps">
        <li><strong>Pay on the status page.</strong> Open
          <a href="/" style="color:var(--rb-link);font-weight:700;">restoreprivacy.online</a>
          (use <strong>Home</strong> in the header). Choose your platform and complete Stripe
          checkout (£2.45/month after the 7-day trial wording on the catalog).</li>
        <li><strong>Download starts after payment.</strong> Use the one-time download link
          (and the email with download + keygen). Packages are not free permanent public
          GitHub installs.</li>
        <li><strong>Install the package for your OS.</strong>
          Windows: run the setup exe (Administrator may be required later for residual tunnel).
          Android: allow install from the file source, then open the APK.
          Linux: extract the tar.gz and run the product entry script.
          macOS / iOS: follow the package README (signed/sideload per catalog notes).</li>
        <li><strong>Accept the end-user licence</strong> on first use (Settings or the licence
          prompt). Acceptance is local only — Connect stays blocked until you accept.</li>
        <li><strong>Enter your keygen unlock code</strong> from the fulfilment email
          (RPT-KEY-… / USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL).
          Use the forced unlock dialog — download alone does not unlock residual VPN.</li>
        <li><strong>Press Connect.</strong> Approve Administrator/root elevation when asked so
          residual public IP uses the VPN node. Wait until the app reports residual capture
          active before relying on the tunnel.</li>
        <li><strong>Optional — Settings privacy scale.</strong> Turn traffic shaping or outer
          obfuscation OFF for a snappier residual feel (weaker traffic analysis resistance).
          Multi-hop ON uses the exit path (higher latency). Changes hot-apply while connected
          where the product supports it (multi-hop re-establishes residual).</li>
        <li><strong>Optional — Measure ping</strong> in Settings to see device→entry (and
          device→exit when multi-hop is on) RTT. Not a contractual speed SLA.</li>
        <li><strong>Disconnect</strong> from the app when finished. Residual routing stops when
          you Disconnect (or Quit, depending on platform shell).</li>
      </ol>
      <p class="howto-note" id="install-howto-note">
        If Connect fails after payment: re-enter the keygen, confirm your subscription is
        still active, check Windows Firewall / UDP path, and review the public
        <a href="/AUDIT.md" style="color:var(--rb-link);">security audit</a>.
        Support docs: Privacy Policy and licence are linked from the homepage.
      </p>
    </section>
"""


def render_settings_explainer_page_html(*, title: str = "RESTORE PRIVACY") -> bytes:
    """Full settings explainer page: shared brand header (no BUY NOW), explainers + how-to."""
    try:
        from public_chrome import (
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )

    parts = settings_parts_catalog()
    explainers = render_explainers_box_html(parts)
    howto = render_install_howto_box_html()
    css = _shared_shell_css()
    header = public_brand_header_html(
        title=title,
        tagline=(
            "Client Settings guide — what every control does, and how to install & run"
        ),
        active="settings",
        logo_size=88,
    )
    body = f"""{public_head_open(title=f"Client Settings guide — {title}", extra_css=css)}
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
