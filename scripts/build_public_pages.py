#!/usr/bin/env python3
"""Build the public GitHub Pages tree for Restore Privacy (catalog monopin).

Writes a whitelist-only static site under ``public_site/``:

  - homepage narrative + free download links
  - privacy / licence pages
  - public brand assets only

Never copies admin panel HTML, admin_*.js, payment secrets, or operator runbooks.

Usage::

  python3 scripts/build_public_pages.py

Publish the open public site (separate public repo, not this monorepo)::

  # after build, push public_site/ contents to:
  #   https://github.com/rgsneddon/restore-privacy-suite
  # Live Pages: https://rgsneddon.github.io/restore-privacy-suite/
"""

from __future__ import annotations

import html
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public_site"
STATIC = ROOT / "status_page" / "static"
STATUS = ROOT / "status_page"

PUBLIC_STATIC = (
    "favicon.ico",
    "favicon.png",
    "logo_transparent.png",
    "logo.png",
    "banner.jpg",
    "apple-touch-icon.png",
    "data_path_motif.svg",
    "public_theme.js",
    "freebie.jpg",
)

FORBIDDEN_NAME_FRAGMENTS = (
    "admin_",
    "admin-",
    "/admin",
    "operator_admin",
    "stripe_secret",
    "webhook_secret",
)


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def assert_no_forbidden(path: Path) -> None:
    rel = str(path.relative_to(OUT)).lower()
    for frag in FORBIDDEN_NAME_FRAGMENTS:
        if frag in rel:
            raise SystemExit(f"refusing forbidden public path: {rel}")


def site_css() -> str:
    return """
:root {
  color-scheme: dark;
  --bg: #0a1628;
  --card: #132a4a;
  --text: #e8eef5;
  --muted: #8eb4d0;
  --accent: #7dd3fc;
  --btn: #2694e8;
  --border: rgba(174, 208, 234, 0.35);
  --font: "Segoe UI", system-ui, -apple-system, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh;
  font-family: var(--font); color: var(--text);
  background: radial-gradient(ellipse at 50% 0%, #1a4a7a 0%, var(--bg) 55%);
}
.page-shell { max-width: 44rem; margin: 0 auto; padding: 1.25rem 1rem 2.5rem; }
.brand-panel {
  background: color-mix(in srgb, var(--card) 88%, transparent);
  border: 1px solid var(--border); border-radius: 14px;
  padding: 1rem 1.1rem; margin-bottom: 1.1rem;
}
.brand-mark { display: flex; align-items: center; gap: 0.85rem; justify-content: center; }
.brand-logo { height: 64px; width: auto; }
.brand-name { margin: 0; font-weight: 800; letter-spacing: 0.04em; font-size: 1.15rem; }
.brand-ver { margin: 0.2rem 0 0; font-size: 0.8rem; color: var(--accent); font-weight: 700; }
.site-nav {
  display: flex; flex-wrap: wrap; gap: 0.55rem; justify-content: center;
  margin-top: 0.9rem;
}
.site-nav a {
  color: var(--text); text-decoration: none; font-size: 0.82rem; font-weight: 700;
  padding: 0.4rem 0.7rem; border-radius: 999px; border: 1px solid var(--border);
  background: rgba(0,0,0,0.18);
}
.site-nav a:hover { border-color: var(--accent); }
.panel {
  background: color-mix(in srgb, var(--card) 90%, transparent);
  border: 1px solid var(--border); border-radius: 14px;
  padding: 1.2rem 1.15rem; margin: 0 0 1rem; text-align: center;
}
.panel h1, .panel h2 { margin: 0 0 0.7rem; letter-spacing: 0.03em; }
.lead { margin: 0 auto 0.75rem; max-width: 36rem; line-height: 1.55; color: #cfe6f7; }
.foot, .muted { color: var(--muted); line-height: 1.45; }
.free-grid {
  display: flex; flex-wrap: wrap; gap: 0.55rem; justify-content: center; margin: 0.85rem 0;
}
.free-grid a.dl, a.btn {
  display: inline-block; min-width: 8rem; padding: 0.65rem 0.9rem;
  border-radius: 12px; font-weight: 700; text-decoration: none;
  color: #0a1628; background: #aed0ea;
}
.free-grid a.dl:hover, a.btn:hover { background: #c5e0f4; }
.keygen-note { margin: 0.75rem auto; max-width: 32rem; color: #fecaca; font-weight: 600; }
.steps { text-align: left; max-width: 28rem; margin: 0.5rem auto; line-height: 1.55; color: #cfe6f7; }
.site-foot {
  display: flex; flex-direction: row; flex-wrap: nowrap; align-items: center;
  justify-content: space-between; gap: 0.5rem 0.75rem; margin-top: 1.5rem;
  font-size: 0.85rem; color: var(--muted);
}
.site-foot .copy {
  margin: 0; text-align: left; flex: 1 1 auto; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.site-foot .map-link {
  margin: 0; text-align: right; flex: 0 0 auto; color: #7aa0c0; text-decoration: none;
  font-size: 0.78rem; letter-spacing: 0.03em; white-space: nowrap;
}
.site-foot .map-link:hover { color: #aed0ea; text-decoration: underline; }
@media (max-width: 420px) {
  .site-foot { flex-direction: row; flex-wrap: nowrap; gap: 0.4rem 0.5rem; }
  .site-foot .copy, .site-foot .map-link { font-size: 0.72rem; }
}
.free-cta { display: block; max-width: 22rem; margin: 0.75rem auto 1rem; }
.free-cta img { width: 100%; height: auto; border-radius: 14px; display: block; }
.map-section { text-align: left; margin: 0.75rem 0 1rem; }
.map-section h3 { margin: 0.85rem 0 0.35rem; font-size: 1rem; color: #e8f2ff; }
.map-section ul { list-style: none; margin: 0; padding: 0; }
.map-section a {
  display: block; color: #ff9a4a; font-weight: 700; text-decoration: none;
  padding: 0.25rem 0; border-bottom: 1px solid rgba(255,122,24,0.35);
  word-break: break-word; font-size: 0.92rem;
}
.map-section a:hover { color: #ffb347; }
.doc-body { text-align: left; max-width: 38rem; margin: 0 auto; line-height: 1.55; color: #cfe6f7; }
"""


