"""Shared public site chrome — brand header, nav buttons, theme (light/dark/device).

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
        "data_path_motif.svg",
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
<div class="{DATA_PATH_LAYER_CLASS}" id="data-path-layer" data-path="1" aria-hidden="true">
  <div class="data-path-grid"></div>
  <div class="data-path-glow data-path-glow-a"></div>
  <div class="data-path-glow data-path-glow-b"></div>
  <img class="data-path-motif data-path-motif-top" src="{_esc(src)}" alt="" width="1200" height="200"/>
  <img class="data-path-motif data-path-motif-bottom" src="{_esc(src)}" alt="" width="1200" height="200"/>
</div>
"""


def public_site_css() -> str:
    """Site-wide CSS variables, shell, brand header, nav buttons, light/dark themes."""
    return f"""
/* === Public site chrome (shared) — site-chrome-pro / data-path === */
:root, [data-theme="dark"] {{
  --rb-navy: #0a1628;
  --rb-navy-mid: #0f2340;
  --rb-card: #132a4a;
  /* Soft fill edge under neon dual-tone border (logo circuit + key palette) */
  --rb-card-border: rgba(0, 229, 255, 0.28);
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
  --rb-radius: 14px;
  --rb-radius-sm: 10px;
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
/* Ambient logo-aligned data-path layers */
.{DATA_PATH_LAYER_CLASS}, .data-path-layer {{
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}}
.data-path-grid {{
  position: absolute;
  inset: 0;
  opacity: 0.22;
  background-image:
    linear-gradient(color-mix(in srgb, var(--rb-neon-cyan) 18%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--rb-neon-blue) 14%, transparent) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 75% 60% at 50% 20%, #000 20%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse 75% 60% at 50% 20%, #000 20%, transparent 75%);
}}
[data-theme="light"] .data-path-grid {{ opacity: 0.14; }}
.data-path-glow {{
  position: absolute;
  border-radius: 50%;
  filter: blur(48px);
}}
.data-path-glow-a {{
  width: min(42vw, 28rem);
  height: min(42vw, 28rem);
  top: -8%;
  left: 8%;
  background: var(--rb-neon-glow-cyan);
}}
.data-path-glow-b {{
  width: min(36vw, 24rem);
  height: min(36vw, 24rem);
  bottom: 4%;
  right: 6%;
  background: var(--rb-neon-glow-green);
}}
.data-path-motif {{
  position: absolute;
  left: 0;
  width: 100%;
  height: auto;
  max-height: 14vh;
  object-fit: cover;
  opacity: 0.38;
  mix-blend-mode: screen;
}}
[data-theme="light"] .data-path-motif {{
  opacity: 0.28;
  mix-blend-mode: multiply;
}}
.data-path-motif-top {{ top: 0; transform: scaleY(0.85); }}
.data-path-motif-bottom {{
  bottom: 0;
  transform: scaleY(-0.75);
  opacity: 0.22;
}}
.page-shell, #{PAGE_SHELL_ID}, #doc-page-shell, #support-page-shell {{
  width: min(100% - 1.75rem, var(--rb-max));
  display: flex;
  flex-direction: column;
  gap: clamp(0.95rem, 2.2vw, 1.35rem);
  margin: 0 auto;
  position: relative;
  z-index: 1;
}}
/* Product family tabs (VPN / Browser / Vault) — equal full shell width */
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
  border: 1.5px solid transparent;
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
    0 0 0 1px color-mix(in srgb, var(--rb-neon-cyan) 12%, transparent),
    var(--rb-panel-shadow-soft);
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}}
a.product-tab:hover, .product-tab:hover {{
  transform: translateY(-1px);
  color: var(--rb-cream);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--rb-neon-cyan) 28%, transparent),
    0 0 18px var(--rb-neon-glow-cyan),
    var(--rb-panel-shadow-soft);
}}
a.product-tab.is-active, .product-tab.is-active {{
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--rb-neon-green) 48%, transparent),
    0 0 16px var(--rb-neon-glow-cyan),
    0 0 22px var(--rb-neon-glow-green),
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
/* Logo data-artifact borders: neon cyan/blue → green gradient + refined glow */
.panel-card {{
  position: relative;
  border: 1.5px solid transparent;
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
    0 0 0 1px color-mix(in srgb, var(--rb-neon-cyan) 14%, transparent),
    0 0 18px var(--rb-neon-glow-cyan),
    0 0 28px var(--rb-neon-glow-green),
    var(--rb-panel-shadow);
  overflow: hidden;
}}
.panel-card::before {{
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 2px;
  background: var(--rb-neon-border);
  opacity: 0.85;
  pointer-events: none;
}}
.panel-card::after {{
  content: "";
  position: absolute;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  top: 10px;
  right: 12px;
  background: var(--rb-neon-green);
  box-shadow: 0 0 10px var(--rb-neon-glow-green);
  opacity: 0.7;
  pointer-events: none;
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
  align-items: center;
  text-align: center;
  gap: 0.85rem;
}}
/* Logo + title row: centered above the menu */
.brand-mark {{
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: clamp(0.55rem, 2vw, 1rem);
  width: 100%;
  max-width: 100%;
}}
.brand-logo {{
  width: clamp(88px, 16vw, 120px);
  height: clamp(88px, 16vw, 120px);
  border: none;
  border-radius: 0;
  object-fit: contain;
  background: transparent;
  box-shadow: none;
  flex-shrink: 0;
  filter: drop-shadow(0 4px 14px rgba(0, 229, 255, 0.18));
}}
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
  width: min(100%, 22rem);
  height: 1px;
  margin: 0.15rem auto 0;
  border: 0;
  background: var(--rb-neon-border);
  opacity: 0.55;
}}
/* Refined nav — professional pills, not toy balloons */
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
  color: var(--rb-btn-text) !important;
  background: linear-gradient(180deg, var(--rb-btn) 0%, var(--rb-btn-deep) 100%);
  border: 1px solid color-mix(in srgb, var(--rb-link) 42%, transparent);
  border-radius: 999px;
  padding: 0.48rem 0.95rem;
  box-shadow: 0 3px 10px rgba(10, 22, 40, 0.18);
  transition: filter 0.14s ease, transform 0.14s ease, box-shadow 0.14s ease;
}}
.nav-btn:hover, a.nav-btn:hover, a.doc-link:hover {{
  filter: brightness(1.07);
  transform: translateY(-1px);
  color: var(--rb-btn-text) !important;
  background: linear-gradient(180deg, var(--rb-accent-sky) 0%, var(--rb-btn) 100%);
  box-shadow: 0 5px 14px rgba(10, 22, 40, 0.22);
}}
.nav-btn.is-active, a.nav-btn.is-active {{
  outline: 2px solid color-mix(in srgb, var(--rb-neon-cyan) 65%, var(--rb-soft));
  outline-offset: 2px;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--rb-neon-green) 35%, transparent),
    0 4px 14px rgba(10, 22, 40, 0.2);
}}
.nav-btn:focus-visible, a.nav-btn:focus-visible, a.doc-link:focus-visible,
.product-tab:focus-visible {{
  outline: 2px solid var(--rb-neon-cyan);
  outline-offset: 3px;
}}
.doc-sep {{ display: none; }}
/* Theme control — calmer segmented control */
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
  border-radius: 999px;
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
  border-radius: 999px;
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
  border-radius: 999px;
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
/* Responsive — tablet */
@media (max-width: 820px) {{
  .page-shell, #{PAGE_SHELL_ID}, #doc-page-shell, #support-page-shell {{
    width: min(100% - 1.35rem, var(--rb-max));
  }}
  a.product-tab, .product-tab {{
    font-size: clamp(0.62rem, 2.1vw, 0.76rem);
    padding: 0.7rem 0.35rem;
  }}
}}
/* Responsive — phone */
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
  .brand-mark {{
    flex-direction: column;
  }}
  /* Override row for logo+title on very small if tests allow — keep row for tests via min-width */
}}
/* Keep brand-mark row orientation for structure (logo left of title) at ≥360px */
@media (min-width: 360px) {{
  .brand-mark {{
    flex-direction: row;
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
    return f"""{tabs}    <header class="brand-panel panel-card" id="{SITE_BRAND_HEADER_ID}" data-site-header="1" data-header-alias="site-brand-header" data-chrome="pro">
      <div class="brand-mark" id="brand-mark" data-brand-mark="1">
        <img class="brand-logo" src="{_esc(src)}" width="{sz}" height="{sz}" alt="Restore Privacy logo"/>
        <h1>{title_safe}</h1>
      </div>
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
    return """</body>
</html>
"""
