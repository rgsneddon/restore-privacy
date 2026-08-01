"""Public Service page — commercial own-company branded Suite licence (£3000/node).

Main-nav destination ``/service``. Layout mirrors homepage: intro
“Privacy you can actually use”, then dual half-width boxes. Left box is the
commercial offer + one-time Stripe £3000 checkout. Right box is a light
companion (individual free Suite / KEYGEN path) — not the £3000 offer.
"""

from __future__ import annotations

from downloads import STRIPE_CHECKOUT_BRANDING_NOTE
from payments import (
    COMMERCIAL_SUITE_CHECKOUT_PATH,
    COMMERCIAL_SUITE_NODE_PRICE_LABEL,
    COMMERCIAL_SUITE_NODE_PRICE_PENCE,
    COMMERCIAL_SUITE_PRODUCT_KEY,
    COMMERCIAL_SUITE_PRODUCT_LINE,
    PRICE_LABEL,
)

# Re-export path constants for app/tests (aligned with public_chrome.SERVICE_PATH)
SERVICE_PATH = "/service"
SERVICE_PAGE_ID = "service-page"
SERVICE_SHOP_ROW_ID = "service-shop-row"
SERVICE_COMMERCIAL_BOX_ID = "service-commercial-box"
SERVICE_COMPANION_BOX_ID = "service-companion-box"
SERVICE_PAY_FORM_ID = "commercial-suite-pay-form"
SERVICE_PAY_BUTTON_ID = "commercial-suite-pay-btn"
SERVICE_INTRO_ID = "service-home-intro"

SERVICE_INTRO_HEADING = "Privacy you can actually use"

SERVICE_COMMERCIAL_TITLE = "Full business package — commercial node"
SERVICE_COMMERCIAL_SUBTITLE = (
    f"{COMMERCIAL_SUITE_NODE_PRICE_LABEL} deposit to begin the work · one-time"
)

# Commercial offer body — deposit framing first; business package substance.
SERVICE_COMMERCIAL_BODY = (
    f"Prices start with a <strong>{COMMERCIAL_SUITE_NODE_PRICE_LABEL} deposit</strong> "
    "to do the work — that payment is a <strong>deposit</strong>, not the finished "
    "all-in price. <em>Costs may be higher</em> once on-site network tasks, hardware, "
    "and scope are agreed; anything beyond the deposit is confirmed before further "
    "work. Run a residual node on your own server or arrange a dedicated host through "
    "<strong>Raskul</strong>. Includes mainframe establishment and deploy of "
    "<strong>Restore Privacy Operating System</strong> (rpOS) and matching Suite "
    "parts, customised accounting and branding SDK, internal VPN for office / WFH "
    "staff, audit scripts, and optional Evolve + rewards token. "
    "User-friendly interface and everyday business apps. "
    f"<strong>{COMMERCIAL_SUITE_NODE_PRICE_LABEL}</strong> deposit · one-time via Stripe."
)

SERVICE_COMMERCIAL_PAY_LABEL = (
    f"Pay {COMMERCIAL_SUITE_NODE_PRICE_LABEL} deposit — begin the work (one-time)"
)
SERVICE_COMMERCIAL_DEPOSIT_NOTE = (
    f"The {COMMERCIAL_SUITE_NODE_PRICE_LABEL} is a deposit to begin commercial node "
    "work, not a guarantee of final total cost."
)