def build_index() -> str:
    sys.path.insert(0, str(STATUS))
    from public_chrome import (  # noqa: E402
        PUBLIC_BRAND_DISPLAY,
        PUBLIC_BRAND_TITLE,
        PUBLIC_BRAND_VERSION,
        SUITE_HOME_INTRO_BODY,
        SUITE_HOME_INTRO_FOOT,
        SUITE_HOME_INTRO_HEADING,
    )
    from downloads import (  # noqa: E402
        PRICE_LABEL,
        RELEASE_VERSION,
        available_downloads,
        suite_free_direct_download_href,
        suite_pay_href,
    )

    origin = "https://restoreprivacy.online"
    # FREE DOWNLOAD: UA-detect → free_direct Suite path (matches live status host).
    # No platform "Get Suite — /pay" grid on static home (removed on live host).
    free_cta = (
        f'<a class="free-cta" id="free-download-v1-cta" '
        f'href="{origin}/" data-free-download-v1="1" data-pay="0" '
        f'data-suite-latest="1" data-href-kind="map">'
        f'<img src="assets/freebie.jpg" width="1024" height="1024" '
        f'alt="FREE DOWNLOAD — Restore Privacy"/></a>'
        f"""
<script id="free-download-ua-detect">
(function () {{
  var origin = {origin!r};
  var a = document.getElementById("free-download-v1-cta");
  if (!a) return;
  var ua = (navigator.userAgent || "").toLowerCase();
  var plat = "";
  if (/android/.test(ua)) plat = "android";
  else if (/iphone|ipad|ipod/.test(ua)) plat = "ios";
  else if (/mac os x|macintosh/.test(ua) && !/iphone|ipad|ipod/.test(ua)) plat = "macos";
  else if (/windows/.test(ua)) plat = "windows";
  else if (/cros|linux/.test(ua)) plat = "linux";
  if (!plat) return;
  var href = origin + "/suite/download?platform=" + plat + "&free_direct=1";
  a.setAttribute("href", href);
  a.setAttribute("data-platform", plat);
  a.setAttribute("data-detected-platform", plat);
  a.setAttribute("data-href-kind", "suite_free_direct");
  a.setAttribute("data-free-direct", "1");
  a.setAttribute("data-pay", "0");
}})();
</script>"""
    )
    # Sanity: free_direct builder path matches script template
    _ = suite_free_direct_download_href("macos")
    _ = available_downloads()
    _ = suite_pay_href  # keep import used for map builder elsewhere

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="description" content="Restore Privacy v{RELEASE_VERSION} — free download; KEYGEN from {PRICE_LABEL}/month or yearly"/>
<title>{_esc(PUBLIC_BRAND_DISPLAY)}</title>
<link rel="icon" href="assets/favicon.ico"/>
<link rel="stylesheet" href="assets/site.css"/>
<script src="assets/public_theme.js" defer></script>
</head>
<body class="site-public site-chrome-pro" data-theme="dark" data-product="suite" data-suite-version="{_esc(PUBLIC_BRAND_VERSION)}">
  <div class="page-shell" id="page-shell">
    <header class="brand-panel" id="brand-panel">
      <div class="brand-mark">
        <img class="brand-logo" src="assets/logo_transparent.png" height="64" alt="Restore Privacy"/>
        <div class="brand-text">
          <p class="brand-name">{_esc(PUBLIC_BRAND_TITLE)}</p>
          <p class="brand-ver">{_esc(PUBLIC_BRAND_DISPLAY)}</p>
        </div>
      </div>
      <nav class="site-nav" aria-label="Site">
        <a href="index.html">Home</a>
        <a href="downloads-map.html">Downloads Map</a>
        <a href="privacy.html">Privacy</a>
        <a href="licence.html">Licence</a>
        <a href="https://restoreprivacy.online/AUDIT.md">Audit</a>
        <a href="https://restoreprivacy.online/support">Support</a>
      </nav>
    </header>

    <section class="panel hero" id="suite-home-intro">
      <h1>{_esc(SUITE_HOME_INTRO_HEADING)}</h1>
      <p class="lead">{_esc(SUITE_HOME_INTRO_BODY)}</p>
      <p class="foot">{_esc(SUITE_HOME_INTRO_FOOT)}</p>
    </section>

    <section class="panel" id="suite-storefront" data-free-download="1">
      <h2>FREE DOWNLOAD</h2>
      {free_cta}
      <p class="muted">Detects your device and starts the free installer.
        All platforms and KEYGEN checkout are also on the
        <a href="downloads-map.html">Downloads Map</a> and restoreprivacy.online.</p>
      <p class="keygen-note">
        KEYGEN from <strong>{_esc(PRICE_LABEL)} per month</strong>
        (yearly on /pay). Paste the code from your email in the app, then Connect.
      </p>
      <p class="cta-row">
        <a class="btn" href="https://restoreprivacy.online/pay?product=suite">Get a KEYGEN — /pay</a>
      </p>
    </section>

    <section class="panel" id="how-it-works">
      <h2>How it works</h2>
      <ol class="steps">
        <li>Download and install free (FREE DOWNLOAD button).</li>
        <li>Try three days, then buy a KEYGEN from {_esc(PRICE_LABEL)}/month on /pay.</li>
        <li>Paste the KEYGEN from your email and Connect.</li>
      </ol>
    </section>

    <section class="panel" id="app-capabilities" data-app-capabilities="1">
      <h2>What the client does</h2>
      <ul class="steps">
        <li>Full-tunnel protection where the OS allows a system VPN (residual path).</li>
        <li>Choose residual location: Germany (default) or Singapore.</li>
        <li>Lean Settings by default — opt into privacy extras only when you want them.</li>
        <li>Android: optional “auto connect if idle” reopens the tunnel after an unexpected drop (gentle backoff; Disconnect still wins).</li>
        <li>Optional residual IPv6 leak posture, leak test, local connection log, and kill-switch opt-in with confirm.</li>
        <li>macOS free monopin ships Notarized Developer ID with Packet Tunnel host NE so first-use System Settings registration can work.</li>
        <li>Windows, Android, macOS, iOS, and Linux packages on the Downloads Map; Connect still needs trial or KEYGEN.</li>
      </ul>
      <p class="muted">Plain-language walkthrough of every Settings control:
        <a href="https://restoreprivacy.online/settings-explainer">Settings guide</a>.</p>
    </section>

