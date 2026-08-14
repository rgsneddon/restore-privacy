"""Shared public site chrome - brand header, nav buttons, theme (light/dark/device).

Used by homepage, public documents, and Settings guide. **Not** used by /admin.

Visual system (site-chrome-pro): high-end business shell on the logo data-path
palette (navy + cyan/blue/green neon). Dual theme first-class.
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
SDK_LINK_ID = "sdk-link"
SERVICE_LINK_ID = "service-link"

# Public website brand / page identity (document <title> + default page title).
# Visible header no longer shows this as an H1 - banner.jpg is the heading mark.
# Browser-tab title: all-caps product brand (dedicated VPN).
PUBLIC_BRAND_TITLE = "RESTORE PRIVACY"
# Keep in lockstep with downloads.RELEASE_VERSION (catalog monopin).
try:
    from downloads import RELEASE_VERSION as _CATALOG_PIN
except Exception:  # pragma: no cover
    try:
        from status_page.downloads import RELEASE_VERSION as _CATALOG_PIN  # type: ignore
    except Exception:  # pragma: no cover
        _CATALOG_PIN = "1.0.7"
PUBLIC_BRAND_VERSION = str(_CATALOG_PIN).strip() or "1.0.7"
PUBLIC_BRAND_DISPLAY = f"Restore Privacy v{PUBLIC_BRAND_VERSION}"

# Borderless mark: shield + protruding green key only (transparent outside).
# Opaque logo.png remains for favicon/legacy plate uses; Stripe uses stripe_brand_*.
PUBLIC_BRAND_LOGO_PATH = "/logo_transparent.png"
PUBLIC_BRAND_LOGO_STATIC_NAME = "logo_transparent.png"
# Public heading banner (wide wordmark / art from operator Downloads → static).
PUBLIC_BRAND_BANNER_PATH = "/banner.jpg"
PUBLIC_BRAND_BANNER_STATIC_NAME = "banner.jpg"
# Shared display height for logo + banner in the brand header row (px).
# Taller clamp keeps the wide banner.jpg sharp at full content-shell width
# (native banner ~1760×576; logo is square transparent mark).
PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT = 160
PUBLIC_BRAND_HEADER_HEIGHT_MIN_CSS = 96
PUBLIC_BRAND_HEADER_HEIGHT_MAX_CSS = 260
# Legacy size aliases (tests / callers) - height-matched to banner row.
PUBLIC_BRAND_LOGO_SIZE_DEFAULT = PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT
PUBLIC_BRAND_LOGO_SIZE_MIN_CSS = PUBLIC_BRAND_HEADER_HEIGHT_MIN_CSS
PUBLIC_BRAND_LOGO_SIZE_MAX_CSS = PUBLIC_BRAND_HEADER_HEIGHT_MAX_CSS

# Redesign shell markers (tests + progressive CSS hooks)
SITE_CHROME_PRO_CLASS = "site-chrome-pro"
DATA_PATH_LAYER_CLASS = "data-path-layer"
PAGE_SHELL_ID = "page-shell"

# Paths (keep aligned with public_docs / settings_explainer)
HOME_PATH = "/"
LICENSE_PATH = "/LICENSE"
PRIVACY_PATH = "/PRIVACY_POLICY.md"
AUDIT_PATH = "/AUDIT.md"
README_PATH = "/README.md"
SUPPORT_PATH = "/support"
SETTINGS_GUIDE_PATH = "/settings-explainer"
SDK_PATH = "/settings-explainer#corporate-clients"
SDK_ALIAS_PATH = "/sdk"
SERVICE_PATH = "/service"

# Product family landings (paths; optional Host aliases for browser./vault.)
PRODUCT_VPN_PATH = "/"
PRODUCT_BROWSER_PATH = "/browser"
PRODUCT_VAULT_PATH = "/vault"
PRODUCT_VPN_KEY = "vpn"
PRODUCT_BROWSER_KEY = "browser"
PRODUCT_VAULT_KEY = "vault"
# Public product family: dedicated VPN is the live product; Browser/Vault landings stay.
PRODUCT_VPN_LABEL = "Restore Privacy"
PRODUCT_BROWSER_LABEL = "Restore Privacy Browser"
PRODUCT_VAULT_LABEL = "Restore Privacy Vault"
PRODUCT_VPN_TITLE = "RESTORE PRIVACY"
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
        PUBLIC_BRAND_BANNER_STATIC_NAME,
        "favicon.ico",
        "favicon.png",
        "apple-touch-icon.png",
        "data_path_motif.svg",
        "freebie.jpg",  # FREE DOWNLOAD CTA face - cache-bust when art changes
    ):
        p = _STATIC_DIR / name
        if p.is_file():
            h.update(p.read_bytes())
    _BRAND_ASSET_VERSION_CACHE = h.hexdigest()[:12]
    return _BRAND_ASSET_VERSION_CACHE


def public_brand_logo_src() -> str:
    """Borderless logo path with cache-bust query for public header ``<img>``."""
    return f"{PUBLIC_BRAND_LOGO_PATH}?v={public_brand_asset_version()}"


def public_brand_banner_src() -> str:
    """Heading banner path with cache-bust query for public header ``<img>``."""
    return f"{PUBLIC_BRAND_BANNER_PATH}?v={public_brand_asset_version()}"


def public_favicon_href(path: str) -> str:
    """Favicon/apple-touch href with the same brand asset version."""
    base = (path or "").strip() or "/favicon.ico"
    return f"{base}?v={public_brand_asset_version()}"


def public_data_path_motif_src() -> str:
    """Cache-busted SVG circuit / data-path motif (logo-aligned palette)."""
    return f"/static/data_path_motif.svg?v={public_brand_asset_version()}"


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def public_data_path_layer_html() -> str:
    """Decorative ambient data-path layer (aria-hidden; pure presentational)."""
    src = public_data_path_motif_src()
    return f"""
<div class="{DATA_PATH_LAYER_CLASS} data-path-prominent" id="data-path-layer" data-path="1" data-path-prominent="1" aria-hidden="true">
  <div class="data-path-grid"></div>
  <div class="data-path-glow data-path-glow-a"></div>
  <div class="data-path-glow data-path-glow-b"></div>
  <img class="data-path-motif data-path-motif-top" src="{_esc(src)}" alt="" width="1200" height="200"/>
  <img class="data-path-motif data-path-motif-bottom" src="{_esc(src)}" alt="" width="1200" height="200"/>
</div>
"""


def public_site_css() -> str:
    """Site-wide CSS variables, shell, brand header, nav buttons, light/dark themes."""
    try:
        from coffee_link import coffee_link_css
    except ImportError:  # pragma: no cover
        from status_page.coffee_link import coffee_link_css  # type: ignore
    footer_css = coffee_link_css()
    return f"""
