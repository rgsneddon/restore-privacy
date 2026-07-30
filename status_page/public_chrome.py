"""Shared public site chrome — brand header, nav buttons, theme (light/dark/device).

Used by homepage, public documents, and Settings guide. **Not** used by /admin.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Browser localStorage key for public theme preference
PUBLIC_THEME_STORAGE_KEY = "rpt_public_theme"

# Stable DOM ids (brand-panel / doc-links keep legacy test selectors)
SITE_BRAND_HEADER_ID = "brand-panel"
SITE_NAV_ID = "doc-links"
THEME_MODE_CONTROL_ID = "theme-mode-control"
HOME_LINK_ID = "home-link"
LICENCE_LINK_ID = "licence-link"
PRIVACY_LINK_ID = "privacy-link"
AUDIT_LINK_ID = "audit-link"
README_LINK_ID = "readme-link"
SUPPORT_LINK_ID = "support-link"
SETTINGS_GUIDE_LINK_ID = "settings-guide-link"

# Public website brand / page identity (top H1 + default document title)
PUBLIC_BRAND_TITLE = "RESTORE PRIVACY VPN"

# Borderless mark: shield + protruding green key only (transparent outside).
# Opaque logo.png remains for favicon/legacy plate uses; Stripe uses stripe_brand_*.
PUBLIC_BRAND_LOGO_PATH = "/logo_transparent.png"
PUBLIC_BRAND_LOGO_STATIC_NAME = "logo_transparent.png"
# Default img width/height (CSS clamp is slightly larger than prior 96px).
PUBLIC_BRAND_LOGO_SIZE_DEFAULT = 112
PUBLIC_BRAND_LOGO_SIZE_MIN_CSS = 88  # clamp min — was 72
PUBLIC_BRAND_LOGO_SIZE_MAX_CSS = 120  # clamp max — was 104

# Paths (keep aligned with public_docs / settings_explainer)
HOME_PATH = "/"
LICENSE_PATH = "/LICENSE"
PRIVACY_PATH = "/PRIVACY_POLICY.md"
AUDIT_PATH = "/AUDIT.md"
README_PATH = "/README.md"
SUPPORT_PATH = "/support"
SETTINGS_GUIDE_PATH = "/settings-explainer"

# Product family landings (paths; optional Host aliases for browser./vault.)
PRODUCT_VPN_PATH = "/"
PRODUCT_BROWSER_PATH = "/browser"
PRODUCT_VAULT_PATH = "/vault"
PRODUCT_VPN_KEY = "vpn"
PRODUCT_BROWSER_KEY = "browser"
PRODUCT_VAULT_KEY = "vault"
PRODUCT_VPN_LABEL = "Restore Privacy VPN"
PRODUCT_BROWSER_LABEL = "Restore Privacy Browser"
PRODUCT_VAULT_LABEL = "Restore Privacy Vault"
PRODUCT_VPN_TITLE = "RESTORE PRIVACY VPN"
PRODUCT_BROWSER_TITLE = "RESTORE PRIVACY BROWSER"
PRODUCT_VAULT_TITLE = "RESTORE PRIVACY VAULT"
PRODUCT_TABS_ID = "product-tabs"
PRODUCT_TAB_VPN_ID = "product-tab-vpn"
PRODUCT_TAB_BROWSER_ID = "product-tab-browser"
PRODUCT_TAB_VAULT_ID = "product-tab-vault"

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_BRAND_ASSET_VERSION_CACHE: str | None = None


def public_brand_asset_version() -> str:
    """Short content hash of header logo + favicon for cache-busting query params.

    Browsers aggressively cache favicons; a stable ``?v=`` on link/img hrefs
    forces a refresh when status static brand bytes change.
    """
    global _BRAND_ASSET_VERSION_CACHE
    if _BRAND_ASSET_VERSION_CACHE is not None:
        return _BRAND_ASSET_VERSION_CACHE
    h = hashlib.sha256()
    for name in (
        PUBLIC_BRAND_LOGO_STATIC_NAME,
        "favicon.ico",
        "favicon.png",
        "apple-touch-icon.png",
    ):
        p = _STATIC_DIR / name
        if p.is_file():
            h.update(p.read_bytes())
    _BRAND_ASSET_VERSION_CACHE = h.hexdigest()[:12]
    return _BRAND_ASSET_VERSION_CACHE


def public_brand_logo_src() -> str:
    """Borderless logo path with cache-bust query for public header ``<img>``."""
    return f"{PUBLIC_BRAND_LOGO_PATH}?v={public_brand_asset_version()}"


def public_favicon_href(path: str) -> str:
    """Favicon/apple-touch href with the same brand asset version."""
    base = (path or "").strip() or "/favicon.ico"
    return f"{base}?v={public_brand_asset_version()}"


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def public_site_css() -> str:
    """Site-wide CSS variables, shell, brand header, nav buttons, light/dark themes."""
    return f"""