{static_site_footer(
        map_href="downloads-map.html",
        copyright_text=f"© Raskul - all rights reserved · {PUBLIC_BRAND_DISPLAY}",
    )}
  </div>
</body>
</html>
"""


def build_downloads_map() -> str:
    """Static Downloads Map — Suite latest only; links → live free_direct Suite download."""
    sys.path.insert(0, str(STATUS))
    from downloads import (  # noqa: E402
        RELEASE_VERSION,
        downloads_map_products,
        list_downloads_map_rows,
    )

    origin = "https://restoreprivacy.online"
    sections: list[str] = []
    for product, rows in downloads_map_products(list_downloads_map_rows()):
        links = []
        for r in rows:
            href = str(r.get("href") or "")
            if href.startswith("/"):
                href = origin + href
            label = str(r.get("label") or r.get("filename") or "")
            plat = str(r.get("platform") or "")
            links.append(
                f'<li><a href="{_esc(href)}" data-pay="0" data-platform="{_esc(plat)}" '
                f'data-kind="suite_client" data-free-direct="1">{_esc(label)}</a></li>'
            )
        body = "\n        ".join(links)
        sections.append(
            f'<div class="map-section" data-map-product="{_esc(product)}">'
            f"<h3>{_esc(product)}</h3><ul>\n        {body}\n      </ul></div>"
        )
    sections_html = "\n      ".join(sections)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Downloads Map · Restore Privacy v{RELEASE_VERSION}</title>
<link rel="icon" href="assets/favicon.ico"/>
<link rel="stylesheet" href="assets/site.css"/>
</head>
<body class="site-public" data-theme="dark" data-product="suite">
  <div class="page-shell">
    <header class="brand-panel">
      <p class="brand-name">Downloads Map</p>
      <nav class="site-nav">
        <a href="index.html">Home</a>
        <a href="downloads-map.html">Downloads Map</a>
      </nav>
    </header>
    <section class="panel" id="downloads-map-page" data-downloads-map-page="1">
      <h1>Downloads Map</h1>
      <p class="muted">Restore Privacy v{RELEASE_VERSION} — free installer for each platform.
        KEYGEN licences are on /pay.</p>
      {sections_html}
    </section>
{static_site_footer(map_href="downloads-map.html")}
  </div>
</body>
</html>
"""


