"""Public site footer + optional BMC tip helpers (admin/env only).

Public page bottom bar: © Raskul (left) + discrete Downloads Map link (right).
BMC tip URL/label remain for admin inventory / optional env overrides only.
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
    """Footer: copyright left, download map link bottom-right."""
    return """
    .coffee-footer, .site-footer {
      margin-top: auto;
      width: 100%;
      padding: 1.75rem 1rem 1.25rem;
      box-sizing: border-box;
    }
    .site-footer-inner {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 0.65rem 1.25rem;
      width: 100%;
      max-width: 56rem;
      margin: 0 auto;
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
      flex: 1 1 auto;
    }
    .site-footer-map, #site-footer-downloads-map {
      font-size: 0.78rem;
      color: #7aa0c0;
      text-decoration: none;
      letter-spacing: 0.03em;
      margin: 0;
      text-align: right;
      flex: 0 0 auto;
      white-space: nowrap;
    }
    .site-footer-map:hover {
      color: #aed0ea;
      text-decoration: underline;
    }
    @media (max-width: 420px) {
      .site-footer-inner { flex-direction: column; align-items: stretch; }
      .site-footer-copyright { text-align: center; }
      .site-footer-map { text-align: center; white-space: normal; }
    }
"""


def render_site_copyright_footer_html() -> str:
    """Public footer: © Raskul (left) + download map link (right)."""
    text = site_copyright_text()
    safe = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    map_href = (
        downloads_map_footer_href()
        .replace("&", "&amp;")
        .replace('"', "&quot;")
    )
    map_label = (
        downloads_map_footer_label()
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"""
  <footer class="site-footer coffee-footer" id="{SITE_FOOTER_ID}" data-site-footer="1">
    <div class="site-footer-inner" id="site-footer-inner">
      <p class="site-footer-copyright" id="site-footer-copyright">{safe}</p>
      <a class="site-footer-map" id="{SITE_FOOTER_MAP_ID}"
         href="{map_href}" data-downloads-map-link="1">{map_label}</a>
    </div>
  </footer>
"""


def render_coffee_link_html() -> str:
    """Deprecated public tip footer — returns copyright + map link."""
    return render_site_copyright_footer_html()
