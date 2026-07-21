"""Discrete Buy Me a Coffee footer for the public status page."""

from __future__ import annotations

import os

COFFEE_LINK_TEXT = "buy rus a coffee"
COFFEE_LINK_URL = "https://buymeacoffee.com/rgsneddon"


def coffee_tip_url() -> str:
    """Public tip URL (env RPT_BMC_TIP_URL overrides default product page)."""
    return os.environ.get("RPT_BMC_TIP_URL", "").strip() or COFFEE_LINK_URL


def coffee_tip_label() -> str:
    """Footer link text (env RPT_BMC_TIP_LABEL overrides default)."""
    return os.environ.get("RPT_BMC_TIP_LABEL", "").strip() or COFFEE_LINK_TEXT


def coffee_link_css() -> str:
    """Bottom-centre, muted/discrete footer styling."""
    return """
    .coffee-footer {
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
"""


def render_coffee_link_html() -> str:
    """Footer fragment: tip URL + label, bottom-centre placement."""
    url = coffee_tip_url()
    label = coffee_tip_label()
    # Minimal attribute escape
    safe_url = (
        url.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
    )
    safe_label = (
        label.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"""
  <footer class="coffee-footer" id="coffee-footer">
    <a class="coffee-link"
       href="{safe_url}"
       target="_blank"
       rel="noopener noreferrer">{safe_label}</a>
  </footer>
"""