/* === Public site chrome (shared) - site-chrome-pro / data-path === */
{footer_css}
:root, [data-theme="dark"] {{
  --rb-navy: #0a1628;
  --rb-navy-mid: #0f2340;
  --rb-card: #132a4a;
  /* Soft fill edge under neon dual-tone border (logo circuit + key palette) */
  --rb-card-border: rgba(0, 229, 255, 0.18);
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
  --rb-neon-glow-cyan: rgba(0, 229, 255, 0.22);
  --rb-neon-glow-green: rgba(57, 255, 106, 0.14);
  --rb-cream: #f2f5f7;
  --rb-muted: #a0bdd4;
  --rb-link: #74b2e2;
  --rb-link-hover: #d7ebf9;
  --rb-btn: #2694e8;
  --rb-btn-deep: #1a6fad;
  --rb-btn-text: #ffffff;
  --rb-soft: #deedf7;
  --rb-accent-sky: #5eb0e8;
  --rb-accent: #5eb0e8;
  /* Sleek business geometry: sharp edges (no toy soft pills on panels) */
  --rb-radius: 0px;
  --rb-radius-sm: 0px;
  --rb-radius-control: 0px;
  --rb-max: 64rem;
  --rb-body-fg: var(--rb-cream);
  --rb-body-bg1: #16325a;
  --rb-body-bg2: var(--rb-navy-mid);
  --rb-body-bg3: var(--rb-navy);
  --rb-body-bg4: #050d18;
  --rb-panel-shadow: 0 12px 40px rgba(2, 8, 20, 0.45);
  --rb-panel-shadow-soft: 0 4px 16px rgba(2, 8, 20, 0.28);
  /* Price callouts always white (sit on navy price panels in both themes) */
  --rb-price-white: #ffffff;
  --rb-price-panel-bg: linear-gradient(165deg, #1a4a7a 0%, #0a1628 70%);
  --rb-code-bg: rgba(10, 22, 40, 0.55);
  --rb-doc-fg: var(--rb-cream);
  --rb-doc-muted: var(--rb-muted);
  --rb-pre-bg: rgba(10, 22, 40, 0.65);
  --rb-pre-border: color-mix(in srgb, var(--rb-neon-cyan) 28%, transparent);
  --rb-input-bg: rgba(6, 14, 28, 0.72);
  --rb-input-border: color-mix(in srgb, var(--rb-neon-cyan) 32%, transparent);
  --rb-field-fg: var(--rb-cream);
  --rb-success-bg: rgba(5, 46, 26, 0.55);
  --rb-success-border: #166534;
  --rb-success-fg: #bbf7d0;
  --rb-error-bg: rgba(63, 29, 29, 0.55);
  --rb-error-border: #7f1d1d;
  --rb-error-fg: #fecaca;
  --rb-font: "Inter", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  --rb-font-mono: ui-monospace, "Cascadia Code", "SF Mono", "Consolas", "Courier New", monospace;
  --rb-space-1: 0.35rem;
  --rb-space-2: 0.65rem;
  --rb-space-3: 1rem;
  --rb-space-4: 1.35rem;
  --rb-space-5: 1.85rem;
  --rb-tracking-tight: 0.02em;
  --rb-tracking-wide: 0.08em;
  --rb-tracking-display: 0.12em;
}}
[data-theme="light"] {{
  --rb-navy: #e8f1f8;
  --rb-navy-mid: #f4f8fb;
  --rb-card: #ffffff;
  --rb-card-border: rgba(0, 180, 220, 0.38);
  --rb-neon-cyan: #00b8d4;
  --rb-neon-blue: #1a8fd4;
  --rb-neon-green: #12c94a;
  --rb-neon-border: linear-gradient(
    135deg,
    var(--rb-neon-cyan) 0%,
    var(--rb-neon-blue) 42%,
    var(--rb-neon-green) 100%
  );
  --rb-neon-glow-cyan: rgba(0, 184, 212, 0.16);
  --rb-neon-glow-green: rgba(18, 201, 74, 0.1);
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
  --rb-body-bg4: #e4ecf4;
  --rb-panel-shadow: 0 10px 32px rgba(15, 35, 64, 0.1);
  --rb-panel-shadow-soft: 0 4px 14px rgba(15, 35, 64, 0.06);
  --rb-price-white: #ffffff;
  --rb-price-panel-bg: linear-gradient(165deg, #2a6fad 0%, #0f2340 75%);
  --rb-code-bg: #f0f5f9;
  --rb-doc-fg: #0f2340;
  --rb-doc-muted: #4a657a;
  --rb-pre-bg: #f4f8fb;
  --rb-pre-border: color-mix(in srgb, var(--rb-neon-cyan) 36%, transparent);
  --rb-input-bg: #ffffff;
  --rb-input-border: color-mix(in srgb, var(--rb-neon-blue) 35%, #c5d5e4);
  --rb-field-fg: #0f2340;
  --rb-success-bg: #ecfdf5;
  --rb-success-border: #6ee7b7;
  --rb-success-fg: #065f46;
  --rb-error-bg: #fef2f2;
  --rb-error-border: #fca5a5;
  --rb-error-fg: #991b1b;
}}
@media (prefers-color-scheme: light) {{
  :root:not([data-theme="dark"]):not([data-theme="light"]) {{
    --rb-navy: #e8f1f8;
    --rb-navy-mid: #f4f8fb;
    --rb-card: #ffffff;
    --rb-card-border: rgba(0, 180, 220, 0.38);
    --rb-neon-cyan: #00b8d4;
    --rb-neon-blue: #1a8fd4;
    --rb-neon-green: #12c94a;
    --rb-neon-border: linear-gradient(
      135deg,
      var(--rb-neon-cyan) 0%,
      var(--rb-neon-blue) 42%,
      var(--rb-neon-green) 100%
    );
    --rb-neon-glow-cyan: rgba(0, 184, 212, 0.16);
    --rb-neon-glow-green: rgba(18, 201, 74, 0.1);
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
    --rb-body-bg4: #e4ecf4;
    --rb-panel-shadow: 0 10px 32px rgba(15, 35, 64, 0.1);
    --rb-panel-shadow-soft: 0 4px 14px rgba(15, 35, 64, 0.06);
    --rb-price-white: #ffffff;
    --rb-price-panel-bg: linear-gradient(165deg, #2a6fad 0%, #0f2340 75%);
    --rb-code-bg: #f0f5f9;
    --rb-doc-fg: #0f2340;
    --rb-doc-muted: #4a657a;
    --rb-pre-bg: #f4f8fb;
    --rb-pre-border: color-mix(in srgb, var(--rb-neon-cyan) 36%, transparent);
    --rb-input-bg: #ffffff;
    --rb-input-border: color-mix(in srgb, var(--rb-neon-blue) 35%, #c5d5e4);
    --rb-field-fg: #0f2340;
    --rb-success-bg: #ecfdf5;
    --rb-success-border: #6ee7b7;
    --rb-success-fg: #065f46;
    --rb-error-bg: #fef2f2;
    --rb-error-border: #fca5a5;
    --rb-error-fg: #991b1b;
  }}
}}
*, *::before, *::after {{ box-sizing: border-box; }}
html {{
  -webkit-text-size-adjust: 100%;
  scroll-behavior: smooth;
}}
body, body.{SITE_CHROME_PRO_CLASS}, body.site-public {{
  margin: 0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  isolation: isolate;
  background:
    radial-gradient(1100px 520px at 50% -8%, var(--rb-body-bg1) 0%, transparent 58%),
    radial-gradient(800px 420px at 100% 100%, color-mix(in srgb, var(--rb-neon-blue) 12%, transparent) 0%, transparent 55%),
    linear-gradient(180deg, var(--rb-body-bg2) 0%, var(--rb-body-bg3) 48%, var(--rb-body-bg4) 100%);
  color: var(--rb-body-fg);
  font-family: var(--rb-font);
  font-size: 16px;
  line-height: 1.5;
  letter-spacing: var(--rb-tracking-tight);
  padding: clamp(1.15rem, 3.2vw, 2.75rem) 0 clamp(2.5rem, 5vw, 3.75rem);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}}
/* Ambient logo-aligned data-path layers (prominent, still non-interactive) */
.{DATA_PATH_LAYER_CLASS}, .data-path-layer {{
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}}
/* data-path-prominent: higher grid + motif contrast than soft ambient */
.data-path-grid {{
  position: absolute;
  inset: 0;
  opacity: 0.42;
  background-image:
    linear-gradient(color-mix(in srgb, var(--rb-neon-cyan) 28%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--rb-neon-blue) 22%, transparent) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(ellipse 90% 75% at 50% 30%, #000 35%, transparent 88%);
  -webkit-mask-image: radial-gradient(ellipse 90% 75% at 50% 30%, #000 35%, transparent 88%);
}}
[data-theme="light"] .data-path-grid {{ opacity: 0.28; }}
.data-path-glow {{
  position: absolute;
  border-radius: 50%;
  filter: blur(56px);
}}
.data-path-glow-a {{
  width: min(52vw, 34rem);
  height: min(52vw, 34rem);
  top: -10%;
  left: 4%;
  background: var(--rb-neon-glow-cyan);
  opacity: 1.15;
}}
.data-path-glow-b {{
  width: min(44vw, 30rem);
  height: min(44vw, 30rem);
  bottom: 2%;
  right: 2%;
  background: var(--rb-neon-glow-green);
  opacity: 1.1;
}}
.data-path-motif {{
  position: absolute;
  left: 0;
  width: 100%;
  height: auto;
  max-height: 22vh;
  object-fit: cover;
  opacity: 0.58;
  mix-blend-mode: screen;
}}
[data-theme="light"] .data-path-motif {{
  opacity: 0.4;
  mix-blend-mode: multiply;
}}
.data-path-motif-top {{ top: 0; transform: scaleY(1); }}
.data-path-motif-bottom {{
  bottom: 0;
  transform: scaleY(-0.95);
  opacity: 0.42;
  max-height: 18vh;
}}
[data-theme="light"] .data-path-motif-bottom {{ opacity: 0.3; }}
.page-shell, #{PAGE_SHELL_ID}, #doc-page-shell, #support-page-shell {{
  width: min(100% - 1.75rem, var(--rb-max));
  display: flex;
  flex-direction: column;
  gap: clamp(0.95rem, 2.2vw, 1.35rem);
  margin: 0 auto;
  position: relative;
  z-index: 1;
}}
/* Product family tabs (VPN / Browser / Vault) - equal full shell width */
#{PRODUCT_TABS_ID}, .product-tabs {{
  display: flex;
  flex-wrap: nowrap;
  justify-content: stretch;
  align-items: stretch;
  gap: 0.55rem;
  width: 100%;
  max-width: 100%;
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}}
a.product-tab, .product-tab {{
  flex: 1 1 0;
  width: 0;
  min-width: 0;
  max-width: none;
  text-align: center;
  text-decoration: none;
  color: var(--rb-cream);
  font-weight: 650;
  letter-spacing: var(--rb-tracking-wide);
  font-size: clamp(0.66rem, 1.7vw, 0.84rem);
  line-height: 1.3;
  padding: 0.78rem 0.45rem;
  border-radius: var(--rb-radius);
  border: 1px solid transparent;
  box-sizing: border-box;
  background:
    linear-gradient(
      165deg,
      color-mix(in srgb, var(--rb-card) 92%, var(--rb-soft)) 0%,
      var(--rb-card) 60%
    ) padding-box,
    var(--rb-neon-border) border-box;
  background-origin: border-box;
  background-clip: padding-box, border-box;
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--rb-neon-cyan) 8%, transparent),
    0 0 12px var(--rb-neon-glow-cyan),
    var(--rb-panel-shadow-soft);
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}}
a.product-tab:hover, .product-tab:hover {{
  transform: translateY(-1px);
  color: var(--rb-cream);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--rb-neon-cyan) 20%, transparent),
    0 0 16px var(--rb-neon-glow-cyan),
    var(--rb-panel-shadow-soft);
}}
a.product-tab.is-active, .product-tab.is-active {{
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--rb-neon-green) 40%, transparent),
    0 0 14px var(--rb-neon-glow-cyan),
    0 0 18px var(--rb-neon-glow-green),
    var(--rb-panel-shadow-soft);
  outline: none;
}}
.product-tab-label {{ display: block; }}
/* Coming-soon product body (Browser / Vault) */
.product-coming-card {{
  text-align: center;
  padding: clamp(1.5rem, 4vw, 2.5rem) clamp(1rem, 3vw, 1.75rem);
}}
.product-coming-title {{
  letter-spacing: var(--rb-tracking-display);
  font-weight: 700;
  font-size: clamp(1.3rem, 4vw, 1.95rem);
  margin: 0 0 0.85rem;
  color: var(--rb-cream);
  line-height: 1.15;
}}
.product-coming-line {{
  margin: 0.35rem 0 0;
  font-size: clamp(0.95rem, 2.6vw, 1.1rem);
  line-height: 1.5;
  color: var(--rb-cream);
  font-weight: 600;
}}
.product-coming-schedule {{
  margin: 0.55rem 0 0;
  font-size: clamp(0.88rem, 2.4vw, 1rem);
  line-height: 1.5;
  color: var(--rb-muted);
  font-weight: 500;
}}
/* Logo data-artifact borders: thin neon edge + retained dual glow (softer prominence) */
.panel-card {{
  position: relative;
  border: 1px solid transparent;
  border-radius: var(--rb-radius);
  padding: clamp(1.05rem, 2.6vw, 1.55rem);
  background:
    linear-gradient(
      165deg,
      color-mix(in srgb, var(--rb-card) 92%, var(--rb-soft)) 0%,
      var(--rb-card) 58%
    ) padding-box,
    var(--rb-neon-border) border-box;
  background-origin: border-box;
  background-clip: padding-box, border-box;
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--rb-neon-cyan) 10%, transparent),
    0 0 14px var(--rb-neon-glow-cyan),
    0 0 22px var(--rb-neon-glow-green),
    var(--rb-panel-shadow);
  overflow: hidden;
}}
.panel-card::before {{
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 1px;
  background: var(--rb-neon-border);
  opacity: 0.55;
  pointer-events: none;
}}
.panel-card::after {{
  content: "";
  position: absolute;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  top: 10px;
  right: 12px;
  background: var(--rb-neon-green);
  box-shadow: 0 0 8px var(--rb-neon-glow-green);
  opacity: 0.5;
  pointer-events: none;
}}
/* Brand header box only: no top-right corner dot */
#{SITE_BRAND_HEADER_ID}.panel-card::after,
.brand-panel.panel-card::after,
#site-brand-header.panel-card::after,
#{SITE_BRAND_HEADER_ID}::after,
.brand-panel::after,
#site-brand-header::after {{
  content: none !important;
  display: none !important;
  width: 0 !important;
  height: 0 !important;
  opacity: 0 !important;
  box-shadow: none !important;
  background: none !important;
}}
.panel-title {{
  margin: 0 0 0.9rem;
  font-size: 0.78rem;
  letter-spacing: var(--rb-tracking-display);
  text-transform: uppercase;
  font-weight: 700;
  color: var(--rb-muted);
  text-align: center;
}}
#{SITE_BRAND_HEADER_ID}, .brand-panel, #site-brand-header {{
  display: flex;
  flex-direction: column;
  align-items: stretch;
  text-align: center;
  gap: 0.75rem;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  /* Full-bleed banner edge-to-edge inside the brand box; pad only below for nav */
  padding-top: 0 !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
  padding-bottom: clamp(0.95rem, 2.4vw, 1.35rem) !important;
  /* Shared logo + banner display height; taller so wordmark/logo fill the strip */
  --rb-brand-header-height: clamp(
    {PUBLIC_BRAND_HEADER_HEIGHT_MIN_CSS}px,
    22vw,
    {PUBLIC_BRAND_HEADER_HEIGHT_MAX_CSS}px
  );
}}
/* Keep nav / rule / theme chrome inset when brand panel padding is zeroed */
#{SITE_BRAND_HEADER_ID} .site-nav,
.brand-panel .site-nav,
#site-brand-header .site-nav,
#{SITE_BRAND_HEADER_ID} .brand-header-rule,
.brand-panel .brand-header-rule,
#site-brand-header .brand-header-rule,
#{SITE_BRAND_HEADER_ID} .brand-tagline,
.brand-panel .brand-tagline,
#site-brand-header .brand-tagline,
#{SITE_BRAND_HEADER_ID} .theme-picker,
.brand-panel .theme-picker,
#site-brand-header .theme-picker,
#{SITE_BRAND_HEADER_ID} .public-theme-picker,
.brand-panel .public-theme-picker,
#site-brand-header .public-theme-picker {{
  margin-left: clamp(1.05rem, 2.6vw, 1.55rem);
  margin-right: clamp(1.05rem, 2.6vw, 1.55rem);
  width: auto;
  max-width: calc(100% - 2 * clamp(1.05rem, 2.6vw, 1.55rem));
  box-sizing: border-box;
}}
/* Banner-only brand mark (no flanking logos) - full width of brand box */
.brand-mark {{
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: stretch;
  justify-content: stretch;
  gap: 0;
  column-gap: 0;
  width: 100%;
  max-width: 100%;
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}}
/* Default public shells: logos inert (banner-only mark). Logo-only shells opt in. */
.brand-logo,
.brand-logo-left,
.brand-logo-right,
.brand-mark .brand-logo {{
  display: none !important;
}}
.brand-banner {{
  /* Full-width fill of the brand box: logo + wordmark occupy the banner area */
  display: block;
  visibility: visible;
  width: 100%;
  max-width: 100%;
  min-width: 100%;
  height: var(--rb-brand-header-height);
  min-height: var(--rb-brand-header-height);
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 0;
  object-fit: cover;
  object-position: center center;
  background: transparent;
  box-shadow: none;
  flex: 1 1 100%;
  image-rendering: -webkit-optimize-contrast;
  image-rendering: high-quality;
  -ms-interpolation-mode: bicubic;
  filter: drop-shadow(0 4px 14px rgba(0, 229, 255, 0.12));
}}
/* Opt-in single logo (pay-plan flow): one logo, no banner */
.brand-panel[data-logo-only="1"] .brand-banner,
.brand-mark[data-logo-only="1"] .brand-banner,
.brand-panel[data-logo-only="1"] img.brand-banner {{
  display: none !important;
  visibility: hidden !important;
}}
.brand-panel[data-logo-only="1"] .brand-logo,
.brand-mark[data-logo-only="1"] .brand-logo,
.brand-panel[data-logo-only="1"] .brand-mark .brand-logo,
.brand-panel[data-logo-only="1"] img.brand-logo {{
  display: block !important;
  visibility: visible !important;
  height: var(--rb-brand-header-height);
  width: auto;
  max-width: min(100%, 12rem);
  min-width: 0;
  margin: 0 auto;
  border: none;
  border-radius: 0;
  object-fit: contain;
  object-position: center;
  background: transparent;
  box-shadow: none;
  flex: 0 0 auto;
  image-rendering: -webkit-optimize-contrast;
  image-rendering: high-quality;
  -ms-interpolation-mode: bicubic;
  filter: drop-shadow(0 4px 14px rgba(0, 229, 255, 0.12));
}}
/* Phone / small screens: default banner-only; logo-only shells keep logo */
@media (max-width: 520px) {{
  .brand-mark {{
    flex-direction: row;
    flex-wrap: nowrap;
    justify-content: center;
    align-items: center;
    gap: 0;
    column-gap: 0;
  }}
  .brand-banner,
  .brand-mark .brand-banner,
  img.brand-banner {{
    display: block !important;
    visibility: visible !important;
    width: 100% !important;
    min-width: 100% !important;
    height: var(--rb-brand-header-height) !important;
    min-height: var(--rb-brand-header-height) !important;
    max-height: none !important;
    margin: 0 !important;
    flex: 1 1 100% !important;
    object-fit: cover !important;
    object-position: center center !important;
  }}
  .brand-logo,
  .brand-logo-left,
  .brand-logo-right,
  .brand-mark .brand-logo {{
    display: none !important;
  }}
  .brand-panel[data-logo-only="1"] .brand-banner,
  .brand-mark[data-logo-only="1"] .brand-banner,
  .brand-panel[data-logo-only="1"] img.brand-banner {{
    display: none !important;
    visibility: hidden !important;
  }}
  .brand-panel[data-logo-only="1"] .brand-logo,
  .brand-mark[data-logo-only="1"] .brand-logo,
  .brand-panel[data-logo-only="1"] img.brand-logo {{
    display: block !important;
    visibility: visible !important;
    height: auto !important;
    max-height: var(--rb-brand-header-height) !important;
    width: auto !important;
    max-width: min(100%, 10rem) !important;
    margin: 0 auto !important;
    flex: 0 0 auto !important;
  }}
}}
/* H1 kept for rare product-page overrides; default header has no title text */
#{SITE_BRAND_HEADER_ID} h1, .brand-panel h1, #site-brand-header h1,
.brand-mark h1 {{
  letter-spacing: var(--rb-tracking-display);
  font-weight: 720;
  font-size: clamp(1.28rem, 4vw, 1.95rem);
  margin: 0;
  color: var(--rb-cream);
  text-align: left;
  line-height: 1.12;
}}
.brand-tagline, .tagline {{
  margin: 0;
  max-width: 36rem;
  font-size: clamp(0.86rem, 2.3vw, 0.98rem);
  line-height: 1.5;
  color: var(--rb-muted);
  font-weight: 500;
}}
.brand-header-rule {{
  width: 100%;
  max-width: 100%;
  height: 1px;
  margin: 0.15rem auto 0;
  border: 0;
  background: var(--rb-neon-border);
  opacity: 0.55;
}}
/* Refined nav - professional pills, not toy balloons */
#{SITE_NAV_ID}, .site-nav, .doc-links, #site-nav {{
  margin: 0.2rem 0 0;
  max-width: 100%;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.15rem;
}}
.nav-btn, a.nav-btn, a.doc-link {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 650;
  letter-spacing: 0.05em;
  font-size: clamp(0.7rem, 1.9vw, 0.8rem);
  text-transform: uppercase;
  text-decoration: none;
  color: var(--rb-cream, #e8f2ff) !important;
  background: transparent;
  border: 0;
  border-radius: 0;
  padding: 0.42rem 0.55rem 0.5rem;
  box-shadow: none;
  border-bottom: 2px solid transparent;
  transition: color 0.14s ease, filter 0.14s ease, border-color 0.14s ease;
}}
.nav-btn:hover, a.nav-btn:hover, a.doc-link:hover {{
  filter: brightness(1.08);
  transform: none;
  color: #ffffff !important;
  background: transparent;
  box-shadow: none;
  border-bottom: 2px solid transparent;
  border-image: linear-gradient(
    90deg,
    var(--rb-neon-cyan, #00e5ff) 0%,
    var(--rb-neon-blue, #2694e8) 42%,
    var(--rb-neon-green, #39ff6a) 100%
  ) 1;
}}
/* Current page: neon-gradient underline (not filled box / pill outline) */
.nav-btn.is-active, a.nav-btn.is-active {{
  outline: none;
  box-shadow: none;
  color: #ffffff !important;
  background: transparent;
  border-bottom: 2px solid transparent;
  border-image: linear-gradient(
    90deg,
    var(--rb-neon-cyan, #00e5ff) 0%,
    var(--rb-neon-blue, #2694e8) 42%,
    var(--rb-neon-green, #39ff6a) 100%
  ) 1;
}}
/* Light mode: active nav label must be dark (not pale/white on light header) */
[data-theme="light"] .nav-btn.is-active,
[data-theme="light"] a.nav-btn.is-active {{
  color: #0a2348 !important;
}}
[data-theme="light"] .nav-btn:hover,
[data-theme="light"] a.nav-btn:hover,
[data-theme="light"] a.doc-link:hover {{
  color: #0a2348 !important;
}}
@media (prefers-color-scheme: light) {{
  :root:not([data-theme="dark"]):not([data-theme="light"]) .nav-btn.is-active,
  :root:not([data-theme="dark"]):not([data-theme="light"]) a.nav-btn.is-active {{
    color: #0a2348 !important;
  }}
  :root:not([data-theme="dark"]):not([data-theme="light"]) .nav-btn:hover,
  :root:not([data-theme="dark"]):not([data-theme="light"]) a.nav-btn:hover,
  :root:not([data-theme="dark"]):not([data-theme="light"]) a.doc-link:hover {{
    color: #0a2348 !important;
  }}
}}
.nav-btn:focus-visible, a.nav-btn:focus-visible, a.doc-link:focus-visible,
.product-tab:focus-visible {{
  outline: 2px solid var(--rb-neon-cyan);
  outline-offset: 3px;
}}
.doc-sep {{ display: none; }}
/* Theme control - calmer segmented control */
#{THEME_MODE_CONTROL_ID}, .theme-mode-control {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.5rem 0.85rem;
  margin: 0.4rem 0 0;
  width: 100%;
}}
.theme-mode-control .theme-ask {{
  margin: 0;
  font-size: 0.72rem;
  color: var(--rb-muted);
  font-weight: 650;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}}
.theme-mode-control fieldset {{
  margin: 0;
  padding: 0.18rem;
  border: 1px solid var(--rb-card-border);
  border-radius: var(--rb-radius-control, 0px);
  display: flex;
  flex-wrap: wrap;
  gap: 0.15rem;
  background: color-mix(in srgb, var(--rb-code-bg) 85%, transparent);
}}
.theme-mode-control legend {{
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0,0,0,0);
}}
.theme-mode-control label {{
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--rb-muted);
  padding: 0.32rem 0.62rem;
  border-radius: var(--rb-radius-control, 0px);
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease;
}}
.theme-mode-control input {{ accent-color: var(--rb-btn); margin: 0; }}
.theme-mode-control label:has(input:checked) {{
  background: color-mix(in srgb, var(--rb-btn) 24%, transparent);
  color: var(--rb-cream);
  outline: 1px solid color-mix(in srgb, var(--rb-btn) 70%, transparent);
}}
/* Settings guide banner */
.settings-banner {{
  text-align: center;
  background: linear-gradient(
    165deg,
    color-mix(in srgb, var(--rb-btn) 14%, var(--rb-card)) 0%,
    var(--rb-card) 62%
  );
}}
.settings-banner-kicker {{
  margin: 0 0 0.4rem;
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--rb-accent-sky);
}}
.settings-banner-title {{
  margin: 0 0 0.5rem;
  font-size: clamp(1.02rem, 2.8vw, 1.22rem);
  font-weight: 750;
  color: var(--rb-cream);
  letter-spacing: 0.04em;
}}
.settings-banner-blurb {{
  margin: 0 auto 0.95rem;
  max-width: 38rem;
  font-size: 0.9rem;
  line-height: 1.55;
  color: var(--rb-muted);
}}
.settings-banner-actions {{ margin: 0; }}
.settings-banner-link, a.settings-banner-link {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 750;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  font-size: 0.8rem;
  color: var(--rb-btn-text) !important;
  background: linear-gradient(180deg, var(--rb-btn) 0%, var(--rb-btn-deep) 100%);
  text-decoration: none;
  padding: 0.58rem 1.2rem;
  border-radius: var(--rb-radius-control, 0px);
  border: 1px solid color-mix(in srgb, var(--rb-link) 40%, transparent);
  box-shadow: 0 6px 18px rgba(10, 22, 40, 0.2);
  transition: filter 0.14s ease, transform 0.14s ease;
}}
.settings-banner-link:hover {{
  filter: brightness(1.07);
  transform: translateY(-1px);
  color: var(--rb-btn-text) !important;
}}
/* Doc body inside box shell */
.doc-body-panel {{
  color: var(--rb-doc-fg);
}}
.doc-body-panel a {{ color: var(--rb-link); font-weight: 600; }}
.doc-body-panel a:hover {{ color: var(--rb-link-hover); }}
.doc-body-panel h1, .doc-body-panel h2, .doc-body-panel h3 {{
  color: var(--rb-cream);
  letter-spacing: 0.02em;
  line-height: 1.25;
}}
.doc-body-panel h1 {{
  font-size: clamp(1.35rem, 3.2vw, 1.75rem);
  font-weight: 750;
}}
.doc-body-panel h2 {{
  font-size: clamp(1.05rem, 2.4vw, 1.25rem);
  margin-top: 1.5rem;
  padding-top: 0.35rem;
  border-top: 1px solid color-mix(in srgb, var(--rb-card-border) 70%, transparent);
}}
.doc-body-panel .muted, .doc-body-panel .doc-muted {{ color: var(--rb-doc-muted); }}
.doc-plain, pre.doc-plain {{
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: var(--rb-font-mono);
  font-size: 0.86rem;
  line-height: 1.55;
  background: var(--rb-pre-bg);
  border: 1px solid var(--rb-pre-border);
  border-radius: var(--rb-radius-sm);
  padding: 1.05rem 1.15rem;
  color: var(--rb-doc-fg);
  margin: 0;
}}
.doc-code {{
  background: var(--rb-pre-bg);
  border: 1px solid var(--rb-pre-border);
  border-radius: var(--rb-radius-sm);
  padding: 0.75rem;
  overflow-x: auto;
}}
.doc-body table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
  margin: 0.85rem 0 1.1rem;
}}
.doc-body th, .doc-body td {{
  border: 1px solid var(--rb-card-border);
  padding: 0.45rem 0.6rem;
  vertical-align: top;
}}
.doc-body th {{
  background: var(--rb-code-bg);
  font-weight: 700;
  letter-spacing: 0.02em;
}}
.doc-foot {{
  margin-top: 0.25rem;
  text-align: center;
  font-size: 0.86rem;
  color: var(--rb-muted);
}}
.doc-foot a {{
  color: var(--rb-link);
  font-weight: 600;
  margin: 0 0.4rem;
  text-decoration: none;
}}
.doc-foot a:hover {{ color: var(--rb-link-hover); text-decoration: underline; }}
/* Shared form / CTA primitives (support + buy) */
.btn-primary, button.btn-primary {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  appearance: none;
  border: 1px solid color-mix(in srgb, var(--rb-link) 35%, transparent);
  border-radius: var(--rb-radius-sm);
  padding: 0.72rem 1.35rem;
  background: linear-gradient(180deg, var(--rb-btn) 0%, var(--rb-btn-deep) 100%);
  color: var(--rb-btn-text);
  font: inherit;
  font-weight: 750;
  letter-spacing: 0.03em;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(10, 22, 40, 0.22);
  transition: filter 0.14s ease, transform 0.14s ease;
}}
.btn-primary:hover, button.btn-primary:hover {{
  filter: brightness(1.07);
  transform: translateY(-1px);
}}
.field-input, .field-select, .field-textarea {{
  width: 100%;
  box-sizing: border-box;
  padding: 0.7rem 0.85rem;
  border-radius: var(--rb-radius-sm);
  border: 1px solid var(--rb-input-border);
  background: var(--rb-input-bg);
  color: var(--rb-field-fg);
  font: inherit;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}}
