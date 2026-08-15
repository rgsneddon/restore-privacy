"""Public site footer + optional BMC tip helpers (admin/env only).

Public page bottom bar: © Raskul (left), social icons (middle),
Downloads Map link (right). BMC tip URL/label remain for admin
inventory / optional env overrides only.
"""

from __future__ import annotations

import os

# Public footer (homepage and other public shells that use render_bmc_tip_html).
# Proper copyright sign — never ASCII "(c)" as the public face.
SITE_COPYRIGHT_TEXT = "© Raskul - all rights reserved"
SITE_FOOTER_ID = "site-footer"
SITE_FOOTER_MAP_ID = "site-footer-downloads-map"
SITE_FOOTER_MAP_LABEL = "download map"
# Path is the Downloads Map route (status host + public export).
SITE_FOOTER_MAP_HREF = "/downloads-map"

# Middle social cluster (icons only; handle/name live in aria-label).
SITE_FOOTER_SOCIALS_ID = "site-footer-socials"
SITE_FOOTER_X_HANDLE = "@restorepriv"
SITE_FOOTER_X_HREF = "https://x.com/restorepriv"
SITE_FOOTER_FACEBOOK_HREF = (
    "https://www.facebook.com/profile.php?id=61592756425645"
)
SITE_FOOTER_LINKEDIN_HREF = "https://www.linkedin.com/in/raskul"

# Admin / env tip (not used as public homepage footer).
COFFEE_LINK_TEXT = "buy rus a coffee"
COFFEE_LINK_URL = "https://buymeacoffee.com/rgsneddon"


def coffee_tip_url() -> str:
    """BMC tip URL for admin inventory (env RPT_BMC_TIP_URL overrides default)."""
    return os.environ.get("RPT_BMC_TIP_URL", "").strip() or COFFEE_LINK_URL


def coffee_tip_label() -> str:
    """BMC tip label for admin inventory (env RPT_BMC_TIP_LABEL overrides default)."""
    return os.environ.get("RPT_BMC_TIP_LABEL", "").strip() or COFFEE_LINK_TEXT


def site_copyright_text() -> str:
    """Customer-facing public footer copyright line (always uses © when default)."""
    raw = os.environ.get("RPT_SITE_COPYRIGHT", "").strip()
    if not raw:
        return SITE_COPYRIGHT_TEXT
    # Normalize accidental ASCII (c) to proper copyright sign
    if raw.startswith("(c)") or raw.startswith("(C)"):
        return "©" + raw[3:]
    return raw


def downloads_map_footer_href() -> str:
    return os.environ.get("RPT_DOWNLOADS_MAP_HREF", "").strip() or SITE_FOOTER_MAP_HREF


def downloads_map_footer_label() -> str:
    return (
        os.environ.get("RPT_DOWNLOADS_MAP_LABEL", "").strip() or SITE_FOOTER_MAP_LABEL
    )


def coffee_link_css() -> str:
    """Footer: copyright left, social icons middle, download map right."""
    return """
    .coffee-footer, .site-footer {
      margin-top: auto;
      width: 100%;
      padding: 1.75rem 1rem 1.25rem;
      box-sizing: border-box;
    }
    .site-footer-inner {
      display: flex;
      flex-direction: row;
      flex-wrap: nowrap;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem 0.75rem;
      width: 100%;
      max-width: 56rem;
      margin: 0 auto;
      box-sizing: border-box;
    }
    .site-footer-socials, #site-footer-socials {
      display: flex;
      flex-direction: row;
      flex-wrap: nowrap;
      align-items: center;
      justify-content: center;
      gap: 0.55rem 0.7rem;
      flex: 0 1 auto;
      min-width: 0;
      margin: 0;
      padding: 0;
    }
    a.site-footer-social {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 1.85rem;
      height: 1.85rem;
      color: #7aa0c0;
      text-decoration: none;
      border-radius: 6px;
      flex: 0 0 auto;
    }
    a.site-footer-social:hover {
      color: #aed0ea;
    }
    a.site-footer-social svg {
      display: block;
      width: 1.15rem;
      height: 1.15rem;
      fill: currentColor;
    }
    [data-theme="light"] a.site-footer-social {
      color: #0a2a6e;
    }
    [data-theme="light"] a.site-footer-social:hover {
      color: #0a1628;
    }
    a.coffee-link {
      font-size: 0.8rem;
      color: #64748b;
      text-decoration: none;
      letter-spacing: 0.02em;
    }
    a.coffee-link:hover {
      color: #94a3b8;
      text-decoration: underline;
    }
    .site-footer-copyright, #site-footer-copyright {
      font-size: 0.8rem;
      color: #64748b;
      letter-spacing: 0.02em;
      margin: 0;
      text-align: left;
      flex: 1 1 0;
      min-width: 0;
      /* Shrink left piece on narrow screens rather than wrapping under map */
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .site-footer-map, #site-footer-downloads-map {
      font-size: 0.78rem;
      color: #7aa0c0;
      text-decoration: none;
      letter-spacing: 0.03em;
      margin: 0;
      text-align: right;
      flex: 1 1 0;
      white-space: nowrap;
    }
    .site-footer-map:hover {
      color: #aed0ea;
      text-decoration: underline;
    }
    /* Light mode: footer map link darker for contrast on pale footer */
    [data-theme="light"] .site-footer-map,
    [data-theme="light"] #site-footer-downloads-map {
      color: #0a2a6e;
    }
    [data-theme="light"] .site-footer-map:hover {
      color: #0a1628;
    }
    [data-theme="light"] .site-footer-copyright,
    [data-theme="light"] #site-footer-copyright {
      color: #0f2340;
    }
    /* Narrow screens: stay one row — copyright left, download map right */
    @media (max-width: 420px) {
      .coffee-footer, .site-footer {
        padding-left: 0.65rem;
        padding-right: 0.65rem;
      }
      .site-footer-inner {
        flex-direction: row;
        flex-wrap: nowrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.4rem 0.5rem;
      }
      .site-footer-copyright, #site-footer-copyright {
        text-align: left;
        font-size: 0.72rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .site-footer-map, #site-footer-downloads-map {
        text-align: right;
        font-size: 0.72rem;
        white-space: nowrap;
      }
      .site-footer-socials, #site-footer-socials {
        gap: 0.35rem 0.45rem;
      }
      a.site-footer-social {
        width: 1.6rem;
        height: 1.6rem;
      }
    }
"""


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _social_icon_x() -> str:
    return (
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231'
        "-5.881 6.231H2.254l7.727-8.835L1.254 2.25H8.08l4.253 5.622L18.244 2.25zm"
        '-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77z"/>'
        "</svg>"
    )