/* === Public site chrome (shared) === */
:root, [data-theme="dark"] {{
  --rb-navy: #0a1628;
  --rb-navy-mid: #0f2340;
  --rb-card: #132a4a;
  /* Soft fill edge under neon dual-tone border (logo circuit + key palette) */
  --rb-card-border: rgba(0, 229, 255, 0.35);
  /* Logo data-artifact neon: cyan/blue circuit + green key */
  --rb-neon-cyan: #00e5ff;
  --rb-neon-blue: #2694e8;
  --rb-neon-green: #39ff6a;
  --rb-neon-border: linear-gradient(
    135deg,
    var(--rb-neon-cyan) 0%,
    var(--rb-neon-blue) 42%,
    var(--rb-neon-green) 100%
  );
  --rb-neon-glow-cyan: rgba(0, 229, 255, 0.42);
  --rb-neon-glow-green: rgba(57, 255, 106, 0.28);
  --rb-cream: #f2f5f7;
  --rb-muted: #aed0ea;
  --rb-link: #74b2e2;
  --rb-link-hover: #d7ebf9;
  --rb-btn: #2694e8;
  --rb-btn-deep: #1a6fad;
  --rb-btn-text: #ffffff;
  --rb-soft: #deedf7;
  --rb-accent-sky: #5eb0e8;
  --rb-accent: #5eb0e8;
  --rb-radius: 16px;
  --rb-max: 56rem;
  --rb-body-fg: var(--rb-cream);
  --rb-body-bg1: #1a3a66;
  --rb-body-bg2: var(--rb-navy-mid);
  --rb-body-bg3: var(--rb-navy);
  --rb-body-bg4: #07101c;
  --rb-panel-shadow: 0 10px 32px rgba(4, 12, 28, 0.35);
  /* Price callouts always white (sit on navy price panels in both themes) */
  --rb-price-white: #ffffff;
  --rb-price-panel-bg: linear-gradient(165deg, #1a4a7a 0%, #0a1628 70%);
  --rb-code-bg: rgba(10, 22, 40, 0.55);
  --rb-doc-fg: var(--rb-cream);
  --rb-doc-muted: var(--rb-muted);
  --rb-pre-bg: rgba(10, 22, 40, 0.65);
  --rb-pre-border: color-mix(in srgb, var(--rb-neon-cyan) 35%, transparent);
}}
[data-theme="light"] {{
  --rb-navy: #e8f1f8;
  --rb-navy-mid: #f4f8fb;
  --rb-card: #ffffff;
  --rb-card-border: rgba(0, 180, 220, 0.45);
  --rb-neon-cyan: #00b8d4;
  --rb-neon-blue: #1a8fd4;
  --rb-neon-green: #12c94a;
  --rb-neon-border: linear-gradient(
    135deg,
    var(--rb-neon-cyan) 0%,
    var(--rb-neon-blue) 42%,
    var(--rb-neon-green) 100%
  );
  --rb-neon-glow-cyan: rgba(0, 184, 212, 0.28);
  --rb-neon-glow-green: rgba(18, 201, 74, 0.18);
  --rb-cream: #0f2340;
  --rb-muted: #4a657a;
  --rb-link: #1a6fad;
  --rb-link-hover: #0a1628;
  --rb-btn: #2694e8;
  --rb-btn-deep: #1a6fad;
  --rb-btn-text: #ffffff;
  --rb-soft: #deedf7;
  --rb-accent-sky: #2694e8;
  --rb-accent: #2694e8;
  --rb-body-fg: #0f2340;
  --rb-body-bg1: #d7ebf9;
  --rb-body-bg2: #eef5fb;
  --rb-body-bg3: #f7fafc;
  --rb-body-bg4: #e8eef4;
  --rb-panel-shadow: 0 8px 28px rgba(15, 35, 64, 0.1);
  --rb-price-white: #ffffff;
  --rb-price-panel-bg: linear-gradient(165deg, #2a6fad 0%, #0f2340 75%);
  --rb-code-bg: #f0f5f9;
  --rb-doc-fg: #0f2340;
  --rb-doc-muted: #4a657a;
  --rb-pre-bg: #f4f8fb;
  --rb-pre-border: color-mix(in srgb, var(--rb-neon-cyan) 40%, transparent);
}}
@media (prefers-color-scheme: light) {{
  :root:not([data-theme="dark"]):not([data-theme="light"]) {{
    --rb-navy: #e8f1f8;
    --rb-navy-mid: #f4f8fb;
    --rb-card: #ffffff;
    --rb-card-border: rgba(0, 180, 220, 0.45);
    --rb-neon-cyan: #00b8d4;
    --rb-neon-blue: #1a8fd4;
    --rb-neon-green: #12c94a;
    --rb-neon-border: linear-gradient(
      135deg,
      var(--rb-neon-cyan) 0%,
      var(--rb-neon-blue) 42%,
      var(--rb-neon-green) 100%
    );
    --rb-neon-glow-cyan: rgba(0, 184, 212, 0.28);
    --rb-neon-glow-green: rgba(18, 201, 74, 0.18);
    --rb-cream: #0f2340;
    --rb-muted: #4a657a;
    --rb-link: #1a6fad;
    --rb-link-hover: #0a1628;
    --rb-btn: #2694e8;
    --rb-btn-deep: #1a6fad;
    --rb-btn-text: #ffffff;
    --rb-soft: #deedf7;
    --rb-accent-sky: #2694e8;
    --rb-accent: #2694e8;
    --rb-body-fg: #0f2340;
    --rb-body-bg1: #d7ebf9;
    --rb-body-bg2: #eef5fb;
    --rb-body-bg3: #f7fafc;
    --rb-body-bg4: #e8eef4;
    --rb-panel-shadow: 0 8px 28px rgba(15, 35, 64, 0.1);
    --rb-price-white: #ffffff;
    --rb-price-panel-bg: linear-gradient(165deg, #2a6fad 0%, #0f2340 75%);
    --rb-code-bg: #f0f5f9;
    --rb-doc-fg: #0f2340;
    --rb-doc-muted: #4a657a;
    --rb-pre-bg: #f4f8fb;
    --rb-pre-border: color-mix(in srgb, var(--rb-neon-cyan) 40%, transparent);
  }}
}}
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  margin: 0; min-height: 100vh; display: flex; flex-direction: column;
  align-items: center;
  background:
    radial-gradient(1200px 600px at 50% -10%, var(--rb-body-bg1) 0%, transparent 55%),
    linear-gradient(180deg, var(--rb-body-bg2) 0%, var(--rb-body-bg3) 45%, var(--rb-body-bg4) 100%);
  color: var(--rb-body-fg);
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  padding: clamp(1rem, 3vw, 2.5rem) 0 3rem;
}}
.page-shell {{
  width: min(100% - 1.5rem, var(--rb-max));
  display: flex; flex-direction: column; gap: 1.15rem;
  margin: 0 auto;
}}
/* Product family tabs (VPN / Browser / Vault) — equal full shell width */
#{PRODUCT_TABS_ID}, .product-tabs {{
  display: flex; flex-wrap: nowrap; justify-content: stretch;
  align-items: stretch;
  gap: 0.65rem; width: 100%; max-width: 100%;
  margin: 0; padding: 0;
  box-sizing: border-box;
}}
a.product-tab, .product-tab {{
  flex: 1 1 0;
  width: 0; /* equal share of full shell row */
  min-width: 0;
  max-width: none;
  text-align: center;
  text-decoration: none;
  color: var(--rb-cream);
  font-weight: 700;
  letter-spacing: 0.04em;
  font-size: clamp(0.68rem, 1.8vw, 0.88rem);
  line-height: 1.25;
  padding: 0.85rem 0.5rem;
  border-radius: var(--rb-radius);
  border: 1.5px solid transparent;
  box-sizing: border-box;
  background:
    linear-gradient(
      165deg,
      color-mix(in srgb, var(--rb-card) 88%, var(--rb-soft)) 0%,
      var(--rb-card) 55%
    ) padding-box,
    var(--rb-neon-border) border-box;
  background-origin: border-box;
  background-clip: padding-box, border-box;
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--rb-neon-cyan) 18%, transparent),
    0 0 10px var(--rb-neon-glow-cyan),
    var(--rb-panel-shadow);
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}}
a.product-tab:hover, .product-tab:hover {{
  transform: translateY(-1px);
  color: var(--rb-cream);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--rb-neon-cyan) 35%, transparent),
    0 0 16px var(--rb-neon-glow-cyan),
    0 0 22px var(--rb-neon-glow-green),
    var(--rb-panel-shadow);
}}
a.product-tab.is-active, .product-tab.is-active {{
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--rb-neon-green) 55%, transparent),
    0 0 18px var(--rb-neon-glow-cyan),
    0 0 28px var(--rb-neon-glow-green),
    var(--rb-panel-shadow);
  outline: none;
}}
.product-tab-label {{ display: block; }}
/* Coming-soon product body (Browser / Vault) — brand lettering weight like H1 */
.product-coming-card {{
  text-align: center;
  padding: clamp(1.5rem, 4vw, 2.5rem) clamp(1rem, 3vw, 1.75rem);
}}
.product-coming-title {{
  letter-spacing: 0.14em; font-weight: 700;
  font-size: clamp(1.35rem, 4.2vw, 2.05rem);
  margin: 0 0 0.85rem; color: var(--rb-cream);
  line-height: 1.15;
}}
.product-coming-line {{
  margin: 0.35rem 0 0; font-size: clamp(0.95rem, 2.6vw, 1.15rem);
  line-height: 1.45; color: var(--rb-cream); font-weight: 600;
}}
.product-coming-schedule {{
  margin: 0.55rem 0 0; font-size: clamp(0.9rem, 2.4vw, 1.05rem);
  line-height: 1.45; color: var(--rb-muted); font-weight: 500;
}}
/* Logo data-artifact borders: neon cyan/blue → green gradient + dual glow */
.panel-card {{
  border: 1.5px solid transparent;
  border-radius: var(--rb-radius);
  padding: clamp(1rem, 2.5vw, 1.45rem);
  background:
    linear-gradient(
      165deg,
      color-mix(in srgb, var(--rb-card) 88%, var(--rb-soft)) 0%,
      var(--rb-card) 55%
    ) padding-box,
    var(--rb-neon-border) border-box;
  background-origin: border-box;
  background-clip: padding-box, border-box;
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--rb-neon-cyan) 22%, transparent),
    0 0 14px var(--rb-neon-glow-cyan),
    0 0 26px var(--rb-neon-glow-green),
    var(--rb-panel-shadow);
}}
.panel-title {{
  margin: 0 0 0.85rem; font-size: 0.95rem; letter-spacing: 0.12em;
  text-transform: uppercase; font-weight: 700; color: var(--rb-muted);
  text-align: center;
}}
#{SITE_BRAND_HEADER_ID}, .brand-panel, #site-brand-header {{
  display: flex; flex-direction: column; align-items: center;
  text-align: center; gap: 0.75rem;
}}
/* Logo + title row: centered above the menu */
.brand-mark {{
  display: flex; flex-direction: row; flex-wrap: wrap;
  align-items: center; justify-content: center;
  gap: clamp(0.55rem, 2vw, 0.95rem);
  width: 100%;
  max-width: 100%;
}}
.brand-logo {{
  /* Slightly larger than previous clamp(72–104) / default 96px */
  width: clamp(88px, 16vw, 120px); height: clamp(88px, 16vw, 120px);
  border: none;
  border-radius: 0;
  object-fit: contain;
  background: transparent;
  box-shadow: none;
  flex-shrink: 0;
}}
#{SITE_BRAND_HEADER_ID} h1, .brand-panel h1, #site-brand-header h1,
.brand-mark h1 {{
  letter-spacing: 0.14em; font-weight: 700;
  font-size: clamp(1.35rem, 4.2vw, 2.05rem);
  margin: 0; color: var(--rb-cream);
  text-align: left;
  line-height: 1.15;
}}
.brand-tagline, .tagline {{
  margin: 0; max-width: 32rem; font-size: clamp(0.85rem, 2.4vw, 0.98rem);
  line-height: 1.45; color: var(--rb-muted); font-weight: 500;
}}
/* Logo-aligned nav buttons (sky blue / navy — not yellow) */
#{SITE_NAV_ID}, .site-nav, .doc-links, #site-nav {{
  margin: 0.15rem 0 0; max-width: 100%;
  display: flex; flex-wrap: wrap; justify-content: center; gap: 0.45rem;
  padding: 0;
}}
.nav-btn, a.nav-btn, a.doc-link {{
  display: inline-block;
  font-weight: 700;
  letter-spacing: 0.04em;
  font-size: clamp(0.72rem, 2vw, 0.82rem);
  text-transform: uppercase;
  text-decoration: none;
  color: var(--rb-btn-text) !important;
  background: linear-gradient(180deg, var(--rb-btn) 0%, var(--rb-btn-deep) 100%);
  border: 1px solid color-mix(in srgb, var(--rb-link) 50%, transparent);
  border-radius: 999px;
  padding: 0.42rem 0.85rem;
  box-shadow: 0 4px 12px rgba(10, 22, 40, 0.2);
  transition: filter 0.12s ease, transform 0.12s ease;
}}
.nav-btn:hover, a.nav-btn:hover, a.doc-link:hover {{
  filter: brightness(1.08);
  color: var(--rb-btn-text) !important;
  background: linear-gradient(180deg, var(--rb-accent-sky) 0%, var(--rb-btn) 100%);
}}
.nav-btn.is-active, a.nav-btn.is-active {{
  outline: 2px solid var(--rb-soft);
  outline-offset: 2px;
}}
.doc-sep {{ display: none; }}
/* Theme control */
#{THEME_MODE_CONTROL_ID}, .theme-mode-control {{
  display: flex; flex-wrap: wrap; align-items: center; justify-content: center;
  gap: 0.45rem 0.75rem; margin: 0.35rem 0 0; width: 100%;
}}
.theme-mode-control .theme-ask {{
  margin: 0; font-size: 0.78rem; color: var(--rb-muted); font-weight: 600;
}}
.theme-mode-control fieldset {{
  margin: 0; padding: 0.2rem; border: 1px solid var(--rb-card-border);
  border-radius: 999px; display: flex; flex-wrap: wrap; gap: 0.2rem;
  background: color-mix(in srgb, var(--rb-code-bg) 80%, transparent);
}}
.theme-mode-control legend {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }}
.theme-mode-control label {{
  display: inline-flex; align-items: center; gap: 0.25rem;
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.03em;
  text-transform: uppercase; color: var(--rb-muted);
  padding: 0.28rem 0.55rem; border-radius: 999px; cursor: pointer;
}}
.theme-mode-control input {{ accent-color: var(--rb-btn); margin: 0; }}
.theme-mode-control label:has(input:checked) {{
  background: color-mix(in srgb, var(--rb-btn) 22%, transparent);
  color: var(--rb-cream); outline: 1px solid var(--rb-btn);
}}
/* Settings guide banner (logo palette, not yellow) */
.settings-banner {{
  text-align: center;
  background: linear-gradient(165deg, color-mix(in srgb, var(--rb-btn) 18%, var(--rb-card)) 0%, var(--rb-card) 60%);
  border-color: color-mix(in srgb, var(--rb-link) 45%, transparent);
}}
.settings-banner-kicker {{
  margin: 0 0 0.35rem; font-size: 0.72rem; letter-spacing: 0.14em;
  text-transform: uppercase; font-weight: 700; color: var(--rb-accent-sky);
}}
.settings-banner-title {{
  margin: 0 0 0.45rem; font-size: clamp(1.05rem, 3vw, 1.25rem);
  font-weight: 800; color: var(--rb-cream); letter-spacing: 0.04em;
}}
.settings-banner-blurb {{
  margin: 0 auto 0.85rem; max-width: 36rem; font-size: 0.88rem;
  line-height: 1.45; color: var(--rb-muted);
}}
.settings-banner-actions {{ margin: 0; }}
.settings-banner-link, a.settings-banner-link {{
  display: inline-block; font-weight: 800; letter-spacing: 0.04em;
  text-transform: uppercase; font-size: 0.82rem;
  color: var(--rb-btn-text) !important;
  background: linear-gradient(180deg, var(--rb-btn) 0%, var(--rb-btn-deep) 100%);
  text-decoration: none; padding: 0.55rem 1.15rem; border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--rb-link) 40%, transparent);
  box-shadow: 0 6px 18px rgba(10, 22, 40, 0.22);
}}
.settings-banner-link:hover {{
  filter: brightness(1.08);
  color: var(--rb-btn-text) !important;
}}
/* Doc body inside box shell */
.doc-body-panel {{
  color: var(--rb-doc-fg);
}}
.doc-body-panel a {{ color: var(--rb-link); font-weight: 600; }}
.doc-body-panel h1, .doc-body-panel h2, .doc-body-panel h3 {{
  color: var(--rb-cream); letter-spacing: 0.02em;
}}
.doc-body-panel .muted, .doc-body-panel .doc-muted {{ color: var(--rb-doc-muted); }}
.doc-plain, pre.doc-plain {{
  white-space: pre-wrap; word-wrap: break-word;
  font-family: ui-monospace, "Cascadia Code", "Consolas", "Courier New", monospace;
  font-size: 0.88rem; line-height: 1.5;
  background: var(--rb-pre-bg);
  border: 1px solid var(--rb-pre-border);
  border-radius: 12px;
  padding: 1rem 1.1rem;
  color: var(--rb-doc-fg);
  margin: 0;
}}
.doc-code {{
  background: var(--rb-pre-bg); border: 1px solid var(--rb-pre-border);
  border-radius: 10px; padding: 0.75rem; overflow-x: auto;
}}
.doc-body table {{
  width: 100%; border-collapse: collapse; font-size: 0.88rem;
  margin: 0.75rem 0 1rem;
}}
.doc-body th, .doc-body td {{
  border: 1px solid var(--rb-card-border); padding: 0.4rem 0.55rem;
  vertical-align: top;
}}
.doc-body th {{ background: var(--rb-code-bg); }}
.doc-foot {{
  margin-top: 0.5rem; text-align: center; font-size: 0.88rem; color: var(--rb-muted);
}}
.doc-foot a {{ color: var(--rb-link); font-weight: 600; margin: 0 0.35rem; }}
@media (max-width: 520px) {{
  .page-shell {{ width: min(100% - 1rem, var(--rb-max)); gap: 0.9rem; }}
  .nav-btn, a.nav-btn, a.doc-link {{ font-size: 0.68rem; padding: 0.38rem 0.65rem; }}
}}
"""


def public_theme_boot_script() -> str:
    """Same-origin theme script tag (CSP script-src 'self'; logic in static JS)."""
    key = PUBLIC_THEME_STORAGE_KEY
    return (
        f'<script id="public-theme-script" src="/static/public_theme.js" '
        f'data-storage-key="{key}"></script>\n'
    )


def public_theme_picker_html() -> str:
    """Light / Dark / Device control (public pages only)."""
    return f"""