SERVICE_COMPANION_TITLE = "Individuals & residual Connect"
SERVICE_COMPANION_BODY = (
    f"Need the free Suite installer and a monthly KEYGEN ({PRICE_LABEL}/month) "
    "for personal residual Connect? That path stays on the homepage — not this "
    "commercial node licence."
)


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def service_page_css() -> str:
    """Homepage-matching dual half boxes + commercial pay styling."""
    return f"""
    .service-page {{
      width: 100%; box-sizing: border-box;
    }}
    .service-home-intro {{
      text-align: center; margin: 0 0 1.15rem; padding: 1.25rem 1.15rem 1.15rem;
    }}
    .service-home-intro h2 {{
      margin: 0 0 0.65rem; font-size: clamp(1.25rem, 3.2vw, 1.65rem);
      letter-spacing: 0.04em; color: var(--rb-cream, #fff); font-weight: 800;
    }}
    .service-home-lead {{
      margin: 0 auto; max-width: 40rem; line-height: 1.55;
      font-size: clamp(0.95rem, 2.2vw, 1.05rem); color: var(--rb-soft, #aed0ea);
      font-weight: 500;
    }}
    /* Same dual half-width pattern as homepage .home-shop-row */
    .service-shop-row, #{SERVICE_SHOP_ROW_ID} {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: clamp(0.75rem, 2vw, 1.15rem);
      width: 100%;
      align-items: stretch;
      box-sizing: border-box;
      margin: 0 0 clamp(0.95rem, 2.2vw, 1.35rem);
    }}
    .service-shop-row > .panel-card,
    .service-shop-row > section {{
      width: 100%; max-width: 100%; min-width: 0; margin: 0;
      box-sizing: border-box; height: 100%;
    }}
    @media (max-width: 820px) {{
      .service-shop-row, #{SERVICE_SHOP_ROW_ID} {{
        grid-template-columns: 1fr;
      }}
    }}
    .service-commercial-box h2,
    .service-companion-box h2 {{
      margin: 0 0 0.45rem; font-size: clamp(1.05rem, 2.6vw, 1.3rem);
      color: var(--rb-cream, #fff); font-weight: 800; letter-spacing: 0.03em;
    }}
    .service-commercial-sub {{
      margin: 0 0 0.85rem; font-size: 0.88rem; font-weight: 700;
      color: var(--rb-accent-sky, #7dd3fc); letter-spacing: 0.02em;
    }}
    .service-commercial-body,
    .service-companion-body {{
      margin: 0 0 1rem; font-size: 0.92rem; line-height: 1.55;
      color: var(--rb-soft, #aed0ea); font-weight: 500;
    }}
    .service-price-tag {{
      display: inline-block; margin: 0 0 0.85rem; padding: 0.35rem 0.75rem;
      border-radius: 10px; font-weight: 800; font-size: 1.05rem;
      color: #0a1628; background: linear-gradient(180deg, #fde68a, #f59e0b);
      letter-spacing: 0.04em;
    }}
    .service-commercial-pay-form {{
      margin: 0.5rem 0 0; display: flex; flex-direction: column; gap: 0.55rem;
      align-items: stretch;
    }}
    button.service-commercial-pay-btn,
    #{SERVICE_PAY_BUTTON_ID} {{
      display: inline-block; width: 100%; max-width: 100%;
      margin: 0; padding: 0.85rem 1rem; border: 0; border-radius: 12px;
      cursor: pointer; font: 800 0.95rem/1.25 system-ui, sans-serif;
      letter-spacing: 0.04em; text-transform: none;
      color: #041018;
      background: linear-gradient(180deg, #86efac, #22c55e 55%, #16a34a);
      box-shadow: 0 8px 22px rgba(22, 163, 74, 0.35),
                  0 1px 0 rgba(255,255,255,0.25) inset;
    }}
    button.service-commercial-pay-btn:hover {{
      filter: brightness(1.05);
    }}
    button.service-commercial-pay-btn:active {{
      transform: translateY(1px);
    }}
    .service-stripe-note {{
      margin: 0; font-size: 0.78rem; color: var(--rb-muted, #8eb4d0); line-height: 1.4;
    }}
    .service-pay-error {{
      margin: 0 0 0.75rem; padding: 0.55rem 0.75rem; border-radius: 10px;
      background: rgba(127, 29, 29, 0.45); border: 1px solid rgba(248, 113, 113, 0.55);
      color: #fecaca; font-weight: 600; font-size: 0.9rem;
    }}
    .service-pay-ok {{
      margin: 0 0 0.75rem; padding: 0.55rem 0.75rem; border-radius: 10px;
      background: rgba(6, 78, 59, 0.45); border: 1px solid rgba(52, 211, 153, 0.5);
      color: #a7f3d0; font-weight: 600; font-size: 0.9rem;
    }}
    .service-companion-links {{
      display: flex; flex-wrap: wrap; gap: 0.55rem; margin-top: 0.5rem;
    }}
    .service-companion-links a {{
      display: inline-block; padding: 0.45rem 0.75rem; border-radius: 10px;
      font-weight: 700; font-size: 0.88rem; text-decoration: none;
      color: #0a1628; background: #7dd3fc;
    }}
"""


def render_service_intro_html() -> str:
    """Same homepage intro heading; service-scoped body."""
    return f"""  <section class="panel-card service-home-intro" id="{SERVICE_INTRO_ID}"
           aria-labelledby="service-home-intro-title" data-product="suite"
           data-service-intro="1">
    <h2 id="service-home-intro-title">{SERVICE_INTRO_HEADING}</h2>
    <p class="service-home-lead" id="service-home-lead">
      Commercial own-company branding and full community governance Suite for
      businesses that run their own dedicated residual node — not the monthly
      personal KEYGEN path.
    </p>
  </section>
"""