.field-input:focus, .field-select:focus, .field-textarea:focus {{
  outline: none;
  border-color: color-mix(in srgb, var(--rb-neon-cyan) 55%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--rb-neon-cyan) 18%, transparent);
}}
/* Support page form (shared shell) */
.support-wrap {{
  width: 100%;
  max-width: 40rem;
  margin: 0 auto;
}}
.support-wrap h2 {{
  margin: 0 0 0.45rem;
  font-size: clamp(1.15rem, 2.8vw, 1.4rem);
  font-weight: 750;
  letter-spacing: 0.04em;
  color: var(--rb-cream);
}}
.support-lead {{
  color: var(--rb-muted);
  margin: 0 0 1.15rem;
  line-height: 1.55;
  font-size: 0.95rem;
}}
.support-form label {{
  display: block;
  margin: 0.85rem 0 0.3rem;
  font-weight: 650;
  font-size: 0.84rem;
  letter-spacing: 0.02em;
  color: var(--rb-cream);
}}
.support-form input,
.support-form select,
.support-form textarea {{
  width: 100%;
  box-sizing: border-box;
  padding: 0.7rem 0.85rem;
  border-radius: var(--rb-radius-sm);
  border: 1px solid var(--rb-input-border);
  background: var(--rb-input-bg);
  color: var(--rb-field-fg);
  font: inherit;
}}
.support-form input:focus,
.support-form select:focus,
.support-form textarea:focus {{
  outline: none;
  border-color: color-mix(in srgb, var(--rb-neon-cyan) 55%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--rb-neon-cyan) 18%, transparent);
}}
.support-form textarea {{ min-height: 9.5rem; resize: vertical; }}
.support-form .hint {{
  font-size: 0.78rem;
  color: var(--rb-muted);
  font-weight: 500;
  margin-top: 0.2rem;
}}
.support-form button,
#support-submit {{
  margin-top: 1.2rem;
  appearance: none;
  border: 1px solid color-mix(in srgb, var(--rb-link) 35%, transparent);
  border-radius: var(--rb-radius-sm);
  padding: 0.78rem 1.4rem;
  background: linear-gradient(180deg, var(--rb-btn) 0%, var(--rb-btn-deep) 100%);
  color: var(--rb-btn-text);
  font: inherit;
  font-weight: 750;
  letter-spacing: 0.04em;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(10, 22, 40, 0.22);
  transition: filter 0.14s ease, transform 0.14s ease;
}}
.support-form button:hover,
#support-submit:hover {{
  filter: brightness(1.07);
  transform: translateY(-1px);
}}
.support-err {{
  color: var(--rb-error-fg);
  background: var(--rb-error-bg);
  border: 1px solid var(--rb-error-border);
  padding: 0.75rem 0.95rem;
  border-radius: var(--rb-radius-sm);
  margin: 0 0 1rem;
  font-weight: 600;
}}
.support-ok {{
  background: var(--rb-success-bg);
  border: 1px solid var(--rb-success-border);
  border-radius: var(--rb-radius);
  padding: 0.95rem 1.05rem;
  margin: 0 0 1.15rem;
  color: var(--rb-success-fg);
}}
.support-ok code {{
  font-size: 0.95rem;
  font-family: var(--rb-font-mono);
  letter-spacing: 0.03em;
}}
/* Reduced motion */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }}
}}
/* Responsive - tablet */
@media (max-width: 820px) {{
  .page-shell, #{PAGE_SHELL_ID}, #doc-page-shell, #support-page-shell {{
    width: min(100% - 1.35rem, var(--rb-max));
  }}
  a.product-tab, .product-tab {{
    font-size: clamp(0.62rem, 2.1vw, 0.76rem);
    padding: 0.7rem 0.35rem;
  }}
}}
/* Responsive - phone */
@media (max-width: 520px) {{
  body, body.{SITE_CHROME_PRO_CLASS}, body.site-public {{
    padding: 0.85rem 0 2.25rem;
  }}
  .page-shell, #{PAGE_SHELL_ID}, #doc-page-shell, #support-page-shell {{
    width: min(100% - 0.95rem, var(--rb-max));
    gap: 0.85rem;
  }}
  .nav-btn, a.nav-btn, a.doc-link {{
    font-size: 0.66rem;
    padding: 0.4rem 0.68rem;
  }}
  .panel-card {{
    padding: 0.95rem 0.9rem;
  }}
  #{SITE_BRAND_HEADER_ID} h1, .brand-panel h1, .brand-mark h1 {{
    text-align: center;
    font-size: clamp(1.1rem, 5.5vw, 1.45rem);
  }}
  /* brand-mark phone: banner-only (no logo fallback) */
}}
/* Desktop/tablet: default banner-only mark; logo-only shells keep logo */
@media (min-width: 521px) {{
  .brand-mark {{
    flex-direction: row;
    flex-wrap: nowrap;
    align-items: center;
    justify-content: center;
    gap: 0;
    column-gap: 0;
  }}
  .brand-banner {{
    display: block;
    visibility: visible;
    object-fit: cover;
    object-position: center center;
    width: 100%;
    min-width: 100%;
    height: var(--rb-brand-header-height);
  }}
  .brand-logo,
  .brand-logo-left,
  .brand-logo-right {{
    display: none !important;
  }}
  .brand-panel[data-logo-only="1"] .brand-banner {{
    display: none !important;
  }}
  .brand-panel[data-logo-only="1"] .brand-logo,
  .brand-panel[data-logo-only="1"] .brand-mark .brand-logo {{
    display: block !important;
  }}
  #{SITE_BRAND_HEADER_ID} h1, .brand-panel h1, .brand-mark h1 {{
    text-align: left;
  }}
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
    """Button-style nav: Home → Settings Guide → SDK → Licence →
    Security Audit → Privacy Policy → Support.

    *active* is one of: home, licence, privacy, audit, support, settings, sdk
    (or None). README is not a main-menu control (``/README.md`` may still be
    served as a document). Settings Guide remains in the top brand nav.
    SDK jumps to the corporate / MISHI retainer box on the Settings guide.

    Service (``SERVICE_PATH`` / ``/service``) is intentionally **not** in the
    public main menu - the page module and route are retained for private use.
    """
    items = (
        ("HOME", HOME_PATH, HOME_LINK_ID, "home"),
        ("SETTINGS GUIDE", SETTINGS_GUIDE_PATH, SETTINGS_GUIDE_LINK_ID, "settings"),
        ("SDK", SDK_PATH, SDK_LINK_ID, "sdk"),
        ("LICENCE", LICENSE_PATH, LICENCE_LINK_ID, "licence"),
        ("SECURITY AUDIT", AUDIT_PATH, AUDIT_LINK_ID, "audit"),
        ("PRIVACY POLICY", PRIVACY_PATH, PRIVACY_LINK_ID, "privacy"),
        ("SUPPORT", SUPPORT_PATH, SUPPORT_LINK_ID, "support"),
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
    """Normalize product title for public brand chrome and document ``<title>``.

    Maps historical Suite / short titles to :data:`PUBLIC_BRAND_TITLE`
    (**RESTORE PRIVACY**). Empty / missing → product brand. Body copy describes
    the dedicated VPN; tab title stays the short brand.
    """
    t = (raw or "").strip()
    if not t:
        return PUBLIC_BRAND_TITLE
    # Exact legacy Suite / VPN / short brand strings → canonical brand
    if t in (
        "RESTORE PRIVACY",
        "RESTORE PRIVACY VPN",
        "RESTORE PRIVACY SUITE",
        "Restore Privacy VPN",
        "Restore Privacy",
        "Restore Privacy Suite",
        PUBLIC_BRAND_TITLE,
    ):
        return PUBLIC_BRAND_TITLE
    compact = " ".join(t.upper().split())
    if compact in (
        "RESTORE PRIVACY",
        "RESTORE PRIVACY VPN",
        "RESTORE PRIVACY SUITE",
    ) or compact.startswith("RESTORE PRIVACY VPN") or compact.startswith(
        "RESTORE PRIVACY SUITE"
    ):
        return PUBLIC_BRAND_TITLE
    # Legacy sole-VPN product brand wording → canonical short brand
    if "VPN" in compact and "RESTORE PRIVACY" in compact:
        return PUBLIC_BRAND_TITLE
    if "SUITE" in compact and "RESTORE PRIVACY" in compact:
        return PUBLIC_BRAND_TITLE
    return t


# Homepage lead copy (human cadence — dedicated VPN; one job for this section).
SUITE_HOME_INTRO_ID = "suite-home-intro"
# Neon typewriter lines (one-shot keystroke animation on page load)
SUITE_HOME_WELCOME_TYPE = ".:WELCOME, ANON:."
SUITE_HOME_CLOSING_TYPE = "YOUR PRIVACY, RESTORED"
# Normal CSS heading (not neon typewriter)
SUITE_HOME_INTRO_HEADING = "...privacy you can actually use..."
# Legacy alias for callers/tests that still import the short human title idea
SUITE_HOME_INTRO_HEADING_LEGACY = "Privacy you can actually use"
# What the product is + how to start. Price once. Closing typewriter carries the tagline.
SUITE_HOME_INTRO_BODY = (
    "Restore Privacy is a virtual private network for your device and personal use. "
    "Download the client free from the link below, try three days free with no "
    "obligation to pay, then keep your privacy restored with a Restore Privacy VPN "
    "subscription (£3 a month or £30 a year)."
)
# Foot retired: closing typewriter is the end line
SUITE_HOME_INTRO_FOOT = ""


def typewriter_prefix(full: str, step: int) -> str:
    """Return progressive typewriter text for *step* (0 = empty, len = complete)."""
    text = full or ""
    n = max(0, min(int(step), len(text)))
    return text[:n]


def typewriter_done(full: str, step: int) -> bool:
    """True when typewriter has finished the full string (and stays done)."""
    return int(step) >= len(full or "")


def typewriter_sequence(full: str) -> list[str]:
    """All progressive prefixes including empty start and final full string."""
    text = full or ""
    return [typewriter_prefix(text, i) for i in range(len(text) + 1)]


def render_suite_home_intro_html() -> str:
    """Suite welcome block: neon typewriters + tagline + body (above free downloads)."""
    welcome = _esc(SUITE_HOME_WELCOME_TYPE)
    closing = _esc(SUITE_HOME_CLOSING_TYPE)
    heading = _esc(SUITE_HOME_INTRO_HEADING)
    body = _esc(SUITE_HOME_INTRO_BODY)
    return f"""  <section class="panel-card suite-home-intro" id="{SUITE_HOME_INTRO_ID}"
           aria-labelledby="suite-home-intro-title" data-product="suite"
           data-suite-version="{PUBLIC_BRAND_VERSION}" data-suite-intro="1">
    <p class="suite-typewriter suite-typewriter-welcome neon-type"
       id="suite-welcome-type"
       data-typewriter="1"
       data-typewriter-role="welcome"
       data-typewriter-text="{welcome}"
       data-typewriter-once="1"
       aria-label="{welcome}"></p>
    <h2 class="suite-home-tagline" id="suite-home-intro-title">{heading}</h2>
    <p class="suite-home-lead" id="suite-home-lead">{body}</p>
    <p class="suite-typewriter suite-typewriter-close neon-type"
       id="suite-closing-type"
       data-typewriter="1"
       data-typewriter-role="closing"
       data-typewriter-text="{closing}"
       data-typewriter-once="1"
       data-typewriter-after="suite-welcome-type"
       aria-label="{closing}"></p>
    <p class="suite-home-version" id="suite-home-version">{PUBLIC_BRAND_DISPLAY}</p>
  </section>
"""


def suite_home_intro_script_tag() -> str:
    """Same-origin one-shot typewriter script for the Suite intro panel."""
    return (
        '<script id="suite-home-typewriter-script" '
        'src="/static/suite_home_typewriter.js" defer></script>\n'
    )


def suite_home_intro_css() -> str:
    return """
    .suite-home-intro {
      text-align: center; margin: 0 0 1.15rem; padding: 1.25rem 1.15rem 1.15rem;
    }
    .suite-home-tagline,
    .suite-home-intro h2 {
      margin: 0.55rem auto 0.75rem; max-width: 40rem;
      font-size: clamp(1.15rem, 3vw, 1.5rem);
      letter-spacing: 0.03em; color: var(--rb-cream, #fff); font-weight: 700;
      font-family: inherit; line-height: 1.3;
    }
    .suite-home-lead {
      margin: 0 auto 0.95rem; max-width: 42rem; line-height: 1.58;
      font-size: clamp(0.95rem, 2.2vw, 1.08rem); color: var(--rb-soft, #aed0ea);
      font-weight: 500;
    }
    .suite-home-foot {
      margin: 0 auto 0.55rem; max-width: 32rem; font-size: 0.9rem;
      color: var(--rb-muted, #8eb4d0); line-height: 1.45;
    }
    .suite-home-version {
      margin: 0.65rem 0 0; font-size: 0.78rem; letter-spacing: 0.06em; font-weight: 700;
      color: var(--rb-accent-sky, #7dd3fc); text-transform: uppercase;
    }
    /* Neon typewriter (welcome + closing) - large mono, blue/green glow */
    .suite-typewriter,
    .neon-type {
      margin: 0 auto;
      min-height: 1.35em;
      max-width: 44rem;
      font-family: "Courier New", Courier, ui-monospace, monospace;
      font-size: clamp(1.45rem, 4.2vw, 2.15rem);
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      line-height: 1.35;
      color: #7dffe8;
      text-shadow:
        0 0 6px rgba(0, 229, 255, 0.85),
        0 0 14px rgba(57, 255, 136, 0.55),
        0 0 28px rgba(0, 229, 255, 0.35);
      white-space: pre-wrap;
      word-break: break-word;
    }
    .suite-typewriter-welcome { margin-top: 0.15rem; margin-bottom: 0.35rem; }
    /* Closing line: slightly smaller so full "YOUR PRIVACY, RESTORED" fits on
       phones/tablets (shared typewriter clamp is larger for welcome). */
    .suite-typewriter-close {
      margin-top: 0.85rem;
      margin-bottom: 0.25rem;
      font-size: clamp(1.05rem, 3.2vw, 1.55rem);
      letter-spacing: 0.08em;
      max-width: min(44rem, 96vw);
    }
    .suite-typewriter.is-typing::after {
      content: "▌";
      display: inline-block;
      margin-left: 0.08em;
      color: #39ff88;
      text-shadow: 0 0 8px rgba(57, 255, 136, 0.9);
      animation: suite-type-caret 0.85s step-end infinite;
    }
    .suite-typewriter.is-done::after { content: none; }
    @keyframes suite-type-caret {
      50% { opacity: 0; }
    }
    /* Light mode only: dark blue typewriters + darker intro blurb (dark mode unchanged).
       Scope .suite-typewriter only - do not recolor free-download .neon-type CTA. */
    [data-theme="light"] .suite-typewriter,
    [data-theme="light"] .suite-typewriter.neon-type,
    [data-theme="light"] .suite-typewriter-welcome,
    [data-theme="light"] .suite-typewriter-close {
      color: #0a2a6e;
      text-shadow: none;
    }
    [data-theme="light"] .suite-typewriter.is-typing::after {
      color: #0a2a6e;
      text-shadow: none;
    }
    [data-theme="light"] .suite-home-lead {
      color: #0f2340;
      font-weight: 600;
    }
    @media (prefers-color-scheme: light) {
      :root:not([data-theme="dark"]):not([data-theme="light"]) .suite-typewriter,
      :root:not([data-theme="dark"]):not([data-theme="light"]) .suite-typewriter.neon-type,
      :root:not([data-theme="dark"]):not([data-theme="light"]) .suite-typewriter-welcome,
      :root:not([data-theme="dark"]):not([data-theme="light"]) .suite-typewriter-close {
        color: #0a2a6e;
        text-shadow: none;
      }
      :root:not([data-theme="dark"]):not([data-theme="light"]) .suite-typewriter.is-typing::after {
        color: #0a2a6e;
        text-shadow: none;
      }
      :root:not([data-theme="dark"]):not([data-theme="light"]) .suite-home-lead {
        color: #0f2340;
        font-weight: 600;
      }
    }
"""


def public_brand_header_html(
    *,
    title: str = PUBLIC_BRAND_TITLE,
    tagline: str = "",
    active: str | None = None,
    logo_size: int = PUBLIC_BRAND_LOGO_SIZE_DEFAULT,
    logo_src: str = PUBLIC_BRAND_LOGO_PATH,
    banner_src: str = PUBLIC_BRAND_BANNER_PATH,
    product_active: str = PRODUCT_VPN_KEY,
    include_product_tabs: bool = False,
    include_site_nav: bool = True,
    show_title_text: bool = False,
    mark: str = "banner",
) -> str:
    """Static top brand panel used across public pages.

    Default *mark* is **banner** (full-width banner.jpg, no logos) for homepage
    and most public shells. Pass ``mark="logo"`` for pay-flow and other shells
    that want **exactly one** logo and no banner image.
    *title* still normalizes page titles for callers.
    """
    _ = title  # retained for API compat (page titles use public_display_title)
    mode = (mark or "banner").strip().lower()
    if mode not in ("banner", "logo"):
        mode = "banner"
    # Display height (height attr; CSS clamps via --rb-brand-header-height)
    sz = int(logo_size) if logo_size else PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT
    if sz < 48:
        sz = PUBLIC_BRAND_HEADER_HEIGHT_DEFAULT
    h_attr = sz
    tag = (tagline or "").strip()
    tagline_html = (
        f'      <p class="brand-tagline">{_esc(tag)}</p>\n' if tag else ""
    )
    tabs = (
        public_product_tabs_html(active=product_active) if include_product_tabs else ""
    )
    nav_html = public_nav_links_html(active=active) if include_site_nav else ""
    # Optional H1 only when explicitly requested (not default VPN heading text).
    title_html = ""
    if show_title_text:
        raw_title = (title or "").strip()
        if raw_title in (PRODUCT_BROWSER_TITLE, PRODUCT_VAULT_TITLE):
            title_safe = _esc(raw_title)
        else:
            title_safe = _esc(public_display_title(title))
        title_html = f"\n        <h1>{title_safe}</h1>"

    if mode == "logo":
        raw_logo = (logo_src or PUBLIC_BRAND_LOGO_PATH).strip() or PUBLIC_BRAND_LOGO_PATH
        if raw_logo == PUBLIC_BRAND_LOGO_PATH or raw_logo.startswith(
            f"{PUBLIC_BRAND_LOGO_PATH}?"
        ):
            lsrc = public_brand_logo_src()
        else:
            lsrc = raw_logo
        mark_html = f"""      <div class="brand-mark" id="brand-mark" data-brand-mark="1" data-logo-only="1">
        <img class="brand-logo" id="brand-logo" src="{_esc(lsrc)}" height="{h_attr}" alt="Restore Privacy"/>{title_html}
      </div>"""
        header_data = (
            f'data-site-header="1" data-header-alias="site-brand-header" '
            f'data-chrome="pro" data-brand-logo="1" data-logo-only="1"'
        )
    else:
        raw_banner = (
            (banner_src or PUBLIC_BRAND_BANNER_PATH).strip() or PUBLIC_BRAND_BANNER_PATH
        )
        if raw_banner == PUBLIC_BRAND_BANNER_PATH or raw_banner.startswith(
            f"{PUBLIC_BRAND_BANNER_PATH}?"
        ):
            bsrc = public_brand_banner_src()
        else:
            bsrc = raw_banner
        mark_html = f"""      <div class="brand-mark" id="brand-mark" data-brand-mark="1" data-banner-only="1">
        <img class="brand-banner" id="brand-banner" src="{_esc(bsrc)}" height="{h_attr}" alt="Restore Privacy"/>{title_html}
      </div>"""
        header_data = (
            f'data-site-header="1" data-header-alias="site-brand-header" '
            f'data-chrome="pro" data-brand-banner="1" data-banner-only="1"'
        )
    return f"""{tabs}    <header class="brand-panel panel-card" id="{SITE_BRAND_HEADER_ID}" {header_data}>
{mark_html}
      <hr class="brand-header-rule" aria-hidden="true"/>
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
    ambient = public_data_path_layer_html()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="color-scheme" content="dark light"/>
  <meta name="theme-color" content="#0a1628" media="(prefers-color-scheme: dark)"/>
  <meta name="theme-color" content="#e8f1f8" media="(prefers-color-scheme: light)"/>
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
<body class="site-public {SITE_CHROME_PRO_CLASS}" data-chrome="pro">
{ambient}
"""


def public_page_close() -> str:
    """Close every public HTML shell with the shared copyright + map footer.

    Copyright left, downloads map link right - same line on all public pages
    that use this closer (home, downloads-map, docs, support, settings guide,
    product family landings, …). Admin routes do not use this helper.
    """
    try:
        from coffee_link import render_site_copyright_footer_html
    except ImportError:  # pragma: no cover
        from status_page.coffee_link import (  # type: ignore
            render_site_copyright_footer_html,
        )
    return f"""{render_site_copyright_footer_html()}
</body>
</html>
"""