<div class="theme-mode-control" id="{THEME_MODE_CONTROL_ID}" role="group" aria-label="Colour mode">
  <p class="theme-ask" id="theme-mode-ask">Colour mode</p>
  <fieldset id="public-theme-fieldset">
    <legend>Colour mode</legend>
    <label><input type="radio" name="public-theme" id="theme-device" value="device" checked/> Device</label>
    <label><input type="radio" name="public-theme" id="theme-light" value="light"/> Light</label>
    <label><input type="radio" name="public-theme" id="theme-dark" value="dark"/> Dark</label>
  </fieldset>
</div>
"""


def public_product_tabs_html(*, active: str = PRODUCT_VPN_KEY) -> str:
    """Three product family tabs (VPN / Browser / Vault) in panel-card box style.

    *active* is one of: vpn, browser, vault. Placed at the very top of public pages.
    """
    key = (active or PRODUCT_VPN_KEY).strip().lower()
    if key not in (PRODUCT_VPN_KEY, PRODUCT_BROWSER_KEY, PRODUCT_VAULT_KEY):
        key = PRODUCT_VPN_KEY
    items = (
        (PRODUCT_VPN_KEY, PRODUCT_VPN_PATH, PRODUCT_TAB_VPN_ID, PRODUCT_VPN_LABEL),
        (
            PRODUCT_BROWSER_KEY,
            PRODUCT_BROWSER_PATH,
            PRODUCT_TAB_BROWSER_ID,
            PRODUCT_BROWSER_LABEL,
        ),
        (
            PRODUCT_VAULT_KEY,
            PRODUCT_VAULT_PATH,
            PRODUCT_TAB_VAULT_ID,
            PRODUCT_VAULT_LABEL,
        ),
    )
    parts: list[str] = []
    for k, path, el_id, label in items:
        cls = "product-tab"
        if k == key:
            cls += " is-active"
        aria = ' aria-current="page"' if k == key else ""
        parts.append(
            f'<a class="{cls}" id="{el_id}" href="{path}" data-product="{k}"{aria}>'
            f'<span class="product-tab-label">{_esc(label)}</span></a>'
        )
    return (
        f'  <nav class="product-tabs" id="{PRODUCT_TABS_ID}" '
        f'data-product-tabs="1" aria-label="Product family">'
        f"{''.join(parts)}</nav>\n"
    )


def public_nav_links_html(*, active: str | None = None) -> str:
    """Button-style nav: Home, Licence, Privacy, Audit, Support, README.

    *active* is one of: home, licence, privacy, audit, support, readme (or None).
    Settings guide is **not** in the top brand nav (homepage banner may still
    link to the explainer page).
    """
    items = (
        ("HOME", HOME_PATH, HOME_LINK_ID, "home"),
        ("LICENCE", LICENSE_PATH, LICENCE_LINK_ID, "licence"),
        ("PRIVACY POLICY", PRIVACY_PATH, PRIVACY_LINK_ID, "privacy"),
        ("SECURITY AUDIT", AUDIT_PATH, AUDIT_LINK_ID, "audit"),
        ("SUPPORT", SUPPORT_PATH, SUPPORT_LINK_ID, "support"),
        ("README", README_PATH, README_LINK_ID, "readme"),
    )
    parts: list[str] = []
    for label, path, el_id, key in items:
        cls = "nav-btn doc-link"
        if active and active == key:
            cls += " is-active"
        parts.append(
            f'<a class="{cls}" id="{el_id}" href="{path}">{label}</a>'
        )
    return (
        f'  <nav class="site-nav doc-links" id="{SITE_NAV_ID}" '
        f'data-site-nav="1" aria-label="Site navigation">{"".join(parts)}</nav>'
    )


def public_display_title(raw: str | None = None) -> str:
    """Normalize product title for public brand chrome and page titles.

    Short historical **RESTORE PRIVACY** (node/status payload) becomes
    **RESTORE PRIVACY VPN**. Empty / missing → :data:`PUBLIC_BRAND_TITLE`.
    """
    t = (raw or "").strip()
    if not t or t == "RESTORE PRIVACY":
        return PUBLIC_BRAND_TITLE
    return t


def public_brand_header_html(
    *,
    title: str = PUBLIC_BRAND_TITLE,
    tagline: str = "",
    active: str | None = None,
    logo_size: int = PUBLIC_BRAND_LOGO_SIZE_DEFAULT,
    logo_src: str = PUBLIC_BRAND_LOGO_PATH,
    product_active: str = PRODUCT_VPN_KEY,
    include_product_tabs: bool = True,
    include_site_nav: bool = True,
) -> str:
    """Static top brand panel used across all public pages.

    Layout: **product tabs** (VPN / Browser / Vault) at the very top, then
    **borderless shield+key mark** to the **left** of the brand H1, as a centered
    row **above** the site nav (when included). Logo has no outer plate/frame.
    Under-title tagline is omitted by default (no lightweight-vpn slogan).
    Pass a non-empty *tagline* only if a page truly needs a header subtitle;
    public catalog/docs call sites leave it empty for a clean top box.
    Brand H1 defaults to :data:`PUBLIC_BRAND_TITLE` (**RESTORE PRIVACY VPN**).
    *product_active* is vpn | browser | vault for the top product tabs.
    *include_site_nav* controls Home/Licence/Privacy/Audit/README menu buttons
    (VPN homepage keeps them; Browser/Vault omit them).
    """
    # Product landings pass full product titles; VPN home normalizes short titles.
    raw_title = (title or "").strip()
    if raw_title in (PRODUCT_BROWSER_TITLE, PRODUCT_VAULT_TITLE):
        title_safe = _esc(raw_title)
    else:
        title_safe = _esc(public_display_title(title))
    raw_src = (logo_src or PUBLIC_BRAND_LOGO_PATH).strip() or PUBLIC_BRAND_LOGO_PATH
    # Default solid logo gets cache-bust; explicit override paths are left as-is
    # unless they are the standard solid path without a query.
    if raw_src == PUBLIC_BRAND_LOGO_PATH or raw_src.startswith(f"{PUBLIC_BRAND_LOGO_PATH}?"):
        src = public_brand_logo_src()
    else:
        src = raw_src
    sz = int(logo_size) if logo_size else PUBLIC_BRAND_LOGO_SIZE_DEFAULT
    if sz < 64:
        sz = PUBLIC_BRAND_LOGO_SIZE_DEFAULT
    tag = (tagline or "").strip()
    tagline_html = (
        f'      <p class="brand-tagline">{_esc(tag)}</p>\n' if tag else ""
    )
    tabs = (
        public_product_tabs_html(active=product_active) if include_product_tabs else ""
    )
    nav_html = public_nav_links_html(active=active) if include_site_nav else ""
    return f"""{tabs}    <header class="brand-panel panel-card" id="{SITE_BRAND_HEADER_ID}" data-site-header="1" data-header-alias="site-brand-header">
      <div class="brand-mark" id="brand-mark" data-brand-mark="1">
        <img class="brand-logo" src="{_esc(src)}" width="{sz}" height="{sz}" alt="Restore Privacy logo"/>
        <h1>{title_safe}</h1>
      </div>
{tagline_html}{nav_html}
{public_theme_picker_html()}
    </header>
"""


def public_head_open(
    *,
    title: str,
    extra_css: str = "",
) -> str:
    """Opening HTML through ``</head><body>`` with shared CSS + theme boot script."""
    title_safe = _esc(title)
    ico = public_favicon_href("/favicon.ico")
    png = public_favicon_href("/favicon.png")
    apple = public_favicon_href("/apple-touch-icon.png")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="color-scheme" content="dark light"/>
  <title>{title_safe}</title>
  <link rel="icon" href="{_esc(ico)}" type="image/x-icon"/>
  <link rel="icon" href="{_esc(png)}" type="image/png" sizes="32x32"/>
  <link rel="apple-touch-icon" href="{_esc(apple)}"/>
  <style>
{public_site_css()}
{extra_css}
  </style>
{public_theme_boot_script()}
</head>
<body>
"""


def public_page_close() -> str:
    return """</body>
</html>
"""