def render_service_commercial_box_html(*, pay_error: str = "") -> str:
    """Left half: commercial Suite offer + one-time £3000 Stripe pay control."""
    err = (pay_error or "").strip()
    err_html = ""
    if err and err.lower() not in ("1", "true", "cancelled"):
        err_html = (
            f'<p class="service-pay-error" id="service-pay-error" role="alert">'
            f"{_esc(err)}</p>"
        )
    elif err.lower() == "cancelled":
        err_html = (
            '<p class="service-pay-error" id="service-pay-error" role="alert">'
            "Checkout was cancelled. You can try again when ready.</p>"
        )
    return f"""
  <section class="panel-card service-commercial-box" id="{SERVICE_COMMERCIAL_BOX_ID}"
           data-service-commercial="1" data-product="{_esc(COMMERCIAL_SUITE_PRODUCT_KEY)}"
           data-product-line="{_esc(COMMERCIAL_SUITE_PRODUCT_LINE)}"
           data-price-pence="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}"
           data-billing="one_time" data-currency="gbp"
           aria-label="Commercial Suite licence">
    <h2 id="service-commercial-title">{SERVICE_COMMERCIAL_TITLE}</h2>
    <p class="service-commercial-sub" id="service-commercial-sub">
      {SERVICE_COMMERCIAL_SUBTITLE}
    </p>
    {err_html}
    <p class="service-commercial-body" id="service-commercial-body">
      {SERVICE_COMMERCIAL_BODY}
    </p>
    <span class="service-price-tag" id="service-price-tag"
          data-price-pence="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}"
          data-deposit="1">
      {COMMERCIAL_SUITE_NODE_PRICE_LABEL} deposit · one-time
    </span>
    <p class="service-commercial-body" id="service-commercial-deposit-note"
       data-deposit="1" style="margin-top:0;font-size:0.85rem;color:#fde68a">
      {SERVICE_COMMERCIAL_DEPOSIT_NOTE}
    </p>
    <form class="service-commercial-pay-form" id="{SERVICE_PAY_FORM_ID}"
          method="post" action="{COMMERCIAL_SUITE_CHECKOUT_PATH}"
          data-pay-via="commercial-suite" data-billing="one_time"
          data-product="{_esc(COMMERCIAL_SUITE_PRODUCT_KEY)}"
          data-price-pence="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}"
          data-commercial-deposit="1">
      <input type="hidden" name="product" value="{_esc(COMMERCIAL_SUITE_PRODUCT_KEY)}"/>
      <input type="hidden" name="product_line" value="{_esc(COMMERCIAL_SUITE_PRODUCT_LINE)}"/>
      <input type="hidden" name="billing" value="one_time"/>
      <input type="hidden" name="amount_pence" value="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}"/>
      <button type="submit" class="service-commercial-pay-btn"
              id="{SERVICE_PAY_BUTTON_ID}"
              data-commercial-pay="1"
              data-commercial-deposit="1"
              data-price-pence="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}">
        {SERVICE_COMMERCIAL_PAY_LABEL}
      </button>
      <p class="service-stripe-note" id="service-stripe-note">
        {STRIPE_CHECKOUT_BRANDING_NOTE}
        One-time <strong>deposit</strong> of {COMMERCIAL_SUITE_NODE_PRICE_LABEL} GBP
        via Stripe Checkout — begins the work; not a monthly KEYGEN subscription
        and not a final all-in quote.
      </p>
    </form>
  </section>
"""


SERVICE_RX_BOX_ID = "service-rx-browser-box"
SERVICE_RX_LINK_ID = "service-link-rx-browser"


def render_service_rx_browser_box_html(*, user_agent: str = "") -> str:
    """Rx Privacy Browser package link — device/UA-aware when UA is known."""
    try:
        from downloads import (
            RELEASE_VERSION,
            detect_platform_from_user_agent,
            rx_browser_download_label,
            rx_browser_package_filename,
            rx_browser_package_href,
        )
    except ImportError:  # pragma: no cover
        from status_page.downloads import (  # type: ignore
            RELEASE_VERSION,
            detect_platform_from_user_agent,
            rx_browser_download_label,
            rx_browser_package_filename,
            rx_browser_package_href,
        )
    href = rx_browser_package_href(user_agent=user_agent)
    label = rx_browser_download_label(user_agent)
    plat = detect_platform_from_user_agent(user_agent) or "unknown"
    # Keep download= / data-package in lockstep with UA-aware href (not generic zip).
    fname = rx_browser_package_filename(
        platform=plat if plat != "unknown" else None
    )
    return f"""
  <section class="panel-card service-rx-browser-box" id="{SERVICE_RX_BOX_ID}"
           data-service-rx="1" data-product="rx-browser"
           data-detected-platform="{_esc(plat)}"
           aria-label="Rx Privacy Browser">
    <h2 id="service-rx-title">Rx Privacy Browser</h2>
    <p class="service-companion-body" id="service-rx-body">
      Suite <strong>{_esc(RELEASE_VERSION)}</strong> includes the <strong>Rx</strong>
      Chromium MV3 companion — browser-scoped Connect/Disconnect (IPv4 basic path).
      Not OS residual TUN. Load unpacked or install the zip in Chromium-class browsers.
    </p>
    <div class="service-companion-links" id="service-rx-links">
      <a href="{_esc(href)}" id="{SERVICE_RX_LINK_ID}"
         data-rx-browser-download="1"
         data-package="{_esc(fname)}"
         data-detected-platform="{_esc(plat)}"
         download="{_esc(fname)}">{_esc(label)}</a>
    </div>
  </section>
"""


