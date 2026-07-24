"""Release download catalog + paid download UI (version 0.4.2).

Primary path: pay **£2.45** (GBP) via Stripe Checkout per package, then a
single-use download token. Free permanent GitHub ``href`` is not used on the
public buttons. After payment the status host **proxies** the installer
(authenticated GitHub API / local assets) so fulfilment works when the
restore-privacy repo is **private**. Buy Me a Coffee is tip/support only.

Current catalog packages: restore-privacy release **0.4.2**
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

RELEASE_VERSION = "0.4.2"
GITHUB_OWNER = "rgsneddon"
GITHUB_REPO = "restore-privacy"
RELEASE_TAG = "0.4.2"
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


# Canonical public asset filenames (must match GitHub Release 0.4.0 assets).
WINDOWS_EXE_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-windows-x64-setup.exe"
ANDROID_APK_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-android.apk"
MACOS_ZIP_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-macos.zip"
IOS_ZIP_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-ios.zip"
LINUX_TGZ_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-linux-x64.tar.gz"

PRICE_LABEL = "£2.45"
PRICE_YEARLY_LABEL = "£29.40"  # 12 × £2.45 GBP anchor
# Large white bold callout under "Download client v…" on the public homepage.
ONLY_PRICE_BANNER = "ONLY £2.45 per month — or pay yearly (£29.40)"
# Short single-line note under the price box (no re-listing of £ amounts).
YEARLY_PLAN_NOTE = (
    "Pick Monthly or Yearly for your platform. "
    "Local currency display uses the GBP anchors above "
    "(we accept your local currency when Stripe allows; otherwise USD)."
)
# Shown under the buy-button grid (bold bright white, price-box-like frame).
PLATFORM_SELECT_NOTE = (
    "Please select your device platform carefully — you will only receive "
    "the installer for that platform."
)
# Homepage download price block (single shipped contract for public #downloads).
PACKAGE_IDENTITY = "one device licence"
TRIAL_SUBSCRIPTION_SENTENCE = (
    "your monthly subscription begins after your 7 day trial"
)
PAY_AND_KEYGEN_CLAUSE = (
    "pay on Stripe, then download starts automatically "
    "(licence key and download links are emailed to you separately)"
)
# Default tip identity; runtime public page uses coffee_tip_url() (env override).
BMC_TIP_URL = COFFEE_LINK_URL

# --- Public buy-button mode ---
# Default OFF (live Stripe subscription Pay): platform controls open subscription Payment Link.
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
        """Paid entry: monthly Stripe Payment Link for this platform."""
        return self.pay_path_for_interval("month")

    def pay_path_for_interval(
        self,
        interval: str = "month",
        *,
        currency: str = "",
    ) -> str:
        """Stripe Payment Link for *interval* (``month`` or ``year``) + platform."""
        from payments import stripe_payment_page_href_for_platform

        return stripe_payment_page_href_for_platform(
            self.platform, interval=interval, currency=currency
        )


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
                    margin: 0 0 0.5rem; color: var(--rb-cream); text-transform: uppercase; }
    /* Single large price callout — no second £ amount banner below it */
    .dl-only-price {
      margin: 0.25rem auto 0.55rem;
      padding: 0.55rem 0.85rem;
      max-width: 26rem;
      font-size: clamp(1.35rem, 4.2vw, 2.05rem);
      font-weight: 900;
      line-height: 1.2;
      letter-spacing: 0.04em;
      color: #ffffff;
      text-shadow: 0 2px 14px rgba(0, 0, 0, 0.45), 0 0 1px rgba(0, 0, 0, 0.55);
      font-family: Georgia, "Palatino Linotype", Palatino, "Times New Roman", serif;
      font-style: normal;
      text-transform: uppercase;
      text-align: center;
      width: 100%;
      box-sizing: border-box;
      background: var(--rb-price-panel-bg, linear-gradient(165deg, #1a4a7a 0%, #0a1628 70%));
      border: 1px solid rgba(174, 208, 234, 0.35);
      border-radius: 14px;
      box-shadow: 0 8px 24px rgba(4, 12, 28, 0.35);
    }
    /* One local-currency line (accept notice included; no duplicate italic line) */
    .dl-local-price {
      text-align: center;
      color: var(--rb-muted, #aed0ea);
      font-weight: 600;
      margin: 0.15rem auto 0.65rem;
      max-width: 36rem;
      line-height: 1.4;
      font-size: clamp(0.82rem, 2.1vw, 0.95rem);
    }
    .dl-accept-currency[hidden] { display: none !important; }
    .dl-sub { display: none; } /* platforms shown on tiles only */
    /* Nested price box: trial + pay once (~2/3 width) */
    .dl-price-box {
      width: 66.67%;
      max-width: 66.67%;
      margin: 0 auto 1rem;
      padding: 0.7rem 1rem;
      box-sizing: border-box;
      border: 1px solid rgba(174, 208, 234, 0.35);
      border-radius: 12px;
      background: var(--rb-price-panel-bg, linear-gradient(165deg, #1a4a7a 0%, #0a1628 70%));
      box-shadow: 0 6px 20px rgba(4, 12, 28, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    }
    .dl-price {
      font-size: clamp(0.88rem, 2.2vw, 1rem);
      margin: 0;
      font-weight: 700;
      color: #ffffff;
      line-height: 1.4;
      text-align: center;
      letter-spacing: 0.01em;
      text-shadow: 0 1px 8px rgba(0, 0, 0, 0.35);
      font-family: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
    }
    .dl-interval-note {
      font-size: 0.8rem; color: rgba(174, 208, 234, 0.92);
      margin: 0.45rem 0 0; line-height: 1.35; font-weight: 600;
    }
    .dl-platform-note-box {
      width: 66.67%;
      max-width: 66.67%;
      margin: 1rem auto 0.25rem;
      padding: 0.65rem 0.9rem;
      box-sizing: border-box;
      border: 1px solid var(--rb-card-border);
      border-radius: 12px;
      background: rgba(10, 22, 40, 0.45);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
    .dl-platform-note {
      margin: 0;
      font-size: clamp(0.85rem, 2vw, 0.98rem);
      font-weight: 700;
      line-height: 1.4;
      color: #ffffff;
      text-align: center;
      text-shadow: 0 1px 0 rgba(0, 0, 0, 0.35);
    }
    .dl-payment-disclaimer {
      max-width: 36rem; margin: 1.15rem auto 0.35rem; padding: 0.65rem 0.85rem;
      font-size: 0.82rem; line-height: 1.45; font-weight: 600;
      color: #fecaca; background: rgba(127, 29, 29, 0.35);
      border: 1px solid #b91c1c; border-radius: 12px; text-align: left;
    }
    .dl-buttons {
      display: flex; flex-direction: column; gap: 1rem; align-items: stretch; width: 100%;
    }
    .dl-row {
      display: flex; flex-direction: row; flex-wrap: wrap; gap: 1rem;
      justify-content: center; align-items: stretch; width: 100%;
    }
    .dl-row-3, .dl-row-2 { max-width: 100%; }
    .dl-platform-cell {
      display: flex; flex-direction: column; align-items: stretch; gap: 0.45rem;
      min-width: 9.5rem; width: clamp(9.5rem, 18vw, 11rem);
      padding: 0.65rem 0.55rem 0.7rem;
      border-radius: 14px;
      background: rgba(8, 18, 32, 0.45);
      border: 1px solid rgba(174, 208, 234, 0.18);
      box-sizing: border-box;
    }
    .dl-platform-label {
      font-weight: 800; font-size: 0.98rem; color: var(--rb-fg, #e8f1ff);
      letter-spacing: 0.03em; text-align: center; margin: 0 0 0.1rem;
    }
    .dl-interval-row {
      display: flex; flex-direction: column; gap: 0.4rem; width: 100%;
      align-items: stretch;
    }
    /* Shared buy control: pill, not square — month/year same size */
    a.dl, button.dl {
      display: inline-flex; flex-direction: column; align-items: center; justify-content: center;
      gap: 0.15rem;
      width: 100%; max-width: none;
      min-height: 2.65rem; height: auto;
      padding: 0.55rem 0.6rem;
      background: linear-gradient(180deg, var(--rb-btn) 0%, var(--rb-btn-deep) 100%);
      color: #fff; text-decoration: none; border-radius: 10px;
      font-weight: 800; font-size: 0.86rem; box-sizing: border-box;
      border: 1px solid rgba(255,255,255,0.22); cursor: pointer;
      font-family: inherit; text-align: center; line-height: 1.2;
      box-shadow: 0 3px 10px rgba(7, 30, 60, 0.32);
      transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease;
      aspect-ratio: auto;
      flex: 0 0 auto;
    }
    a.dl .dl-platform, button.dl .dl-platform {
      font-size: 0.95rem; font-weight: 800; letter-spacing: 0.02em;
      line-height: 1.15; color: #ffffff;
    }
    a.dl .dl-buy, button.dl .dl-buy {
      font-size: 0.84rem; font-weight: 800; opacity: 1;
      letter-spacing: 0.01em; color: inherit;
    }
    a.dl:hover, button.dl:hover {
      filter: brightness(1.08);
      transform: translateY(-1px);
      box-shadow: 0 5px 14px rgba(7, 30, 60, 0.4);
    }
    a.dl:focus-visible, button.dl:focus-visible {
      outline: 2px solid var(--rb-accent); outline-offset: 3px;
    }
    /* Platform colours apply to BOTH monthly and yearly (data-platform on cell) */
    .dl-platform-cell[data-platform="windows"] a.dl,
    a.dl#dl-windows, button.dl#dl-windows,
    a.dl#dl-windows-year {
      background: linear-gradient(180deg, #2f8fd8 0%, #1a5f9e 100%);
      color: #ffffff;
    }
    .dl-platform-cell[data-platform="android"] a.dl,
    a.dl#dl-android, button.dl#dl-android,
    a.dl#dl-android-year {
      background: linear-gradient(180deg, #2f9e6b 0%, #1b6b48 100%);
      color: #ffffff;
    }
    .dl-platform-cell[data-platform="macos"] a.dl,
    a.dl#dl-macos, button.dl#dl-macos,
    a.dl#dl-macos-year {
      background: linear-gradient(180deg, #6a7a8c 0%, #3d4754 100%);
      color: #ffffff;
    }
    .dl-platform-cell[data-platform="ios"] a.dl,
    a.dl#dl-ios, button.dl#dl-ios,
    a.dl#dl-ios-year {
      background: linear-gradient(180deg, #5b6fd6 0%, #3b4aa8 100%);
      color: #ffffff;
    }
    .dl-platform-cell[data-platform="linux"] a.dl,
    a.dl#dl-linux, button.dl#dl-linux,
    a.dl#dl-linux-year {
      background: linear-gradient(180deg, #d4ad2e 0%, #8a6e12 100%);
      color: #0a1628;
    }
    /* Yearly: same hue, slightly deeper edge so month/year match family */
    a.dl.dl-interval-year {
      border-color: rgba(255,255,255,0.32);
      box-shadow: 0 3px 10px rgba(7, 30, 60, 0.28), inset 0 0 0 1px rgba(0,0,0,0.12);
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
      .dl-platform-cell { width: min(11rem, 46vw); min-width: 8.5rem; }
      a.dl, button.dl { min-height: 2.5rem; font-size: 0.82rem; }
      .dl-price-box, .dl-platform-note-box {
        width: 100%;
        max-width: 100%;
        padding: 0.65rem 0.75rem;
      }
      .dl-only-price {
        font-size: clamp(1.15rem, 5.5vw, 1.65rem);
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
    local_price: object | None = None,
) -> str:
    """One platform control (stable id + data attrs for layout/tests).

    When *coming_soon* is true (default via :func:`catalog_buy_buttons_coming_soon`),
    the control is a temporary self-link to :data:`COMING_SOON_PUBLIC_HREF`.

    When *coming_soon* is false, live Stripe Payment Link path
    (``data-pay-via="stripe-payment-page"``).

    *local_price* is a :class:`local_currency.LocalPriceDisplay` for tile labels.
    """
    if coming_soon is None:
        coming_soon = catalog_buy_buttons_coming_soon()
    platform_title = platform_face_title(a.platform)
    month_label = "Monthly £2.45"
    year_label = f"Yearly {PRICE_YEARLY_LABEL}"
    ccy = ""
    if local_price is not None:
        month_label = f"Monthly {getattr(local_price, 'monthly_label', month_label)}"
        year_label = f"Yearly {getattr(local_price, 'yearly_label', year_label)}"
        ccy = str(getattr(local_price, "currency", "") or "")
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
            f'<div class="dl-platform-cell" id="dl-cell-{a.platform}" '
            f'data-platform="{a.platform}">'
            f'<a class="dl dl-coming-soon" id="dl-{a.platform}" href="{href}" '
            f'rel="noopener noreferrer" '
            f'data-platform="{a.platform}" data-filename="{a.filename}" '
            f'data-price-pence="245" data-pay-via="coming-soon" '
            f'data-billing-interval="month" '
            f'data-coming-soon="1" aria-label="{aria}">'
            f"{face}</a></div>"
        )
    href_m = a.pay_path_for_interval("month", currency=ccy)
    href_y = a.pay_path_for_interval("year", currency=ccy)
    # Dual subscription interval: monthly + yearly Payment Links
    return (
        f'<div class="dl-platform-cell" id="dl-cell-{a.platform}" '
        f'data-platform="{a.platform}">'
        f'<span class="dl-platform-label">{platform_title}</span>'
        f'<div class="dl-interval-row" id="dl-interval-{a.platform}">'
        f'<a class="dl dl-interval-month" id="dl-{a.platform}" href="{href_m}" '
        f'rel="noopener noreferrer" target="_blank" '
        f'data-platform="{a.platform}" data-filename="{a.filename}" '
        f'data-price-pence="245" data-pay-via="stripe-payment-page" '
        f'data-billing-interval="month" '
        f'data-display-currency="{ccy}" '
        f'aria-label="{platform_title}: monthly subscription — {a.label}">'
        f'<span class="dl-buy">{month_label}</span></a>'
        f'<a class="dl dl-interval-year" id="dl-{a.platform}-year" href="{href_y}" '
        f'rel="noopener noreferrer" target="_blank" '
        f'data-platform="{a.platform}" data-filename="{a.filename}" '
        f'data-pay-via="stripe-payment-page" '
        f'data-billing-interval="year" '
        f'data-display-currency="{ccy}" '
        f'aria-label="{platform_title}: yearly subscription — {a.label}">'
        f'<span class="dl-buy">{year_label}</span></a>'
        f"</div></div>"
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
    accept_language: str = "",
    country: str = "",
    currency: str = "",
) -> str:
    """HTML: platform buy controls (live Stripe pay **or** temporary coming-soon).

    Platform menu below the download title is **two rows**: three items, then two.

    *coming_soon* defaults to :func:`catalog_buy_buttons_coming_soon`. Pass
    ``coming_soon=False`` (or env live switch) to restore Stripe Pay buttons.

    Local-currency display uses GBP anchors £2.45 / £29.40 with
    :mod:`local_currency` (Stripe-unsupported currencies → USD).
    """
    items = list(assets) if assets is not None else available_downloads()
    if not items:
        return ""
    if coming_soon is None:
        coming_soon = catalog_buy_buttons_coming_soon()

    try:
        from local_currency import resolve_local_price_display
    except ImportError:  # pragma: no cover
        from status_page.local_currency import (  # type: ignore
            resolve_local_price_display,
        )

    local = resolve_local_price_display(
        accept_language=accept_language,
        country=country,
        explicit_currency=currency,
    )

    if not coming_soon:
        from payments import stripe_payment_page_url

        # Keep pay pipeline imported/ready; buttons use per-platform pay_path.
        _ = stripe_payment_page_url()

    row1, row2 = download_menu_rows(items)
    row1_html = "\n      ".join(
        _render_platform_pay_link(a, coming_soon=coming_soon, local_price=local)
        for a in row1
    )
    row2_block = ""
    if row2:
        row2_html = "\n      ".join(
            _render_platform_pay_link(a, coming_soon=coming_soon, local_price=local)
            for a in row2
        )
        row2_block = f"""
    <div class="dl-row dl-row-2" id="dl-row-2" data-dl-row="2" data-dl-count="{len(row2)}">
      {row2_html}
    </div>"""
    # One local-currency line (includes accept notice — no second accept paragraph).
    accept = local.accept_notice  # e.g. we accept *EUR*
    if (local.currency or "").upper() in ("GBP", ""):
        local_line = (
            f"GBP catalog price · {accept}"
            if accept
            else "GBP catalog price"
        )
    else:
        local_line = (
            f"Local: <strong>{local.monthly_label}</strong> / mo · "
            f"<strong>{local.yearly_label}</strong> / yr "
            f"(from £2.45 / £29.40 GBP) · {accept}"
        )
    if coming_soon:
        price_line = (
            f"{PRICE_LABEL} GBP · {PACKAGE_IDENTITY} — "
            f"{TRIAL_SUBSCRIPTION_SENTENCE} — buy buttons coming soon"
        )
        buttons_mode = ' data-buy-mode="coming-soon"'
    else:
        # £2.45 GBP once here; banner has ONLY + yearly. No third £ list.
        price_line = (
            f"{PRICE_LABEL} GBP · {PACKAGE_IDENTITY} — "
            f"{TRIAL_SUBSCRIPTION_SENTENCE} — {PAY_AND_KEYGEN_CLAUSE}"
        )
        buttons_mode = (
            ' data-buy-mode="stripe-live" data-billing-intervals="month,year"'
            f' data-display-currency="{local.currency}"'
            f' data-stripe-presentment="{local.stripe_presentment_currency}"'
        )
    # Order: title → one price banner → local line → trial box → pay tiles.
    return f"""
  <section class="downloads panel-card" id="downloads" aria-label="Download Restore Privacy client"
    data-price-currency="{local.currency}" data-accept-currency="{local.currency}">
    <h2>Download client v{RELEASE_VERSION}</h2>
    <p class="dl-only-price" id="dl-only-price">{ONLY_PRICE_BANNER}</p>
    <p class="dl-local-price" id="dl-local-price">{local_line}</p>
    <p class="dl-accept-currency" id="dl-accept-currency" hidden>{accept}</p>
    <div class="dl-price-box" id="dl-price-box">
      <p class="dl-price" id="dl-price">{price_line}</p>
      <p class="dl-interval-note" id="dl-interval-note">{YEARLY_PLAN_NOTE}</p>
    </div>
    <div class="dl-buttons" id="dl-buttons" data-dl-layout="3+2"{buttons_mode}>
    <div class="dl-row dl-row-3" id="dl-row-1" data-dl-row="1" data-dl-count="{len(row1)}">
      {row1_html}
    </div>{row2_block}
    </div>
    <div class="dl-platform-note-box" id="dl-platform-note-box">
      <p class="dl-platform-note" id="dl-platform-note">{PLATFORM_SELECT_NOTE}</p>
    </div>
  </section>
"""