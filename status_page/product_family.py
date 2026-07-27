"""Public product-family landings: Browser and Vault (style only, not VPN structure).

VPN homepage remains :func:`app.render_html`. These builders share public chrome
CSS/theme via :mod:`public_chrome` but intentionally omit download shop, audit
countdown, node wipe timer, and settings banner.
"""

from __future__ import annotations

from typing import Any


def _import_chrome():
    try:
        from public_chrome import (
            PRODUCT_BROWSER_KEY,
            PRODUCT_BROWSER_PATH,
            PRODUCT_BROWSER_TITLE,
            PRODUCT_VAULT_KEY,
            PRODUCT_VAULT_PATH,
            PRODUCT_VAULT_TITLE,
            PRODUCT_VPN_KEY,
            PRODUCT_VPN_PATH,
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            PRODUCT_BROWSER_KEY,
            PRODUCT_BROWSER_PATH,
            PRODUCT_BROWSER_TITLE,
            PRODUCT_VAULT_KEY,
            PRODUCT_VAULT_PATH,
            PRODUCT_VAULT_TITLE,
            PRODUCT_VPN_KEY,
            PRODUCT_VPN_PATH,
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    return {
        "PRODUCT_BROWSER_KEY": PRODUCT_BROWSER_KEY,
        "PRODUCT_BROWSER_PATH": PRODUCT_BROWSER_PATH,
        "PRODUCT_BROWSER_TITLE": PRODUCT_BROWSER_TITLE,
        "PRODUCT_VAULT_KEY": PRODUCT_VAULT_KEY,
        "PRODUCT_VAULT_PATH": PRODUCT_VAULT_PATH,
        "PRODUCT_VAULT_TITLE": PRODUCT_VAULT_TITLE,
        "PRODUCT_VPN_KEY": PRODUCT_VPN_KEY,
        "PRODUCT_VPN_PATH": PRODUCT_VPN_PATH,
        "public_brand_header_html": public_brand_header_html,
        "public_head_open": public_head_open,
        "public_page_close": public_page_close,
    }


# Exact three-line body copy (criterion 3)
BROWSER_LINE_1 = "RESTORE PRIVACY BROWSER"
BROWSER_LINE_2 = "ETA for Restore Privacy Browser"
BROWSER_LINE_3 = "scheduled for Q3 2026"

VAULT_LINE_1 = "RESTORE PRIVACY VAULT"
VAULT_LINE_2 = "Restore Privacy Vault"
VAULT_LINE_3 = "scheduled for Q3 2027"


def product_coming_body_html(
    *,
    line1: str,
    line2: str,
    line3: str,
    section_id: str,
) -> str:
    """Single content card: three-line brand title (no VPN shop/countdown structure)."""
    return f"""    <section class="panel-card product-coming-card" id="{section_id}"
             data-product-coming="1" aria-labelledby="{section_id}-title">
      <h1 class="product-coming-title" id="{section_id}-title">{line1}</h1>
      <p class="product-coming-line" id="{section_id}-eta">{line2}</p>
      <p class="product-coming-schedule" id="{section_id}-schedule">{line3}</p>
    </section>
"""


def render_browser_page_html() -> bytes:
    """Public Browser landing — style chrome only; schedule Q3 2026."""
    c = _import_chrome()
    header = c["public_brand_header_html"](
        title=c["PRODUCT_BROWSER_TITLE"],
        active=None,
        product_active=c["PRODUCT_BROWSER_KEY"],
        include_site_nav=False,
    )
    body = product_coming_body_html(
        line1=BROWSER_LINE_1,
        line2=BROWSER_LINE_2,
        line3=BROWSER_LINE_3,
        section_id="product-browser-body",
    )
    page = f"""{c["public_head_open"](title=c["PRODUCT_BROWSER_TITLE"])}
  <div class="page-shell" id="page-shell" data-product="browser">
{header}
{body}
  </div>
{c["public_page_close"]()}
"""
    return page.encode("utf-8")


def render_vault_page_html() -> bytes:
    """Public Vault landing — style chrome only; schedule Q3 2027."""
    c = _import_chrome()
    header = c["public_brand_header_html"](
        title=c["PRODUCT_VAULT_TITLE"],
        active=None,
        product_active=c["PRODUCT_VAULT_KEY"],
        include_site_nav=False,
    )
    body = product_coming_body_html(
        line1=VAULT_LINE_1,
        line2=VAULT_LINE_2,
        line3=VAULT_LINE_3,
        section_id="product-vault-body",
    )
    page = f"""{c["public_head_open"](title=c["PRODUCT_VAULT_TITLE"])}
  <div class="page-shell" id="page-shell" data-product="vault">
{header}
{body}
  </div>
{c["public_page_close"]()}
"""
    return page.encode("utf-8")


def product_key_from_host(host: str) -> str | None:
    """Map Host header to product key for optional subdomain routing.

    Returns ``browser`` / ``vault`` when the left-most label is that product;
    ``None`` for apex / www / unknown (caller keeps path-based dispatch).
    """
    h = (host or "").strip().lower()
    if not h:
        return None
    # strip port
    if ":" in h:
        h = h.split(":", 1)[0]
    label = h.split(".", 1)[0]
    if label == "browser":
        return "browser"
    if label == "vault":
        return "vault"
    return None


def product_paths() -> dict[str, str]:
    c = _import_chrome()
    return {
        c["PRODUCT_VPN_KEY"]: c["PRODUCT_VPN_PATH"],
        c["PRODUCT_BROWSER_KEY"]: c["PRODUCT_BROWSER_PATH"],
        c["PRODUCT_VAULT_KEY"]: c["PRODUCT_VAULT_PATH"],
    }
