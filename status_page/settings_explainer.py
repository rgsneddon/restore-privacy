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
    """CSS fragment injected into homepage for the mid-page settings banner."""
    return """
    .settings-banner {
      text-align: center;
      background: linear-gradient(165deg, rgba(38, 148, 232, 0.18) 0%, var(--rb-card) 60%);
      border-color: rgba(116, 178, 226, 0.45);
    }
    .settings-banner-kicker {
      margin: 0 0 0.35rem; font-size: 0.72rem; letter-spacing: 0.14em;
      text-transform: uppercase; font-weight: 700; color: var(--rb-accent);
    }
    .settings-banner-title {
      margin: 0 0 0.45rem; font-size: clamp(1.05rem, 3vw, 1.25rem);
      font-weight: 800; color: var(--rb-cream); letter-spacing: 0.04em;
    }
    .settings-banner-blurb {
      margin: 0 auto 0.85rem; max-width: 36rem; font-size: 0.88rem;
      line-height: 1.45; color: var(--rb-muted);
    }
    .settings-banner-actions { margin: 0; }
    .settings-banner-link {
      display: inline-block; font-weight: 800; letter-spacing: 0.04em;
      color: var(--rb-navy); background: var(--rb-accent);
      text-decoration: none; padding: 0.55rem 1.15rem; border-radius: 999px;
      box-shadow: 0 6px 18px rgba(0,0,0,0.25);
    }
    .settings-banner-link:hover {
      background: #fff3a0; color: var(--rb-navy);
    }
"""


def _shared_shell_css() -> str:
    """Same navy/card/cream language as the main homepage."""
    return """
    :root {
      --rb-navy: #0a1628;
      --rb-navy-mid: #0f2340;
      --rb-card: #132a4a;
      --rb-card-border: rgba(174, 208, 234, 0.28);
      --rb-cream: #f2f5f7;
      --rb-muted: #aed0ea;
      --rb-link: #74b2e2;
      --rb-link-hover: #d7ebf9;
      --rb-accent: #f9dd34;
      --rb-btn: #2694e8;
      --rb-btn-deep: #1a6fad;
      --rb-soft: #deedf7;
      --rb-radius: 16px;
      --rb-max: 56rem;
    }
    *, *::before, *::after { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; display: flex; flex-direction: column;
      align-items: center; background:
        radial-gradient(1200px 600px at 50% -10%, #1a3a66 0%, transparent 55%),
        linear-gradient(180deg, var(--rb-navy-mid) 0%, var(--rb-navy) 45%, #07101c 100%);
      color: var(--rb-cream);
      font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
      padding: clamp(1rem, 3vw, 2.5rem) 0 3rem;
    }
    .page-shell {
      width: min(100% - 1.5rem, var(--rb-max));
      display: flex; flex-direction: column; gap: 1.15rem;
      margin: 0 auto;
    }
    .panel-card {
      background: linear-gradient(165deg, rgba(26, 58, 102, 0.55) 0%, var(--rb-card) 55%);
      border: 1px solid var(--rb-card-border);
      border-radius: var(--rb-radius);
      padding: clamp(1rem, 2.5vw, 1.45rem);
      box-shadow: 0 10px 32px rgba(4, 12, 28, 0.35);
    }
    .panel-title {
      margin: 0 0 0.85rem; font-size: 0.95rem; letter-spacing: 0.12em;
      text-transform: uppercase; font-weight: 700; color: var(--rb-soft);
      text-align: center;
    }
    .brand-panel {
      display: flex; flex-direction: column; align-items: center;
      text-align: center; gap: 0.65rem;
    }
    .brand-logo {
      width: clamp(64px, 12vw, 88px); height: clamp(64px, 12vw, 88px);
      border-radius: 18px; object-fit: cover;
      box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
      border: 2px solid rgba(174, 208, 234, 0.35);
    }
    h1 {
      letter-spacing: 0.1em; font-weight: 700;
      font-size: clamp(1.25rem, 4vw, 1.85rem);
      margin: 0; color: var(--rb-cream);
    }
    .tagline {
      margin: 0; max-width: 34rem; font-size: clamp(0.85rem, 2.4vw, 0.98rem);
      line-height: 1.45; color: var(--rb-muted); font-weight: 500;
    }
    .buy-now-row { margin: 0.35rem 0 0; }
    .buy-now-btn {
      display: inline-block; font-weight: 800; letter-spacing: 0.06em;
      text-transform: uppercase; text-decoration: none;
      color: var(--rb-navy); background: var(--rb-accent);
      padding: 0.65rem 1.4rem; border-radius: 999px;
      box-shadow: 0 8px 22px rgba(0,0,0,0.28);
    }
    .buy-now-btn:hover { background: #fff3a0; color: var(--rb-navy); }
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
      letter-spacing: 0.06em; text-transform: uppercase; color: var(--rb-accent);
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
    .footer-nav a:hover { color: var(--rb-link-hover); }
    @media (max-width: 520px) {
      .page-shell { width: min(100% - 1rem, var(--rb-max)); gap: 0.9rem; }
    }
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
          (or use <strong>BUY NOW</strong> above). Choose your platform and complete Stripe
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
    """Full settings explainer page: homepage shell, BUY NOW → home, explainers + how-to."""
    title_safe = _esc(title)
    parts = settings_parts_catalog()
    explainers = render_explainers_box_html(parts)
    howto = render_install_howto_box_html()
    css = _shared_shell_css()
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Client Settings guide — {title_safe}</title>
  <link rel="icon" href="/favicon.ico" type="image/x-icon"/>
  <link rel="icon" href="/favicon.png" type="image/png" sizes="32x32"/>
  <link rel="apple-touch-icon" href="/apple-touch-icon.png"/>
  <style>
{css}
  </style>
</head>
<body>
  <div class="page-shell" id="settings-explainer-page">
    <header class="brand-panel panel-card" id="settings-explainer-header">
      <img class="brand-logo" src="/logo.png" width="88" height="88" alt="Restore Privacy logo"/>
      <h1>{title_safe}</h1>
      <p class="tagline">Client Settings guide — what every control does, and how to install &amp; run</p>
      <p class="buy-now-row">
        <a class="buy-now-btn" id="settings-explainer-buy-now" href="/">BUY NOW</a>
      </p>
      <p class="footer-nav" style="margin:0.65rem 0 0;">
        <a href="/">← Back to status &amp; downloads</a>
        · <a href="/AUDIT.md">Security audit</a>
        · <a href="/PRIVACY_POLICY.md">Privacy policy</a>
      </p>
    </header>
{explainers}
{howto}
    <section class="panel-card footer-nav" id="settings-explainer-footer">
      <p style="margin:0 0 0.75rem;">Ready to restore your privacy?</p>
      <a class="buy-now-btn" id="settings-explainer-buy-now-bottom" href="/">BUY NOW</a>
      <p style="margin:0.85rem 0 0;"><a href="/">Return to homepage</a></p>
    </section>
  </div>
</body>
</html>
"""
    return body.encode("utf-8")


def settings_explainer_paths() -> frozenset[str]:
    """All URL paths that serve the settings explainer page."""
    return frozenset({SETTINGS_EXPLAINER_PATH, *SETTINGS_EXPLAINER_ALIASES})


def catalog_ids() -> list[str]:
    return [p["id"] for p in settings_parts_catalog()]
