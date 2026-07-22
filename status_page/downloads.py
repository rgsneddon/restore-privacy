"""Release download catalog + paid download UI (version 0.3.6).

Primary path: pay **£2.45** (GBP) via Stripe Checkout per package, then a
single-use download token. Free permanent GitHub ``href`` is not used on the
public buttons. After payment the status host **proxies** the installer
(authenticated GitHub API / local assets) so fulfilment works when the
restore-privacy repo is **private**. Buy Me a Coffee is tip/support only.

Current catalog packages: restore-privacy release **0.3.6**
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

RELEASE_VERSION = "0.3.6"
GITHUB_OWNER = "rgsneddon"
GITHUB_REPO = "restore-privacy"
RELEASE_TAG = "0.3.6"
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


# Canonical public asset filenames (must match GitHub Release 0.3.6 assets).
WINDOWS_EXE_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-windows-x64-setup.exe"
ANDROID_APK_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-android.apk"
MACOS_ZIP_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-macos.zip"
IOS_ZIP_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-ios.zip"
LINUX_TGZ_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-linux-x64.tar.gz"

PRICE_LABEL = "£2.45"
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


# Compatibility aliases used by older tests (map to 0.3.6 installers).
WINDOWS_ZIP_FILENAME = WINDOWS_EXE_FILENAME


def download_css() -> str:
    """CSS for catalog pay section (RB-donate inspired navy/blue palette)."""
    return """
    .downloads { width: 100%; text-align: center; box-sizing: border-box; }
    .downloads h2 { font-size: 1.05rem; letter-spacing: 0.1em; font-weight: 700;
                    margin: 0 0 0.35rem; color: var(--rb-cream); text-transform: uppercase; }
    .dl-sub { color: var(--rb-muted); font-size: 0.92rem; margin: 0 0 0.85rem; }
    .dl-price { font-size: 0.95rem; margin: 0 0 1.1rem; font-weight: 600; color: var(--rb-accent); }
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
      display: inline-flex; align-items: center; justify-content: center;
      flex: 1 1 9.5rem; min-width: 8.5rem; max-width: 18rem;
      padding: 0.95rem 1rem;
      background: linear-gradient(180deg, var(--rb-btn) 0%, var(--rb-btn-deep) 100%);
      color: #fff; text-decoration: none; border-radius: 14px;
      font-weight: 700; font-size: 0.88rem; box-sizing: border-box;
      border: 1px solid rgba(255,255,255,0.18); cursor: pointer;
      font-family: inherit; text-align: center; line-height: 1.3;
      box-shadow: 0 4px 14px rgba(7, 30, 60, 0.35);
      transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease;
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
    .dl-tip { margin-top: 1rem; font-size: 0.86rem; color: var(--rb-muted); width: 100%; }
    .dl-tip a { color: var(--rb-accent); text-decoration: underline; font-weight: 600; }
    @media (max-width: 640px) {
      a.dl, button.dl { flex: 1 1 100%; max-width: 100%; }
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


def render_catalog_footer_html() -> str:
    """Footer under download buttons — optional tip only (no How-to-buy link).

    The old “Catalog v… — installers after £2.45…” / FULL CATALOGUE footer link
    is intentionally **not** emitted on the public page.
    Platform Pay buttons remain the only catalog entry; no separate catalogue link.
    """
    tip = coffee_tip_url()
    tip_label = tip.replace("https://", "").replace("http://", "")
    return (
        f'    <p class="dl-tip" id="bmc-tip">'
        f'Tip / support (not a paid download): '
        f'<a id="bmc-tip-link" href="{tip}" rel="noopener noreferrer" '
        f'target="_blank">{tip_label}</a></p>'
    )


# Back-compat alias (historical name from RUST residual era).
render_rust_footer_html = render_catalog_footer_html


def _render_platform_pay_link(
    a: DownloadAsset,
    *,
    coming_soon: bool | None = None,
) -> str:
    """One platform control (stable id + data attrs for layout/tests).

    When *coming_soon* is true (default via :func:`catalog_buy_buttons_coming_soon`),
    the control is a **Coming soon** label with a redundant href to
    :data:`COMING_SOON_PUBLIC_HREF` (https://restoreprivacy.online) — not Stripe.

    When *coming_soon* is false, restores the live Stripe Payment Link path
    (``data-pay-via="stripe-payment-page"``, ``Pay £2.45 - …``).
    """
    if coming_soon is None:
        coming_soon = catalog_buy_buttons_coming_soon()
    # Visible label is intentionally short; platform stays in id / data / aria-label.
    buy_label = f"BUY - {RELEASE_VERSION}"
    aria = f"{buy_label} ({a.label})"
    if coming_soon:
        href = COMING_SOON_PUBLIC_HREF
        return (
            f'<a class="dl dl-coming-soon" id="dl-{a.platform}" href="{href}" '
            f'rel="noopener noreferrer" '
            f'data-platform="{a.platform}" data-filename="{a.filename}" '
            f'data-price-pence="245" data-pay-via="coming-soon" '
            f'data-coming-soon="1" aria-label="{aria}">'
            f"{buy_label}</a>"
        )
    href = a.pay_path
    return (
        f'<a class="dl" id="dl-{a.platform}" href="{href}" '
        f'rel="noopener noreferrer" target="_blank" '
        f'data-platform="{a.platform}" data-filename="{a.filename}" '
        f'data-price-pence="245" data-pay-via="stripe-payment-page" '
        f'aria-label="{aria}">'
        f"{buy_label}</a>"
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
    if coming_soon:
        price_line = (
            f"{PRICE_LABEL} GBP per package when available — "
            f"buy buttons coming soon (links return to restoreprivacy.online)"
        )
        buttons_mode = ' data-buy-mode="coming-soon"'
    else:
        price_line = (
            f"{PRICE_LABEL} GBP per package — pay on Stripe, "
            f"then download starts automatically"
        )
        buttons_mode = ' data-buy-mode="stripe-live"'
    # Order: title/price → pay controls → tip. Homepage omits STRONG DISCLAIMER
    # banner (apps/licence retain payment-required language).
    return f"""
  <section class="downloads panel-card" id="downloads" aria-label="Download Restore Privacy client">
    <h2>Download client v{RELEASE_VERSION}</h2>
    <p class="dl-sub">Windows | Linux | macOS | iOS | Android</p>
    <p class="dl-price" id="dl-price">{price_line}</p>
    <div class="dl-buttons" id="dl-buttons" data-dl-layout="3+2"{buttons_mode}>
    <div class="dl-row dl-row-3" id="dl-row-1" data-dl-row="1" data-dl-count="{len(row1)}">
      {row1_html}
    </div>{row2_block}
    </div>
{render_catalog_footer_html()}
  </section>
"""
