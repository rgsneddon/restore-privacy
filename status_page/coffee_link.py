"""Discrete Buy Me a Coffee footer for the public status page."""

from __future__ import annotations

COFFEE_LINK_TEXT = "buy rus a coffee"
COFFEE_LINK_URL = "https://buymeacoffee.com/rgsneddon"


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
    """Footer fragment: exact link text and URL, bottom-centre placement."""
    return f"""
  <footer class="coffee-footer" id="coffee-footer">
    <a class="coffee-link"
       href="{COFFEE_LINK_URL}"
       target="_blank"
       rel="noopener noreferrer">{COFFEE_LINK_TEXT}</a>
  </footer>
"""