def _social_icon_facebook() -> str:
    return (
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<path d="M22 12.06C22 6.5 17.52 2 12 2S2 6.5 2 12.06c0 5.02 3.66 9.18 '
        "8.44 9.94v-7.03H8.08v-2.91h2.36V9.84c0-2.34 1.39-3.64 3.52-3.64 "
        "1.02 0 2.09.18 2.09.18v2.31h-1.18c-1.16 0-1.52.72-1.52 1.46v1.76h2.59"
        'l-.41 2.91h-2.18V22c4.78-.76 8.44-4.92 8.44-9.94z"/>'
        "</svg>"
    )


def _social_icon_linkedin() -> str:
    return (
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 '
        "0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.47-.9 1.63-1.85 "
        "3.36-1.85 3.59 0 4.25 2.36 4.25 5.44v6.3zM5.34 7.43a2.06 2.06 0 1 1 "
        '0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45z"/>'
        "</svg>"
    )


def render_site_footer_socials_html() -> str:
    """Icon-only X / Facebook / LinkedIn cluster for the footer middle."""
    x_href = _esc(SITE_FOOTER_X_HREF)
    x_label = _esc(f"X {SITE_FOOTER_X_HANDLE}")
    fb_href = _esc(SITE_FOOTER_FACEBOOK_HREF)
    li_href = _esc(SITE_FOOTER_LINKEDIN_HREF)
    return f"""      <nav class="site-footer-socials" id="{SITE_FOOTER_SOCIALS_ID}"
           aria-label="Social" data-site-footer-socials="1">
        <a class="site-footer-social" id="site-footer-social-x"
           href="{x_href}" data-social="x" data-handle="{_esc(SITE_FOOTER_X_HANDLE)}"
           target="_blank" rel="noopener noreferrer" aria-label="{x_label}"
           title="{x_label}">{_social_icon_x()}</a>
        <a class="site-footer-social" id="site-footer-social-facebook"
           href="{fb_href}" data-social="facebook"
           target="_blank" rel="noopener noreferrer" aria-label="Facebook"
           title="Facebook">{_social_icon_facebook()}</a>
        <a class="site-footer-social" id="site-footer-social-linkedin"
           href="{li_href}" data-social="linkedin"
           target="_blank" rel="noopener noreferrer" aria-label="LinkedIn"
           title="LinkedIn">{_social_icon_linkedin()}</a>
      </nav>
"""


def render_site_copyright_footer_html(*, map_href: str | None = None) -> str:
    """Public footer: © Raskul (left), social icons (middle), download map (right)."""
    text = site_copyright_text()
    safe = _esc(text)
    map_href = _esc(map_href or downloads_map_footer_href())
    map_label = _esc(downloads_map_footer_label())
    socials = render_site_footer_socials_html()
    return f"""
  <footer class="site-footer coffee-footer" id="{SITE_FOOTER_ID}" data-site-footer="1">
    <div class="site-footer-inner" id="site-footer-inner">
      <p class="site-footer-copyright" id="site-footer-copyright">{safe}</p>
{socials}      <a class="site-footer-map" id="{SITE_FOOTER_MAP_ID}"
         href="{map_href}" data-downloads-map-link="1">{map_label}</a>
    </div>
  </footer>
"""


def render_coffee_link_html() -> str:
    """Deprecated public tip footer — returns copyright + map link."""
    return render_site_copyright_footer_html()
