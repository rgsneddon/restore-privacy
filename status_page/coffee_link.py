"""Public site footer + optional BMC tip helpers (admin/env only).

Public page bottom bar is the Raskul copyright — not Buy Me a Coffee.
BMC tip URL/label remain for admin inventory / optional env overrides only.
"""

from __future__ import annotations

import os

# Public footer (homepage and other public shells that use render_bmc_tip_html).
SITE_COPYRIGHT_TEXT = "(c) Raskul - all rights reserved"
SITE_FOOTER_ID = "site-footer"

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
    """Customer-facing public footer copyright line."""
    return os.environ.get("RPT_SITE_COPYRIGHT", "").strip() or SITE_COPYRIGHT_TEXT


def coffee_link_css() -> str:
    """Bottom-centre footer styling (copyright or legacy tip)."""
    return """
    .coffee-footer, .site-footer {
      margin-top: auto;
      width: 100%;
      padding: 1.75rem 1rem 1.25rem;
      text-align: center;
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
    .site-footer-copyright, #site-footer {
      font-size: 0.8rem;
      color: #64748b;
      letter-spacing: 0.02em;
      margin: 0;
    }
"""


def render_site_copyright_footer_html() -> str:
    """Public footer: ``(c) Raskul - all rights reserved`` (no BMC link)."""
    text = site_copyright_text()
    safe = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f"""
  <footer class="site-footer coffee-footer" id="{SITE_FOOTER_ID}" data-site-footer="1">
    <p class="site-footer-copyright" id="site-footer-copyright">{safe}</p>
  </footer>
"""


def render_coffee_link_html() -> str:
    """Deprecated public tip footer — returns copyright (BMC no longer public footer)."""
    return render_site_copyright_footer_html()