def static_site_footer(
    *,
    map_href: str = "downloads-map.html",
    copyright_text: str = "© Raskul - all rights reserved",
) -> str:
    """Shared static footer: copyright left + download map link (right)."""
    return f"""    <footer class="site-foot">
      <p class="copy">{_esc(copyright_text)}</p>
      <a class="map-link" href="{_esc(map_href)}" data-downloads-map-link="1">download map</a>
    </footer>"""


def build_simple_doc(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_esc(title)} · Restore Privacy</title>
<link rel="icon" href="assets/favicon.ico"/>
<link rel="stylesheet" href="assets/site.css"/>
</head>
<body class="site-public" data-theme="dark" data-product="suite">
  <div class="page-shell">
    <header class="brand-panel">
      <p class="brand-name">Restore Privacy</p>
      <nav class="site-nav"><a href="index.html">Home</a></nav>
    </header>
    <section class="panel">
      <h1>{_esc(title)}</h1>
      <div class="doc-body">{body_html}</div>
    </section>
{static_site_footer()}
  </div>
</body>
</html>
"""


def main() -> int:
    sys.path.insert(0, str(STATUS))
    from downloads import RELEASE_VERSION  # noqa: E402

    if OUT.exists():
        shutil.rmtree(OUT)
    assets = OUT / "assets"
    assets.mkdir(parents=True)

    (assets / "site.css").write_text(site_css(), encoding="utf-8")
    for name in PUBLIC_STATIC:
        src = STATIC / name
        if src.is_file():
            shutil.copy2(src, assets / name)

    (OUT / "index.html").write_text(build_index(), encoding="utf-8")
    (OUT / "downloads-map.html").write_text(build_downloads_map(), encoding="utf-8")
    (OUT / "privacy.html").write_text(
        build_simple_doc(
            "Privacy",
            "<p>Device settings stay on your machine. Stripe handles cards; "
            "this site does not store card details.</p>"
            "<p>Full policy: "
            '<a href="https://restoreprivacy.online/PRIVACY_POLICY.md">Privacy policy</a>.</p>',
        ),
        encoding="utf-8",
    )
    (OUT / "licence.html").write_text(
        build_simple_doc(
            "Licence",
            "<p>Restore Privacy is proprietary software. Install free; "
            "Connect needs an active KEYGEN after the trial.</p>"
            '<p>Full terms: <a href="https://restoreprivacy.online/LICENSE">End-user licence</a>.</p>',
        ),
        encoding="utf-8",
    )
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Restore Privacy — public site\n\n"
        f"Static GitHub Pages export for **Restore Privacy v{RELEASE_VERSION}**.\n\n"
        "Free installers and a Downloads Map; KEYGEN from £3/month on "
        "restoreprivacy.online.\n\n"
        "This tree is **public only**. It does **not** include `/admin` or operator tools.\n\n"
        "## Live public open site\n\n"
        "| | |\n|--|--|\n"
        "| **GitHub Pages** | https://rgsneddon.github.io/restore-privacy-suite/ |\n"
        "| **Public source repo** | https://github.com/rgsneddon/restore-privacy-suite |\n"
        "| **Downloads Map** | downloads-map.html (and live /downloads-map) |\n\n"
        "Installer bytes are fulfilled on restoreprivacy.online / Helsinki; this "
        "export links to those routes (large binaries are not committed to Pages).\n\n"
        "Publish by pushing this export to the public `restore-privacy-suite` repo "
        "(keep the product monorepo private).\n",
        encoding="utf-8",
    )

    # Fail closed if operator console artifacts appear (deny-phrases in README OK).
    for p in OUT.rglob("*"):
        if p.is_file():
            assert_no_forbidden(p)
            raw = p.read_bytes()
            low = raw.lower()
            if b"admin-login-form" in low or b"operator admin pages" in low:
                raise SystemExit(f"admin UI leaked into {p}")
            if b"admin_sidebar.js" in low or b"admin_fleet_usage" in low:
                raise SystemExit(f"admin script reference in {p}")
            if b'id="admin-' in low and b"admin-panel" in low:
                raise SystemExit(f"admin panel id leaked into {p}")

    print(f"public_site_ok={OUT}")
    print(f"files={sum(1 for _ in OUT.rglob('*') if _.is_file())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
