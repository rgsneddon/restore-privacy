"""Release download catalog + paid download UI (version 0.3.7).

Primary path: pay **£2.45** (GBP) via Stripe Checkout per package, then a
single-use download token. Free permanent GitHub ``href`` is not used on the
public buttons. After payment the status host **proxies** the installer
(authenticated GitHub API / local assets) so fulfilment works when the
restore-privacy repo is **private**. Buy Me a Coffee is tip/support only.

Current catalog packages: restore-privacy release **0.3.7**
(Windows setup needs no separate Python install; macOS Developer ID notarized;
iOS Team-signed sideload).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

try:
    from coffee_link import COFFEE_LINK_URL, coffee_tip_url
except ImportError:  # package import path (status_page as package)
    from status_page.coffee_link import COFFEE_LINK_URL, coffee_tip_url

RELEASE_VERSION = "0.3.7"
GITHUB_OWNER = "rgsneddon"
GITHUB_REPO = "restore-privacy"
RELEASE_TAG = "0.3.7"
RELEASE_PAGE_URL = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tag/{RELEASE_TAG}"
)
RELEASE_DOWNLOAD_BASE = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/{RELEASE_TAG}"
)


def product_client_version() -> str | None:
    """Monorepo product pin from ``client/VERSION`` when present (status-only deploys: None)."""
    try:
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "client" / "VERSION"
        if p.is_file():
            v = p.read_text(encoding="utf-8").strip()
            return v or None
    except OSError:
        return None
    return None


def current_catalog_version() -> str:
    """Single current catalog version for pay buttons and fulfilment.

    This is the **shipped** catalog pin (``RELEASE_VERSION``). When the monorepo
    ``client/VERSION`` is present it must match — use :func:`catalog_matches_product_pin`.
    """
    return RELEASE_VERSION


def catalog_matches_product_pin() -> bool:
    """True when catalog version matches client/VERSION (or client pin absent)."""
    pin = product_client_version()
    if pin is None:
        return True
    return pin == current_catalog_version()


REQUIRED_CATALOG_PLATFORMS: tuple[str, ...] = (
    "windows",
    "android",
    "macos",
    "ios",
    "linux",
)


def assure_current_catalog_packages() -> dict[str, object]:
    """Imperative check: paid downloads bind only the **current** per-device packages.

    Returns a dict::
        {
          "ok": bool,
          "catalog_version": str,
          "product_pin": str | None,
          "platforms": list[dict],  # from list_catalog_platform_packages()
          "errors": list[str],
        }

    Failures (ok=False) include: catalog pin ≠ client/VERSION, fewer/more than
    five device platforms, filename missing current version, or stale platform.
    Safe for every commit (no network, no SSH, no binary rebuild).
    """
    errors: list[str] = []
    catalog = current_catalog_version()
    pin = product_client_version()
    if pin is not None and pin != catalog:
        errors.append(
            f"catalog pin {catalog!r} does not match client/VERSION {pin!r} "
            f"— bump RELEASE_VERSION / RELEASE_TAG / filenames together"
        )
    pkgs = list_catalog_platform_packages()
    platforms = [p["platform"] for p in pkgs]
    if len(pkgs) != len(REQUIRED_CATALOG_PLATFORMS):
        errors.append(
            f"expected {len(REQUIRED_CATALOG_PLATFORMS)} device packages, got {len(pkgs)}"
        )
    for need in REQUIRED_CATALOG_PLATFORMS:
        if need not in platforms:
            errors.append(f"missing platform package: {need}")
    seen: set[str] = set()
    for p in pkgs:
        plat = p["platform"]
        fname = p["filename"]
        ver = p["version"]
        if plat in seen:
            errors.append(f"duplicate platform entry: {plat}")
        seen.add(plat)
        if ver != catalog:
            errors.append(f"platform {plat}: version {ver!r} != catalog {catalog!r}")
        if catalog not in fname:
            errors.append(
                f"platform {plat}: filename {fname!r} missing catalog version {catalog!r}"
            )
        if not fname.startswith(f"restore-privacy-client-{catalog}-"):
            errors.append(
                f"platform {plat}: filename {fname!r} is not current-catalog pattern"
            )
        if not is_current_catalog_filename(fname) and ver == RELEASE_VERSION:
            errors.append(f"platform {plat}: {fname!r} not in current RELEASE_ASSETS")
    # RELEASE_TAG must match catalog for bookkeeping URLs
    if RELEASE_TAG != catalog:
        errors.append(f"RELEASE_TAG {RELEASE_TAG!r} != catalog version {catalog!r}")
    return {
        "ok": not errors,
        "catalog_version": catalog,
        "product_pin": pin,
        "platforms": pkgs,
        "errors": errors,
    }


# Canonical public asset filenames (must match GitHub Release 0.3.7 assets).
WINDOWS_EXE_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-windows-x64-setup.exe"
ANDROID_APK_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-android.apk"
MACOS_ZIP_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-macos.zip"
IOS_ZIP_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-ios.zip"
LINUX_TGZ_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-linux-x64.tar.gz"

PRICE_LABEL = "£2.45"
# Homepage download price block (single shipped contract for public #downloads).
PACKAGE_IDENTITY = "per month subscription package — one device licence"
TRIAL_SUBSCRIPTION_SENTENCE = (
    "Your monthly subscription begins after your 7 day trial"
)
PAY_AND_KEYGEN_CLAUSE = (
    "pay on Stripe, then download starts automatically and keygen is emailed to you directly"
)
# Default tip identity; runtime public page uses coffee_tip_url() (env override).
BMC_TIP_URL = COFFEE_LINK_URL

# --- Public buy-button mode ---
# Default OFF (live Stripe Pay): platform controls open the operator Payment Link.
# Temporary "Coming soon" self-links: set CATALOG_BUY_BUTTONS_COMING_SOON = True, or
# set env RPT_CATALOG_BUY_COMING_SOON=1. Force live anytime with RPT_CATALOG_BUY_LIVE=1.
CATALOG_BUY_BUTTONS_COMING_SOON = False
COMING_SOON_PUBLIC_HREF = "https://restoreprivacy.online"


def catalog_buy_buttons_coming_soon() -> bool:
    """True when public platform controls are temporary coming-soon self-links.

    Live Stripe Pay buttons (default when constant is False):
      - ``CATALOG_BUY_BUTTONS_COMING_SOON = False`` in this module, **or**
      - ``RPT_CATALOG_BUY_LIVE=1`` / ``true`` / ``yes`` / ``on``, **or**
      - ``RPT_CATALOG_BUY_COMING_SOON=0`` / ``false`` / ``no`` / ``off``

    Force coming-soon even if the constant is False:
      - ``RPT_CATALOG_BUY_COMING_SOON=1`` / ``true`` / ``yes`` / ``on``
    """
    import os

    live = os.environ.get("RPT_CATALOG_BUY_LIVE", "").strip().lower()
    if live in ("1", "true", "yes", "on"):
        return False
    cs = os.environ.get("RPT_CATALOG_BUY_COMING_SOON", "").strip().lower()
    if cs in ("0", "false", "no", "off"):
        return False
    if cs in ("1", "true", "yes", "on"):
        return True
    return bool(CATALOG_BUY_BUTTONS_COMING_SOON)


@dataclass(frozen=True)
class DownloadAsset:
    platform: str
    label: str
    filename: str

    @property
    def url(self) -> str:
        """Canonical release asset URL (bookkeeping / authenticated fetch only).

        Public HTML must use :attr:`pay_path`, not this URL as a free href.
        """
        return f"{RELEASE_DOWNLOAD_BASE}/{self.filename}"

    @property
    def pay_path(self) -> str:
        """Paid entry: Stripe payment page with platform for post-pay fulfilment.

        Not a free GitHub href. Uses the operator Payment Link URL plus
        ``client_reference_id=<platform>`` so the webhook can mint a token for
        this package only.
        """
        from payments import stripe_payment_page_href_for_platform

        return stripe_payment_page_href_for_platform(self.platform)


RELEASE_ASSETS: tuple[DownloadAsset, ...] = (
    DownloadAsset(
        platform="windows",
        label="Windows (x64) - Installer (.exe)",
        filename=WINDOWS_EXE_FILENAME,
    ),
    DownloadAsset(
        platform="android",
        label="Android - APK installer",
        filename=ANDROID_APK_FILENAME,
    ),
    DownloadAsset(
        platform="macos",
        label="macOS - App package (.zip, Developer ID + notarized)",
        filename=MACOS_ZIP_FILENAME,
    ),
    DownloadAsset(
        platform="ios",
        label="iOS - App package (.zip, Team-signed sideload)",
        filename=IOS_ZIP_FILENAME,
    ),
    DownloadAsset(
        platform="linux",
        label="Linux (x64) - Installer (.tar.gz)",
        filename=LINUX_TGZ_FILENAME,
    ),
)

# Fixed platform order for operator staging / Iceland VPS host layout.
CATALOG_PLATFORMS: tuple[str, ...] = tuple(a.platform for a in RELEASE_ASSETS)


def is_current_catalog_filename(filename: str) -> bool:
    """True only for installers in the current catalog set (not stale tags)."""
    name = (filename or "").strip()
    if not name:
        return False
    return name in {a.filename for a in RELEASE_ASSETS}


def list_catalog_platform_packages(
    *, version: str | None = None
) -> list[dict[str, str]]:
    """Per-device product packages for the current (or given) catalog version.

    Returns one dict per platform with keys:
    ``version``, ``platform``, ``filename``, ``relative_path``
    (relative to a version root: ``{version}/{filename}``).
    """
    ver = (version or RELEASE_VERSION).strip()
    out: list[dict[str, str]] = []
    for a in RELEASE_ASSETS:
        # Rebuild filename if a different version is requested.
        if ver == RELEASE_VERSION:
            fname = a.filename
        else:
            # Canonical pattern: restore-privacy-client-{ver}-…
            suffix = a.filename.split(f"-{RELEASE_VERSION}-", 1)[-1]
            if suffix == a.filename:
                # fallback: replace version substring once
                fname = a.filename.replace(RELEASE_VERSION, ver, 1)
            else:
                fname = f"restore-privacy-client-{ver}-{suffix}"
        out.append(
            {
                "version": ver,
                "platform": a.platform,
                "filename": fname,
                "relative_path": f"{ver}/{fname}",
            }
        )
    return out


def available_downloads(
    include_android: bool = True,
    include_macos: bool = True,
    include_ios: bool = True,
    include_linux: bool = True,
    include_windows: bool = True,
) -> list[DownloadAsset]:
    """Return download assets advertised on the public VPN APP Shop."""
    out: list[DownloadAsset] = []
    for a in RELEASE_ASSETS:
        if a.platform == "android" and not include_android:
            continue
        if a.platform == "windows" and not include_windows:
            continue
        if a.platform == "macos" and not include_macos:
            continue
        if a.platform == "ios" and not include_ios:
            continue
        if a.platform == "linux" and not include_linux:
            continue
        out.append(a)
    return out


# Footer: catalog identity on the public status host (repo is private — no free GH).
# RELEASE_PAGE_URL remains for bookkeeping; public HTML must not send buyers to a
# 404 GitHub release page when the repository is private.
# Keep this string in sync with payments.DEFAULT_PRODUCTION_PUBLIC_BASE_URL
# (avoid importing payments here — circular with payments → downloads).
# Pre-RUST product line: restore-privacy Python RPT catalog (not RUST-IN-PRIVACY).
PRODUCT_CATALOG_URL = "https://restoreprivacy.online/#downloads"
PRODUCT_CATALOG_LABEL = (
    f"Catalog v{RELEASE_VERSION} — installers after £2.45 payment only (signed packages)"
)
# Back-compat aliases (historical RUST_REPO_* names; values are pre-RUST catalog).
RUST_REPO_URL = PRODUCT_CATALOG_URL
RUST_REPO_LABEL = PRODUCT_CATALOG_LABEL


# Compatibility aliases used by older tests (map to 0.3.7 installers).
WINDOWS_ZIP_FILENAME = WINDOWS_EXE_FILENAME


def download_css() -> str:
    """CSS for catalog pay section (RB-donate inspired navy/blue palette)."""
    return """
    .downloads { width: 100%; text-align: center; box-sizing: border-box; }
    .downloads h2 { font-size: 1.05rem; letter-spacing: 0.1em; font-weight: 700;
                    margin: 0 0 0.35rem; color: var(--rb-cream); text-transform: uppercase; }
    .dl-sub { color: var(--rb-muted); font-size: 0.92rem; margin: 0 0 0.85rem; }
    /* Nested price box inside #downloads: ~2/3 panel width, fluid on narrow viewports */
    .dl-price-box {
      width: 66.67%;
      max-width: 66.67%;
      margin: 0 auto 1.1rem;
      padding: 0.75rem 1rem;
      box-sizing: border-box;
      border: 1px solid var(--rb-card-border);
      border-radius: 12px;
      background: rgba(10, 22, 40, 0.45);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
    .dl-price {
      font-size: 0.95rem;
      margin: 0;
      font-weight: 600;
      color: var(--rb-accent);
      line-height: 1.45;
      text-align: center;
    }
    .dl-payment-disclaimer {
      max-width: 36rem; margin: 1.15rem auto 0.35rem; padding: 0.65rem 0.85rem;
      font-size: 0.82rem; line-height: 1.45; font-weight: 600;
      color: #fecaca; background: rgba(127, 29, 29, 0.35);
      border: 1px solid #b91c1c; border-radius: 12px; text-align: left;
    }
    .dl-buttons {
      display: flex; flex-direction: column; gap: 0.85rem; align-items: stretch; width: 100%;
    }
    .dl-row {
      display: flex; flex-direction: row; flex-wrap: wrap; gap: 0.75rem;
      justify-content: center; align-items: stretch; width: 100%;
    }
    .dl-row-3, .dl-row-2 { max-width: 100%; }
    a.dl, button.dl {
      display: inline-flex; flex-direction: column; align-items: center; justify-content: center;
      gap: 0.28rem;
      flex: 0 0 5.65rem; width: 5.65rem; height: 5.65rem;
      min-width: 5.65rem; max-width: 5.65rem; min-height: 5.65rem; max-height: 5.65rem;
      padding: 0.4rem 0.3rem;
      background: linear-gradient(180deg, var(--rb-btn) 0%, var(--rb-btn-deep) 100%);
      color: #fff; text-decoration: none; border-radius: 12px;
      font-weight: 700; font-size: 0.68rem; box-sizing: border-box;
      border: 1px solid rgba(255,255,255,0.18); cursor: pointer;
      font-family: inherit; text-align: center; line-height: 1.15;
      box-shadow: 0 3px 10px rgba(7, 30, 60, 0.32);
      transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease;
      aspect-ratio: 1 / 1;
    }
    a.dl .dl-platform, button.dl .dl-platform {
      font-size: 0.78rem; font-weight: 800; letter-spacing: 0.02em;
      line-height: 1.1; color: #fff;
    }
    a.dl .dl-buy, button.dl .dl-buy {
      font-size: 0.62rem; font-weight: 700; opacity: 0.92;
      letter-spacing: 0.01em;
    }
    a.dl:hover, button.dl:hover {
      filter: brightness(1.08);
      transform: translateY(-1px);
      box-shadow: 0 6px 18px rgba(7, 30, 60, 0.42);
    }
    a.dl:focus-visible, button.dl:focus-visible {
      outline: 2px solid var(--rb-accent); outline-offset: 3px;
    }
    a.dl#dl-windows, button.dl#dl-windows {
      background: linear-gradient(180deg, #2f8fd8 0%, #1a5f9e 100%);
    }
    a.dl#dl-android, button.dl#dl-android {
      background: linear-gradient(180deg, #2f9e6b 0%, #1b6b48 100%);
    }
    a.dl#dl-macos, button.dl#dl-macos {
      background: linear-gradient(180deg, #5b6b7c 0%, #3d4754 100%);
    }
    a.dl#dl-ios, button.dl#dl-ios {
      background: linear-gradient(180deg, #5b6fd6 0%, #3b4aa8 100%);
    }
    a.dl#dl-linux, button.dl#dl-linux {
      background: linear-gradient(180deg, #c9a227 0%, #8a6e12 100%);
      color: #0a1628;
    }
    a.dl.dl-coming-soon, button.dl.dl-coming-soon { opacity: 0.92; }
    a.dl.dl-coming-soon:hover, button.dl.dl-coming-soon:hover { opacity: 1; }
    .dl-footer { margin-top: 1.25rem; font-size: 0.9rem; line-height: 1.45; width: 100%; }
    .dl-footer a.catalog-link { color: var(--rb-link); text-decoration: underline; font-weight: 600; }
    .dl-footer a.catalog-link:hover { color: var(--rb-link-hover); }
    .dl-tip { margin-top: 1rem; font-size: 0.86rem; color: var(--rb-muted); width: 100%; text-align: center; }
    .dl-tip a { color: var(--rb-accent); text-decoration: underline; font-weight: 600; }
    .bmc-page-footer { margin-top: 0.5rem; margin-bottom: 0.25rem; padding: 0.75rem 0.5rem 1rem; }
    @media (max-width: 640px) {
      a.dl, button.dl {
        flex: 0 0 5.25rem; width: 5.25rem; height: 5.25rem;
        min-width: 5.25rem; max-width: 5.25rem;
      }
      /* Full width of downloads panel on narrow viewports */
      .dl-price-box {
        width: 100%;
        max-width: 100%;
        padding: 0.65rem 0.75rem;
      }
    }
"""


def payment_connect_disclaimer_html() -> str:
    """Red STRONG DISCLAIMER box for the public downloads section.

    Placed after platform pay controls and immediately above the BMC tip link.
    """
    return (
        '<p class="dl-payment-disclaimer" id="dl-payment-disclaimer">'
        "<strong>STRONG DISCLAIMER — PAYMENT REQUIRED FOR CONNECT:</strong> "
        "Access to Connect and residual VPN use requires "
        "<strong>successful payment</strong>. If payment "
        "<strong>fails at any time</strong> (failed checkout, failed charge, "
        "refund, dispute, revoked entitlement, or "
        "<strong>subscription cancellation</strong> / end of the paid "
        "subscription period), the ability to "
        "<strong>Connect with the Restore Privacy app is cancelled</strong> "
        "for that purchase/install until a successful payment is completed."
        "</p>"
    )


def render_bmc_tip_html() -> str:
    """Buy Me a Coffee tip block (tip/support only — not a paid download control).

    Homepage places this at the **very bottom** of the page shell (after downloads,
    node-wipe, and audit). Stable anchors: ``#bmc-tip`` / ``#bmc-tip-link``.
    """
    tip = coffee_tip_url()
    tip_label = tip.replace("https://", "").replace("http://", "")
    return (
        f'  <p class="dl-tip bmc-page-footer" id="bmc-tip">'
        f'Tip / support (not a paid download): '
        f'<a id="bmc-tip-link" href="{tip}" rel="noopener noreferrer" '
        f'target="_blank">{tip_label}</a></p>'
    )


def render_catalog_footer_html() -> str:
    """Under-download-buttons footer (intentionally empty on public homepage).

    BMC tip is **not** rendered here so it can sit at the page bottom via
    :func:`render_bmc_tip_html` in the homepage shell. How-to-buy / catalogue
    links remain omitted; Pay buttons are the only catalog entry.
    """
    return ""


# Back-compat: historical name still returns the tip fragment for callers/tests.
render_rust_footer_html = render_bmc_tip_html


def platform_face_title(platform: str) -> str:
    """Short device/platform title for pay-button face (sighted users)."""
    key = (platform or "").strip().lower()
    names = {
        "windows": "Windows",
        "android": "Android",
        "macos": "macOS",
        "ios": "iOS",
        "linux": "Linux",
    }
    return names.get(key, key.title() if key else "Device")


def _render_platform_pay_link(
    a: DownloadAsset,
    *,
    coming_soon: bool | None = None,
) -> str:
    """One platform control (stable id + data attrs for layout/tests).

    When *coming_soon* is true (default via :func:`catalog_buy_buttons_coming_soon`),
    the control is a temporary self-link to :data:`COMING_SOON_PUBLIC_HREF`.

    When *coming_soon* is false, live Stripe Payment Link path
    (``data-pay-via="stripe-payment-page"``).

    Face shows **platform title** + compact ``BUY - {version}`` on a small square tile.
    """
    if coming_soon is None:
        coming_soon = catalog_buy_buttons_coming_soon()
    platform_title = platform_face_title(a.platform)
    buy_line = f"BUY - {RELEASE_VERSION}"
    # Stacked face: platform name + buy line (visible, distinct per control)
    face = (
        f'<span class="dl-platform">{platform_title}</span>'
        f'<span class="dl-buy">{buy_line}</span>'
    )
    aria = f"{platform_title}: {buy_line} — {a.label}"
    if coming_soon:
        href = COMING_SOON_PUBLIC_HREF
        return (
            f'<a class="dl dl-coming-soon" id="dl-{a.platform}" href="{href}" '
            f'rel="noopener noreferrer" '
            f'data-platform="{a.platform}" data-filename="{a.filename}" '
            f'data-price-pence="245" data-pay-via="coming-soon" '
            f'data-coming-soon="1" aria-label="{aria}">'
            f"{face}</a>"
        )
    href = a.pay_path
    return (
        f'<a class="dl" id="dl-{a.platform}" href="{href}" '
        f'rel="noopener noreferrer" target="_blank" '
        f'data-platform="{a.platform}" data-filename="{a.filename}" '
        f'data-price-pence="245" data-pay-via="stripe-payment-page" '
        f'aria-label="{aria}">'
        f"{face}</a>"
    )


def download_menu_rows(
    assets: Iterable[DownloadAsset] | None = None,
) -> tuple[list[DownloadAsset], list[DownloadAsset]]:
    """Split catalog into two rows under the title: three, then two."""
    items = list(assets) if assets is not None else available_downloads()
    if len(items) <= 3:
        return items, []
    return items[:3], items[3:]


def render_download_section_html(
    assets: Iterable[DownloadAsset] | None = None,
    *,
    coming_soon: bool | None = None,
) -> str:
    """HTML: platform buy controls (live Stripe pay **or** temporary coming-soon).

    Platform menu below the download title is **two rows**: three items, then two.

    *coming_soon* defaults to :func:`catalog_buy_buttons_coming_soon`. Pass
    ``coming_soon=False`` (or env live switch) to restore Stripe Pay buttons.
    """
    items = list(assets) if assets is not None else available_downloads()
    if not items:
        return ""
    if coming_soon is None:
        coming_soon = catalog_buy_buttons_coming_soon()

    if not coming_soon:
        from payments import stripe_payment_page_url

        # Keep pay pipeline imported/ready; buttons use per-platform pay_path.
        _ = stripe_payment_page_url()

    row1, row2 = download_menu_rows(items)
    row1_html = "\n      ".join(
        _render_platform_pay_link(a, coming_soon=coming_soon) for a in row1
    )
    row2_block = ""
    if row2:
        row2_html = "\n      ".join(
            _render_platform_pay_link(a, coming_soon=coming_soon) for a in row2
        )
        row2_block = f"""
    <div class="dl-row dl-row-2" id="dl-row-2" data-dl-row="2" data-dl-count="{len(row2)}">
      {row2_html}
    </div>"""
    # Price identity: £2.45 package + one device licence, trial honesty, pay + keygen email.
    if coming_soon:
        price_line = (
            f"{PRICE_LABEL} GBP {PACKAGE_IDENTITY} — {TRIAL_SUBSCRIPTION_SENTENCE} — "
            f"buy buttons coming soon (links return to restoreprivacy.online)"
        )
        buttons_mode = ' data-buy-mode="coming-soon"'
    else:
        price_line = (
            f"{PRICE_LABEL} GBP {PACKAGE_IDENTITY} — {TRIAL_SUBSCRIPTION_SENTENCE} — "
            f"{PAY_AND_KEYGEN_CLAUSE}"
        )
        buttons_mode = ' data-buy-mode="stripe-live"'
    # Order: title/price box → pay controls only. BMC tip is page-bottom (homepage shell).
    # Homepage omits STRONG DISCLAIMER banner (apps/licence retain payment language).
    return f"""
  <section class="downloads panel-card" id="downloads" aria-label="Download Restore Privacy client">
    <h2>Download client v{RELEASE_VERSION}</h2>
    <p class="dl-sub">Windows | Linux | macOS | iOS | Android</p>
    <div class="dl-price-box" id="dl-price-box">
      <p class="dl-price" id="dl-price">{price_line}</p>
    </div>
    <div class="dl-buttons" id="dl-buttons" data-dl-layout="3+2"{buttons_mode}>
    <div class="dl-row dl-row-3" id="dl-row-1" data-dl-row="1" data-dl-count="{len(row1)}">
      {row1_html}
    </div>{row2_block}
    </div>
  </section>
"""