def render_service_companion_box_html(*, user_agent: str = "") -> str:
    """Right half layout companion — free Suite / KEYGEN / Rx path pointer."""
    try:
        from downloads import rx_browser_package_href
    except ImportError:  # pragma: no cover
        from status_page.downloads import rx_browser_package_href  # type: ignore
    rx_href = rx_browser_package_href(user_agent=user_agent)
    return f"""
  <section class="panel-card service-companion-box" id="{SERVICE_COMPANION_BOX_ID}"
           data-service-companion="1" aria-label="Individual Suite path">
    <h2 id="service-companion-title">{SERVICE_COMPANION_TITLE}</h2>
    <p class="service-companion-body" id="service-companion-body">
      {SERVICE_COMPANION_BODY}
    </p>
    <div class="service-companion-links" id="service-companion-links">
      <a href="/#suite-storefront" id="service-link-free-suite">Free Suite download</a>
      <a href="/#suite-keygen-form" id="service-link-keygen">Monthly KEYGEN</a>
      <a href="{_esc(rx_href)}" id="service-link-rx-browser-inline"
         data-rx-browser-download="1">Rx Privacy Browser package</a>
      <a href="/NODE_OPERATOR.md" id="service-link-node-op">Node operator docs</a>
    </div>
  </section>
"""


def render_service_shop_row_html(
    *, pay_error: str = "", user_agent: str = ""
) -> str:
    """Dual half-width row matching homepage home-shop-row structure."""
    left = render_service_commercial_box_html(pay_error=pay_error)
    right = render_service_companion_box_html(user_agent=user_agent)
    return f"""
    <div class="service-shop-row home-shop-row" id="{SERVICE_SHOP_ROW_ID}"
         data-home-shop-row="1" data-service-shop-row="1"
         data-layout="two-halves" aria-label="Commercial Suite and companion">
{left}
{right}
    </div>
"""


def render_service_page_html(
    *,
    pay_error: str = "",
    paid: bool = False,
    user_agent: str = "",
) -> bytes:
    """Full public Service page HTML (status host)."""
    try:
        from public_chrome import (
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    try:
        from downloads import render_bmc_tip_html
    except ImportError:  # pragma: no cover
        from status_page.downloads import render_bmc_tip_html  # type: ignore

    ok_html = ""
    if paid:
        ok_html = (
            '<p class="service-pay-ok" id="service-pay-ok" role="status">'
            "Payment started successfully. Complete Stripe Checkout if you have "
            "not already — our team will follow up on commercial onboarding for "
            f"your {COMMERCIAL_SUITE_NODE_PRICE_LABEL} node licence."
            "</p>"
        )

    extra = service_page_css()
    header = public_brand_header_html(active="service", product_active="vpn")
    intro = render_service_intro_html()
    shop = render_service_shop_row_html(pay_error=pay_error, user_agent=user_agent)
    rx_box = render_service_rx_browser_box_html(user_agent=user_agent)
    # Inject success banner into left box top when paid
    if ok_html:
        shop = shop.replace(
            f'id="{SERVICE_COMMERCIAL_BOX_ID}"',
            f'id="{SERVICE_COMMERCIAL_BOX_ID}"',
            1,
        )
        # Place after commercial title block
        shop = shop.replace(
            f'<p class="service-commercial-sub" id="service-commercial-sub">',
            f"{ok_html}\n    <p class=\"service-commercial-sub\" id=\"service-commercial-sub\">",
            1,
        )

    body = f"""{public_head_open(title=f"Service — {PUBLIC_BRAND_TITLE}", extra_css=extra)}
  <div class="page-shell" id="page-shell" data-page="service" data-product="suite"
       data-chrome="pro" data-service-page="1">
{header}
    <main class="service-page" id="{SERVICE_PAGE_ID}" data-service-page="1"
          aria-label="Commercial Suite service">
{intro}
{shop}
{rx_box}
    </main>
{render_bmc_tip_html()}
  </div>
{public_page_close()}
"""
    return body.encode("utf-8")
