"""Release download catalog + paid download UI (Restore Privacy Suite v1.0.7).

Primary path: pay **£3.00** (GBP) via Stripe Checkout per package, then a
time-limited download token (default **12 hours**, reusable until expiry).
Free permanent GitHub ``href`` is not used on the public buttons. After payment
the status host **proxies** the installer (authenticated GitHub API / local
assets) so fulfilment works when the restore-privacy repo is **private**.
Buy Me a Coffee is tip/support only.

Current catalog packages: Restore Privacy Suite **1.0.7**
(Windows setup needs no separate Python install; macOS Developer ID notarized;
iOS Team-signed sideload).
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Iterable

try:
    from coffee_link import (
        COFFEE_LINK_URL,
        coffee_tip_url,
        render_site_copyright_footer_html,
        site_copyright_text,
    )
except ImportError:  # package import path (status_page as package)
    from status_page.coffee_link import (  # type: ignore
        COFFEE_LINK_URL,
        coffee_tip_url,
        render_site_copyright_footer_html,
        site_copyright_text,
    )

RELEASE_VERSION = "1.0.7"
GITHUB_OWNER = "rgsneddon"
GITHUB_REPO = "restore-privacy"
RELEASE_TAG = "1.0.7"
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

# Prefer payments module anchors when available (single source of truth).
try:
    from payments import (  # type: ignore
        PRICE_LABEL as _PAY_PRICE_LABEL,
        PRICE_YEARLY_LABEL as _PAY_PRICE_YEARLY_LABEL,
        YEARLY_DISCOUNT_PERCENT as _PAY_YEARLY_DISCOUNT_PERCENT,
    )

    PRICE_LABEL = _PAY_PRICE_LABEL
    PRICE_YEARLY_LABEL = _PAY_PRICE_YEARLY_LABEL
    _YEARLY_SAVE_PCT = int(_PAY_YEARLY_DISCOUNT_PERCENT)
except Exception:  # noqa: BLE001
    PRICE_LABEL = "£3.00"
    PRICE_YEARLY_LABEL = "£30.00"
    _YEARLY_SAVE_PCT = 17
# Large white bold callout under "Download client v…" on the public homepage.
ONLY_PRICE_BANNER = (
    f"ONLY {PRICE_LABEL} per month — or annual {PRICE_YEARLY_LABEL} "
    f"(save ~{_YEARLY_SAVE_PCT}% vs 12 × monthly) — includes a 3-day free trial"
)
# Short single-line note under the price box (no re-listing of £ amounts).
YEARLY_PLAN_NOTE = (
    "Select your device and plan below, then Buy now. "
    f"Annual is {PRICE_YEARLY_LABEL} (save ~{_YEARLY_SAVE_PCT}% vs 12 × monthly). "
    "Every plan includes a 3-day free trial — no money is taken until after the trial ends. "
    "Local currency display uses the GBP anchors above "
    "(we accept your local currency when Stripe allows; otherwise USD)."
)
# Shown under the selection form (bold bright white, price-box-like frame).
PLATFORM_SELECT_NOTE = (
    "Please select your device platform carefully — you will only receive "
    "the installer for that platform."
)
# Homepage download price block (single shipped contract for public #downloads).
PACKAGE_IDENTITY = "one device licence"
# Catalog trial copy (kept name for import stability).
TRIAL_SUBSCRIPTION_SENTENCE = (
    f"Select your device and plan — Monthly {PRICE_LABEL} or Annual {PRICE_YEARLY_LABEL} — "
    "3-day free trial — no money is taken until after the trial ends"
)
CATALOG_SUBSCRIPTION_SENTENCE = TRIAL_SUBSCRIPTION_SENTENCE
PAY_AND_KEYGEN_CLAUSE = (
    "Buy now opens secure Stripe checkout (card on file; first charge after the 3-day trial), "
    "then download starts automatically "
    "(licence key and download links are emailed to you separately)"
)
# Buy now label on the homepage form.
BUY_NOW_LABEL = "Buy now"
# Auto-renew checkbox (purchase flow → subscription_data cancel_at_period_end).
AUTO_RENEW_LABEL = "Auto-renew this subscription"
AUTO_RENEW_HELP = (
    "When on, Stripe bills again at the end of each month or year. "
    "Turn off for a single paid period (access until period end, no further charges)."
)
# Honest Stripe branding note (site form uses main CSS; Checkout is Stripe-hosted).
# Custom domains (pay.yourdomain) only change the hostname — still not full CSS.
STRIPE_CHECKOUT_BRANDING_NOTE = (
    "Card payment opens on Stripe’s secure checkout page. "
    "That page uses Stripe’s layout with optional Dashboard logo/colours "
    "(and optional pay.yourdomain custom domain) — "
    "it cannot load this website’s full CSS."
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
        """Paid entry: site-hosted plan page for this platform."""
        return self.pay_path_for_interval("month")

    def pay_path_for_interval(
        self,
        interval: str = "month",
        *,
        currency: str = "",
    ) -> str:
        """Site ``/pay`` plan page for *interval* preselect + platform.

        Catalog primary path is the status host plan page (not buy.stripe.com).
        """
        from payments import site_pay_plan_path, stripe_payment_page_href_for_platform

        _ = currency  # presentment applied at Checkout Session create
        # Prefer pure relative path for catalog HTML (same-origin)
        return site_pay_plan_path(self.platform, interval=interval) or (
            stripe_payment_page_href_for_platform(
                self.platform, interval=interval, currency=currency
            )
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
    f"Catalog v{RELEASE_VERSION} — installers after {PRICE_LABEL} payment only (signed packages)"
)
# Back-compat aliases (historical RUST_REPO_* names; values are pre-RUST catalog).
RUST_REPO_URL = PRODUCT_CATALOG_URL
RUST_REPO_LABEL = PRODUCT_CATALOG_LABEL


# Compatibility aliases used by older tests (map to 0.3.7 installers).
WINDOWS_ZIP_FILENAME = WINDOWS_EXE_FILENAME


def download_css() -> str:
    """CSS for catalog pay section (RB-donate inspired navy/blue palette)."""
    return """
    /* Download shop — aligns with site-chrome-pro / data-path shell */
    .downloads {
      width: 100%; text-align: center; box-sizing: border-box;
      position: relative;
    }
    .downloads h2 {
      font-size: 0.82rem; letter-spacing: 0.12em; font-weight: 700;
      margin: 0 0 0.65rem; color: var(--rb-muted, var(--rb-cream));
      text-transform: uppercase;
    }
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
      /* Same UI stack as .dl-price / public chrome body (not Georgia serif) */
      font-family: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
      font-style: normal;
      text-transform: uppercase;
      text-align: center;
      width: 100%;
      box-sizing: border-box;
      background: var(--rb-price-panel-bg, linear-gradient(165deg, #1a4a7a 0%, #0a1628 70%));
      border: 1px solid rgba(174, 208, 234, 0.35);
      border-radius: var(--rb-radius, 0px);
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
    /* Nested price box (~2/3 width) */
    .dl-price-box {
      width: 66.67%;
      max-width: 66.67%;
      margin: 0 auto 1rem;
      padding: 0.7rem 1rem;
      box-sizing: border-box;
      border: 1px solid rgba(174, 208, 234, 0.35);
      border-radius: var(--rb-radius-sm, 0px);
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
      border-radius: var(--rb-radius-sm, 0px);
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
      border: 1px solid #b91c1c; border-radius: var(--rb-radius-sm, 0px); text-align: left;
    }
    .dl-buttons {
      display: flex; flex-direction: column; gap: 1rem; align-items: stretch; width: 100%;
    }
    /* Homepage embedded buy form (platform + plan + Buy now) */
    .dl-buy-form {
      width: min(30rem, 100%);
      margin: 0 auto;
      padding: 1.1rem 1.15rem 1.2rem;
      box-sizing: border-box;
      border-radius: var(--rb-radius, 14px);
      border: 1px solid transparent;
      background:
        linear-gradient(
          165deg,
          color-mix(in srgb, var(--rb-card, #132a4a) 90%, transparent) 0%,
          color-mix(in srgb, var(--rb-code-bg, rgba(8, 18, 32, 0.55)) 95%, transparent) 100%
        ) padding-box,
        var(--rb-neon-border, linear-gradient(135deg, #00e5ff, #2694e8, #39ff6a)) border-box;
      background-origin: border-box;
      background-clip: padding-box, border-box;
      box-shadow: var(--rb-panel-shadow-soft, 0 4px 16px rgba(2, 8, 20, 0.28));
      text-align: left;
    }
    .dl-buy-field { margin: 0 0 0.85rem; }
    .dl-buy-field label.dl-buy-label {
      display: block; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.05em;
      text-transform: uppercase; color: var(--rb-muted, #aed0ea); margin-bottom: 0.35rem;
    }
    .dl-buy-field select {
      width: 100%; box-sizing: border-box; padding: 0.7rem 0.85rem;
      border-radius: var(--rb-radius-sm, 10px);
      border: 1px solid var(--rb-input-border, rgba(174, 208, 234, 0.35));
      background: var(--rb-input-bg, rgba(8, 18, 32, 0.75));
      color: var(--rb-field-fg, #e8f1ff); font: inherit; font-weight: 600;
    }
    .dl-buy-field select:focus {
      outline: none;
      border-color: color-mix(in srgb, var(--rb-neon-cyan, #00e5ff) 55%, transparent);
      box-shadow: 0 0 0 3px color-mix(in srgb, var(--rb-neon-cyan, #00e5ff) 18%, transparent);
    }
    .dl-plan-options { display: flex; flex-direction: column; gap: 0.5rem; }
    .dl-plan-option {
      display: block; cursor: pointer; border-radius: var(--rb-radius-sm, 0px);
      border: 1px solid rgba(174, 208, 234, 0.25); padding: 0.7rem 0.85rem;
      background: rgba(10, 22, 40, 0.55);
    }
    .dl-plan-option:has(input:checked) {
      border-color: rgba(0, 229, 255, 0.55);
      box-shadow: 0 0 0 1px rgba(0, 229, 255, 0.25);
      background: rgba(20, 50, 90, 0.55);
    }
    .dl-plan-option input { margin-right: 0.5rem; accent-color: var(--rb-btn, #2694e8); }
    .dl-plan-title { font-weight: 800; color: #fff; font-size: 0.98rem; }
    .dl-plan-price { font-weight: 700; color: var(--rb-soft, #deedf7); margin-top: 0.15rem; font-size: 0.9rem; }
    .dl-plan-save {
      display: inline-block; margin-left: 0.35rem; padding: 0.1rem 0.4rem;
      border-radius: var(--rb-radius-control, 0px); font-size: 0.7rem; font-weight: 800;
      background: rgba(57, 255, 106, 0.18); color: #39ff6a;
    }
    .dl-buy-now {
      width: 100%; margin-top: 0.35rem; padding: 0.85rem 1rem; border: 0;
      border-radius: var(--rb-radius-sm, 0px); font-weight: 800; font-size: 1.05rem; cursor: pointer;
      font-family: inherit; color: #fff;
      background: linear-gradient(180deg, var(--rb-btn, #2694e8) 0%, var(--rb-btn-deep, #1a6fad) 100%);
      box-shadow: 0 4px 14px rgba(7, 30, 60, 0.4);
    }
    .dl-buy-now:hover { filter: brightness(1.08); }
    .dl-auto-renew-field { margin: 0.25rem 0 0.85rem; }
    .dl-auto-renew-label {
      display: flex; align-items: flex-start; gap: 0.45rem; cursor: pointer;
      font-weight: 700; color: #e8f1ff; font-size: 0.92rem;
    }
    .dl-auto-renew-label input { margin-top: 0.15rem; accent-color: var(--rb-btn, #2694e8); }
    .dl-auto-renew-help {
      margin: 0.35rem 0 0 1.45rem; font-size: 0.78rem; line-height: 1.4;
      color: rgba(174, 208, 234, 0.9);
    }
    .dl-stripe-branding {
      margin: 0.65rem 0 0; font-size: 0.78rem; line-height: 1.4;
      color: rgba(174, 208, 234, 0.88); text-align: center;
    }
    .dl-pay-error {
      color: #fecaca; background: rgba(127, 29, 29, 0.35); border: 1px solid #b91c1c;
      border-radius: var(--rb-radius-sm, 0px); padding: 0.65rem 0.85rem; margin: 0 auto 0.85rem;
      max-width: 28rem; text-align: left; font-weight: 600; font-size: 0.88rem;
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
      border-radius: var(--rb-radius, 0px);
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
      color: #fff; text-decoration: none; border-radius: var(--rb-radius-sm, 0px);
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
    """Deprecated: footer is injected by :func:`public_page_close` for all pages.

    Historical name retained for imports. Returns empty so shells that still
    call this helper do not double-render the copyright + map line.
    """
    return ""


def render_catalog_footer_html() -> str:
    """Under-download-buttons footer (intentionally empty on public homepage).

    Copyright sits at the page bottom via :func:`render_bmc_tip_html` in the
    homepage shell. How-to-buy / catalogue links remain omitted.
    """
    return ""


# Back-compat: historical names return the public copyright footer.
render_rust_footer_html = render_bmc_tip_html
render_site_footer_html = render_bmc_tip_html


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


def detect_platform_from_user_agent(user_agent: str = "") -> str:
    """Map browser User-Agent to a catalog free-download platform key.

    Returns one of: windows, android, macos, ios, linux — empty if unknown.
    Order matters (iPhone/iPad before Mac; Android before Linux).
    """
    ua = (user_agent or "").strip()
    if not ua:
        return ""
    low = ua.lower()
    # Mobile first
    if "iphone" in low or "ipad" in low or "ipod" in low:
        return "ios"
    if "android" in low:
        return "android"
    # Desktop OS brands
    if "windows" in low or "win64" in low or "win32" in low:
        return "windows"
    # macOS: "Macintosh" / "Mac OS X" / "Mac OS"
    if "macintosh" in low or "mac os" in low or "mac_powerpc" in low:
        return "macos"
    if "cros" in low:
        # ChromeOS — closest free package is Linux
        return "linux"
    if "linux" in low or "x11" in low or "ubuntu" in low or "fedora" in low:
        return "linux"
    return ""



# --- Rx Privacy Browser (MV3 companion under Suite monopin) ---
RX_BROWSER_PACKAGE_BASENAME = (
    f"restore-privacy-rx-browser-{RELEASE_VERSION}.zip"
)
BROWSER_EXTENSION_PACKAGE_BASENAME = (
    f"restore-privacy-browser-extension-{RELEASE_VERSION}.zip"
)

# Multi-platform Rx package slots (must match scripts/package_browser_rx.py).
RX_BROWSER_PLATFORMS: tuple[str, ...] = (
    "macos",
    "windows",
    "linux-x86_64",
    "linux-aarch64",
    "ios",
    "android",
    "default",
    "chromium",
)


def browser_extension_package_filename(version: str | None = None) -> str:
    """Canonical browser_extension zip basename for the Suite monopin."""
    ver = (version or RELEASE_VERSION).strip() or RELEASE_VERSION
    return f"restore-privacy-browser-extension-{ver}.zip"


def rx_browser_package_filename(
    version: str | None = None,
    *,
    platform: str | None = None,
) -> str:
    """Catalog basename for Rx Privacy Browser package (Suite monopin).

    *platform* selects OS-specific archive when set (macos, windows,
    linux-x86_64, linux-aarch64, ios, android). Empty/default → generic zip
    that expands on all desktop OSes (valid PKZIP for macOS Archive Utility).
    """
    ver = (version or RELEASE_VERSION).strip() or RELEASE_VERSION
    plat = (platform or "").strip().lower()
    if not plat or plat in ("default", "browser", "chromium", "generic"):
        return f"restore-privacy-rx-browser-{ver}.zip"
    # Map Suite free-download UA platforms to Rx package slots
    if plat == "linux":
        plat = "linux-x86_64"
    if plat == "macos":
        return f"restore-privacy-rx-browser-{ver}-macos.zip"
    if plat == "windows":
        return f"restore-privacy-rx-browser-{ver}-windows.zip"
    if plat == "ios":
        return f"restore-privacy-rx-browser-{ver}-ios.zip"
    if plat == "android":
        return f"restore-privacy-rx-browser-{ver}-android.zip"
    if plat in ("linux-x86_64", "linux-aarch64"):
        return f"restore-privacy-rx-browser-{ver}-{plat}.tar.gz"
    if plat == "linux-x86_64-zip":
        return f"restore-privacy-rx-browser-{ver}-linux-x86_64.zip"
    return f"restore-privacy-rx-browser-{ver}.zip"


def free_open_asset_versions() -> frozenset[str]:
    """Version path segments allowed under /assets/{version}/..."""
    return frozenset({RELEASE_VERSION})


def rx_browser_package_href(
    *,
    version: str | None = None,
    user_agent: str = "",
    platform: str | None = None,
) -> str:
    """Relative free/store path for the Rx browser package.

    Device-aware: when *platform* or *user_agent* resolves to a known OS,
    serves the platform-specific expandable archive; otherwise the default
    valid ZIP (macOS Archive Utility compatible).
    """
    ver = (version or RELEASE_VERSION).strip() or RELEASE_VERSION
    plat = (platform or "").strip().lower()
    if not plat and user_agent:
        plat = detect_platform_from_user_agent(user_agent) or ""
    fname = rx_browser_package_filename(ver, platform=plat or None)
    return f"/assets/{ver}/{fname}"


def rx_browser_download_label(user_agent: str = "") -> str:
    """Human label for the Rx download control (device-aware wording)."""
    plat = detect_platform_from_user_agent(user_agent)
    base = f"Rx Privacy Browser · Suite {RELEASE_VERSION}"
    if plat in ("android", "ios"):
        return f"{base} ({plat} companion package — MV3 notes inside; full load-unpacked on desktop)"
    if plat == "windows":
        return f"{base} (Windows expandable zip · Chromium Edge/Chrome)"
    if plat == "macos":
        return f"{base} (macOS expandable zip · Chromium load unpacked)"
    if plat == "linux":
        return f"{base} (Linux package · Chromium load unpacked)"
    return f"{base} (Chromium MV3 extension — expandable zip)"


def list_rx_browser_platform_packages(
    *, version: str | None = None
) -> list[dict[str, str]]:
    """All Rx multi-platform package rows for free-open allowlist + inventory."""
    ver = (version or RELEASE_VERSION).strip() or RELEASE_VERSION
    rows: list[dict[str, str]] = [
        {
            "version": ver,
            "kind": "rx_browser",
            "platform": "default",
            "filename": rx_browser_package_filename(ver),
            "relative_path": f"{ver}/{rx_browser_package_filename(ver)}",
            "alias_filename": browser_extension_package_filename(ver),
            "product": "Rx Privacy Browser",
        },
        {
            "version": ver,
            "kind": "browser_extension",
            "platform": "chromium",
            "filename": browser_extension_package_filename(ver),
            "relative_path": f"{ver}/{browser_extension_package_filename(ver)}",
            "product": "Browser Extension",
        },
    ]
    for plat in (
        "macos",
        "windows",
        "linux-x86_64",
        "linux-aarch64",
        "ios",
        "android",
    ):
        fname = rx_browser_package_filename(ver, platform=plat)
        rows.append(
            {
                "version": ver,
                "kind": "rx_browser",
                "platform": plat,
                "filename": fname,
                "relative_path": f"{ver}/{fname}",
                "product": "Rx Privacy Browser",
            }
        )
    # Linux zip alternate
    rows.append(
        {
            "version": ver,
            "kind": "rx_browser",
            "platform": "linux-x86_64-zip",
            "filename": f"restore-privacy-rx-browser-{ver}-linux-x86_64.zip",
            "relative_path": f"{ver}/restore-privacy-rx-browser-{ver}-linux-x86_64.zip",
            "product": "Rx Privacy Browser",
        }
    )
    return rows


def list_suite_extra_packages(
    *, version: str | None = None
) -> list[dict[str, str]]:
    """Non-platform Suite companion packages (Rx browser multi-platform set)."""
    return list_rx_browser_platform_packages(version=version)


def download_menu_rows(
    assets: Iterable[DownloadAsset] | None = None,
) -> tuple[list[DownloadAsset], list[DownloadAsset]]:
    """Split catalog into two rows (legacy helper; homepage no longer grids tiles)."""
    items = list(assets) if assets is not None else available_downloads()
    if len(items) <= 3:
        return items, []
    return items[:3], items[3:]


def _esc_html(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_homepage_buy_form_html(
    assets: Iterable[DownloadAsset] | None = None,
    *,
    coming_soon: bool = False,
    local_price: object | None = None,
    default_platform: str = "",
    default_interval: str = "month",
) -> str:
    """Platform + plan selectors and Buy now form for the Download client box.

    Live mode: ``POST /pay/checkout`` with ``platform`` + ``interval`` creates a
    Stripe subscription Checkout Session for Monthly or Yearly VPN plan.
    """
    items = list(assets) if assets is not None else available_downloads()
    if not items:
        return ""
    ccy = ""
    month_label = PRICE_LABEL
    year_label = PRICE_YEARLY_LABEL
    if local_price is not None:
        ccy = str(getattr(local_price, "currency", "") or "")
        month_label = str(getattr(local_price, "monthly_label", month_label) or month_label)
        year_label = str(getattr(local_price, "yearly_label", year_label) or year_label)

    if coming_soon:
        return (
            f'<div class="dl-buy-form" id="dl-buy-form" data-buy-mode="coming-soon">'
            f'<p class="dl-platform-note" id="dl-coming-soon-note">Buy buttons coming soon.</p>'
            f'<a class="dl dl-coming-soon" id="dl-coming-soon" href="{COMING_SOON_PUBLIC_HREF}" '
            f'rel="noopener noreferrer" data-pay-via="coming-soon">{BUY_NOW_LABEL}</a>'
            f"</div>"
        )

    def_plat = (default_platform or "").strip().lower()
    iv = (default_interval or "month").strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        iv = "year"
    else:
        iv = "month"
    opts = []
    for a in items:
        sel = " selected" if a.platform == def_plat else ""
        title = platform_face_title(a.platform)
        opts.append(
            f'<option value="{_esc_html(a.platform)}"{sel} '
            f'data-filename="{_esc_html(a.filename)}">'
            f"{_esc_html(title)}</option>"
        )
    platform_options = "\n            ".join(opts)
    month_checked = " checked" if iv == "month" else ""
    year_checked = " checked" if iv == "year" else ""
    return f"""
    <form class="dl-buy-form" id="dl-buy-form" method="post" action="/pay/checkout"
          data-pay-via="homepage-buy-form" data-billing-intervals="month,year"
          data-display-currency="{_esc_html(ccy)}">
      <div class="dl-buy-field" id="dl-platform-field">
        <label class="dl-buy-label" for="dl-platform">Device / platform</label>
        <select name="platform" id="dl-platform" required aria-required="true"
                aria-label="Select your device platform">
          <option value="" disabled{" selected" if not def_plat else ""}>Choose your device…</option>
            {platform_options}
        </select>
      </div>
      <div class="dl-buy-field" id="dl-plan-field">
        <span class="dl-buy-label" id="dl-plan-label">Plan</span>
        <div class="dl-plan-options" role="radiogroup" aria-labelledby="dl-plan-label">
          <label class="dl-plan-option" id="dl-plan-month" data-interval="month">
            <input type="radio" name="interval" value="month"{month_checked}
                   aria-label="Monthly VPN plan"/>
            <span class="dl-plan-title">Monthly VPN plan</span>
            <div class="dl-plan-price">{_esc_html(month_label)} / month</div>
            <div class="dl-plan-price" style="font-weight:600;font-size:0.82rem;opacity:0.9">
              3-day free trial · no charge until trial ends</div>
          </label>
          <label class="dl-plan-option" id="dl-plan-year" data-interval="year">
            <input type="radio" name="interval" value="year"{year_checked}
                   aria-label="Yearly VPN plan"/>
            <span class="dl-plan-title">Yearly VPN plan
              <span class="dl-plan-save">SAVE ~{_YEARLY_SAVE_PCT}%</span></span>
            <div class="dl-plan-price">{_esc_html(year_label)} / year</div>
            <div class="dl-plan-price" style="font-weight:600;font-size:0.82rem;opacity:0.9">
              3-day free trial · no charge until trial ends</div>
          </label>
        </div>
      </div>
      <div class="dl-buy-field dl-auto-renew-field" id="dl-auto-renew-field">
        <input type="hidden" name="auto_renew" value="0" id="dl-auto-renew-off"/>
        <label class="dl-auto-renew-label" id="dl-auto-renew-label" for="dl-auto-renew">
          <input type="checkbox" name="auto_renew" value="1" id="dl-auto-renew"
                 checked aria-describedby="dl-auto-renew-help"/>
          <span class="dl-auto-renew-title">{AUTO_RENEW_LABEL}</span>
        </label>
        <p class="dl-auto-renew-help" id="dl-auto-renew-help">{AUTO_RENEW_HELP}</p>
      </div>
      <button type="submit" class="dl-buy-now" id="dl-buy-now">{BUY_NOW_LABEL}</button>
      <p class="dl-stripe-branding" id="dl-stripe-branding">{STRIPE_CHECKOUT_BRANDING_NOTE}</p>
    </form>
"""


# Suite storefront (homepage section above VPN #downloads)
SUITE_SECTION_ID = "suite-storefront"
SUITE_PRODUCT_TITLE = "Restore Privacy Suite"
SUITE_PRODUCT_SUBTITLE = (
    "VPN, Perccent wallet (%), and Evolve in one app — start the KEYGEN free trial to download"
)
SUITE_VERSION_LABEL = f"v {RELEASE_VERSION}"
SUITE_KEYGEN_HINT = (
    f"Brand installers require a KEYGEN licence first: start the 3-day free trial "
    f"({PRICE_LABEL}/month or yearly) — no money is taken until after the trial ends. "
    "Enter the KEYGEN from your fulfilment email to unlock residual Connect and downloads."
)
SUITE_FREE_DOWNLOAD_PATH = "/suite/download"
# Anonymous free-CTA delivery (no KEYGEN / no /pay) — detected platform only
SUITE_FREE_DIRECT_QUERY = "free_direct"
SUITE_PAY_PATH = "/pay"
SUITE_PAY_PRODUCT = "suite"
DOWNLOADS_SECTION_ID = "downloads"
# Full-width free-download face (operator asset freebie.jpg) → monopin platform or map
FREE_PACKAGES_PATH = "/free-packages"
DOWNLOADS_MAP_PATH = "/downloads-map"
DOWNLOADS_MAP_LABEL = "Downloadables Mapped Here"
FREEBIE_IMG_PATH = "/static/freebie.jpg"
# Catalog monopin for links (face art no longer bakes a version string)
FREE_DOWNLOAD_FACE_VERSION = RELEASE_VERSION
FREEBIE_IMG_ALT = (
    "Download Restore Privacy Suite — start the KEYGEN 3-day free trial first"
)
FREE_DOWNLOAD_CTA_ID = "free-download-v1-cta"
FREE_PACKAGES_PAGE_ID = "free-packages-page"
DOWNLOADS_MAP_PAGE_ID = "downloads-map-page"

# Suite product ecosystem sub-menu (Perc explorer + Evolve + Perccent wallet docs).
# Only real public destinations (verified live); align explorer base with admin_perc.
try:
    from admin_perc import DEFAULT_PERC_PUBLIC_BASE as _PERC_EXPLORER_BASE
except ImportError:  # pragma: no cover
    try:
        from status_page.admin_perc import (  # type: ignore
            DEFAULT_PERC_PUBLIC_BASE as _PERC_EXPLORER_BASE,
        )
    except ImportError:  # pragma: no cover
        _PERC_EXPLORER_BASE = "https://135.181.152.10.sslip.io/perc"

SUITE_SUBMENU_ID = "suite-product-submenu"
SUITE_PERC_EXPLORER_HREF = str(_PERC_EXPLORER_BASE).rstrip("/") + "/"
SUITE_PERC_EXPLORER_LABEL = "Perc blockchain explorer"
# Homepage iframe embed (must end with / so framed location.pathname is /perc/).
SUITE_PERC_WALLET_EXPLORER_IFRAME_SRC = SUITE_PERC_EXPLORER_HREF
SUITE_PERC_WALLET_EXPLORER_ID = "suite-perc-wallet-explorer"
SUITE_PERC_WALLET_EXPLORER_IFRAME_ID = "suite-perc-wallet-explorer-frame"
SUITE_PERC_WALLET_EXPLORER_LABEL = "Perccent blockchain explorer"
# Evolve docs: same-origin page (README mirror); white paper + source stay external.
SUITE_EVOLVE_DOCS_HREF = "/EVOLVE.md"
SUITE_EVOLVE_DOCS_LABEL = "Evolve docs"
SUITE_EVOLVE_PAGES_HREF = SUITE_EVOLVE_DOCS_HREF  # back-compat alias for tests/callers
SUITE_EVOLVE_PAGES_LABEL = SUITE_EVOLVE_DOCS_LABEL
SUITE_EVOLVE_WHITEPAPER_HREF = "https://rgsneddon.github.io/evolve/fcg_white_paper.html"
SUITE_EVOLVE_WHITEPAPER_LABEL = "Evolve FCG white paper"
SUITE_EVOLVE_SOURCE_HREF = "https://github.com/rgsneddon/evolve"
SUITE_EVOLVE_SOURCE_LABEL = "Evolve source (GitHub)"
SUITE_EVOLVE_README_GITHUB_HREF = (
    "https://github.com/rgsneddon/evolve/blob/main/README.md"
)
SUITE_PERCCENT_WALLET_HREF = "https://github.com/rgsneddon/perccent-wallet"
SUITE_PERCCENT_WALLET_LABEL = "Perccent wallet (GitHub)"
SUITE_PERCCENT_WALLET_README_HREF = (
    "https://github.com/rgsneddon/perccent-wallet/blob/main/README.md"
)
SUITE_PERCCENT_WALLET_README_LABEL = "Perccent wallet README"

# Suite ecosystem product family — rpOS opens on-site README (same-origin)
SUITE_RPOS_HREF = "/RPOS.md"
SUITE_RPOS_LABEL = "rpOS"
SUITE_RPOS_TITLE = "Restore Privacy Operating System"
SUITE_RPOS_KEY = "rpos"
# Same-origin Rx Privacy Browser README (not a bare # placeholder).
SUITE_RX_BROWSER_HREF = "/RX.md"
SUITE_RX_BROWSER_LABEL = "Rx Privacy Browser"
SUITE_RX_BROWSER_KEY = "rx-privacy-browser"
# Same-origin monorepo / product README (residual Suite + Connect docs).
SUITE_ECOSYSTEM_VPN_HREF = "/README.md"
SUITE_ECOSYSTEM_VPN_LABEL = "VPN"
SUITE_ECOSYSTEM_VPN_KEY = "suite-vpn"

# Full business package / residual node host (commercial deposit path via Service).
# Primary doc is status-host /NODE_OPERATOR.md (public pack), not Suite README.
NODE_PREFERENCE_SECTION_ID = "download-node-preference"
NODE_OPERATOR_DOCS_HREF = "/NODE_OPERATOR.md"
NODE_OPERATOR_DOCS_LABEL = "Residual node / operator path"
NODE_OPERATOR_DOCS_ALIAS_HREF = "/node-operator"
# Public open Suite Pages (client storefront docs only — no /admin).
NODE_PUBLIC_SUITE_PAGES_HREF = "https://rgsneddon.github.io/restore-privacy-suite/"
NODE_PUBLIC_SUITE_PAGES_LABEL = "Public Suite Pages (client docs)"
NODE_PUBLIC_SUITE_SOURCE_HREF = "https://github.com/rgsneddon/restore-privacy-suite"
NODE_PUBLIC_SUITE_SOURCE_LABEL = "Public Suite source (GitHub)"
# Commercial deposit cart (same one-time £3000 Stripe path as /service).
try:
    from payments import (
        COMMERCIAL_SUITE_CHECKOUT_PATH as _COMMERCIAL_CHECKOUT,
        COMMERCIAL_SUITE_NODE_PRICE_LABEL as _COMMERCIAL_PRICE,
        COMMERCIAL_SUITE_NODE_PRICE_PENCE as _COMMERCIAL_PENCE,
        COMMERCIAL_SUITE_PRODUCT_KEY as _COMMERCIAL_KEY,
        COMMERCIAL_SUITE_PRODUCT_LINE as _COMMERCIAL_LINE,
    )
except ImportError:  # pragma: no cover
    try:
        from status_page.payments import (  # type: ignore
            COMMERCIAL_SUITE_CHECKOUT_PATH as _COMMERCIAL_CHECKOUT,
            COMMERCIAL_SUITE_NODE_PRICE_LABEL as _COMMERCIAL_PRICE,
            COMMERCIAL_SUITE_NODE_PRICE_PENCE as _COMMERCIAL_PENCE,
            COMMERCIAL_SUITE_PRODUCT_KEY as _COMMERCIAL_KEY,
            COMMERCIAL_SUITE_PRODUCT_LINE as _COMMERCIAL_LINE,
        )
    except ImportError:  # pragma: no cover
        _COMMERCIAL_CHECKOUT = "/pay/commercial-suite"
        _COMMERCIAL_PRICE = "£3000"
        _COMMERCIAL_PENCE = 300_000
        _COMMERCIAL_KEY = "commercial_suite_node"
        _COMMERCIAL_LINE = "commercial_suite"

NODE_PREFERENCE_COMMERCIAL_HREF = "/service"
NODE_PREFERENCE_COMMERCIAL_CHECKOUT = _COMMERCIAL_CHECKOUT
NODE_PREFERENCE_DEPOSIT_LABEL = _COMMERCIAL_PRICE
NODE_PREFERENCE_DEPOSIT_PENCE = int(_COMMERCIAL_PENCE)
NODE_PREFERENCE_PRODUCT_KEY = _COMMERCIAL_KEY
NODE_PREFERENCE_PRODUCT_LINE = _COMMERCIAL_LINE

NODE_PREFERENCE_HEADING = "Full business package? (£3000 deposit required)"
# HTML blurb — human cadence; £3000 is a deposit to start the work (not final total).
NODE_PREFERENCE_BLURB = (
    "Run a residual node on your own server, or arrange a dedicated host through "
    "<strong>Raskul</strong>. This is the full business package: on-site network "
    "tasks, mainframe establishment, and deploy of <strong>Restore Privacy "
    "Operating System</strong> (rpOS) and the matching Suite parts — with a "
    "user-friendly interface and everyday business apps. "
    f"Prices start with a <strong>{NODE_PREFERENCE_DEPOSIT_LABEL} deposit</strong> "
    "to do the work (that payment is a deposit, not the finished all-in price). "
    "<em>Costs may be higher</em> once scope, on-site work, and hardware are "
    "agreed — we confirm anything beyond the deposit before further work."
)
NODE_PREFERENCE_DEPOSIT_CTA = (
    f"Pay {NODE_PREFERENCE_DEPOSIT_LABEL} deposit — begin the work (one-time)"
)
NODE_PREFERENCE_DEPOSIT_NOTE = (
    f"The {NODE_PREFERENCE_DEPOSIT_LABEL} is a <strong>deposit to do the work</strong>, "
    "not a fixed final quote. Further costs are agreed before they are billed."
)


def suite_free_download_href(platform: str) -> str:
    """Relative free-download URL for a Suite platform installer (KEYGEN-gated)."""
    plat = (platform or "").strip().lower()
    if not plat:
        return DOWNLOADS_MAP_PATH
    return f"{SUITE_FREE_DOWNLOAD_PATH}?platform={plat}"


def suite_pay_href(platform: str = "", *, product: str = SUITE_PAY_PRODUCT) -> str:
    """Stripe /pay entry for Suite package with optional platform preselect."""
    plat = (platform or "").strip().lower()
    prod = (product or SUITE_PAY_PRODUCT).strip() or SUITE_PAY_PRODUCT
    q: dict[str, str] = {"product": prod}
    if plat:
        q["platform"] = plat
    return f"{SUITE_PAY_PATH}?{urllib.parse.urlencode(q)}"


def suite_free_direct_download_href(platform: str) -> str:
    """Anonymous free-CTA download for latest Suite on *platform* (no /pay)."""
    plat = (platform or "").strip().lower()
    if not plat:
        return DOWNLOADS_MAP_PATH
    known = {a.platform for a in available_downloads()}
    if plat not in known:
        return DOWNLOADS_MAP_PATH
    return (
        f"{SUITE_FREE_DOWNLOAD_PATH}?platform={plat}"
        f"&{SUITE_FREE_DIRECT_QUERY}=1"
    )


def free_asset_href(filename: str, *, version: str | None = None) -> str:
    """Relative free-open path for a staged brand/catalog basename."""
    ver = (version or RELEASE_VERSION).strip() or RELEASE_VERSION
    fname = (filename or "").strip()
    if not fname:
        return DOWNLOADS_MAP_PATH
    return f"/assets/{ver}/{fname}"


def freebie_img_src() -> str:
    """Cache-busted freebie button image (static freebie.jpg)."""
    try:
        from public_chrome import public_brand_asset_version
    except ImportError:  # pragma: no cover
        try:
            from status_page.public_chrome import (  # type: ignore
                public_brand_asset_version,
            )
        except ImportError:  # pragma: no cover
            return FREEBIE_IMG_PATH
    return f"{FREEBIE_IMG_PATH}?v={public_brand_asset_version()}"


# Visible FREE DOWNLOAD label (typewriter face — matches Suite intro neon mono)
FREE_DOWNLOAD_CTA_LABEL = "FREE DOWNLOAD"


def free_download_cta_css() -> str:
    """Full-width rectangular free-download button — data-path chrome + typewriter label."""
    return f"""
    .free-download-cta-wrap {{
      width: 100%; max-width: 100%; box-sizing: border-box;
      margin: 0 0 clamp(0.85rem, 2vw, 1.2rem);
    }}
    a.free-download-cta, a#{FREE_DOWNLOAD_CTA_ID} {{
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      max-width: 100%;
      min-height: clamp(3.4rem, 9vw, 4.6rem);
      box-sizing: border-box;
      margin: 0;
      padding: clamp(0.95rem, 2.8vw, 1.35rem) clamp(1rem, 3vw, 1.5rem);
      border: 1px solid transparent;
      border-radius: 12px;
      overflow: hidden;
      cursor: pointer;
      text-decoration: none;
      line-height: 1.2;
      position: relative;
      text-align: center;
      /* Data-path panel language: neon dual-tone border + navy fill */
      background:
        linear-gradient(
          165deg,
          color-mix(in srgb, var(--rb-card, #132a4a) 88%, #0a1628) 0%,
          #0a1628 55%,
          color-mix(in srgb, #0f2340 80%, #0a1628) 100%
        ) padding-box,
        linear-gradient(
          135deg,
          var(--rb-neon-cyan, #00e5ff) 0%,
          var(--rb-neon-blue, #2694e8) 42%,
          var(--rb-neon-green, #39ff6a) 100%
        ) border-box;
      background-origin: border-box;
      background-clip: padding-box, border-box;
      box-shadow:
        0 0 0 1px color-mix(in srgb, var(--rb-neon-cyan, #00e5ff) 12%, transparent),
        0 0 18px var(--rb-neon-glow-cyan, rgba(0, 229, 255, 0.22)),
        0 0 28px var(--rb-neon-glow-green, rgba(57, 255, 106, 0.14)),
        0 10px 28px rgba(4, 12, 28, 0.45),
        inset 0 1px 0 rgba(255, 255, 255, 0.06);
      transition: transform 0.08s ease, box-shadow 0.08s ease, filter 0.12s ease;
    }}
    /* Circuit motif wash (same public data-path graphic language) */
    a.free-download-cta::before {{
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      opacity: 0.22;
      background-image: url("/static/data_path_motif.svg");
      background-repeat: no-repeat;
      background-position: center right;
      background-size: min(52%, 18rem) auto;
      z-index: 0;
    }}
    a.free-download-cta::after {{
      content: none !important;
      display: none !important;
    }}
    /* No logo / freebie image face */
    a.free-download-cta img {{
      display: none !important;
    }}
    a.free-download-cta .free-download-cta-label {{
      position: relative;
      z-index: 1;
      display: block;
      width: 100%;
      margin: 0;
      padding: 0;
      /* Same typewriter family as Suite intro neon lines */
      font-family: "Courier New", Courier, ui-monospace, monospace;
      font-size: clamp(1.25rem, 3.8vw, 1.85rem);
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: #7dffe8;
      text-shadow:
        0 0 6px rgba(0, 229, 255, 0.85),
        0 0 14px rgba(57, 255, 136, 0.55),
        0 0 28px rgba(0, 229, 255, 0.35);
      white-space: normal;
      word-break: break-word;
      /* Continuous flash to draw attention to FREE DOWNLOAD */
      animation: free-download-label-blink 1.15s ease-in-out infinite;
    }}
    @keyframes free-download-label-blink {{
      0%, 100% {{
        opacity: 1;
        text-shadow:
          0 0 6px rgba(0, 229, 255, 0.85),
          0 0 14px rgba(57, 255, 136, 0.55),
          0 0 28px rgba(0, 229, 255, 0.35);
      }}
      50% {{
        opacity: 0.22;
        text-shadow:
          0 0 2px rgba(0, 229, 255, 0.25),
          0 0 6px rgba(57, 255, 136, 0.15);
      }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      a.free-download-cta .free-download-cta-label {{
        animation: none;
        opacity: 1;
      }}
    }}
    a.free-download-cta:active,
    a.free-download-cta.is-pressed,
    a.free-download-cta:focus-visible {{
      transform: scale(0.985) translateY(2px);
      box-shadow:
        0 2px 8px rgba(0,0,0,0.45) inset,
        0 0 16px var(--rb-neon-glow-cyan, rgba(0, 229, 255, 0.28));
      filter: brightness(0.96);
      outline: none;
    }}
    a.free-download-cta:hover {{
      filter: brightness(1.06);
      box-shadow:
        0 0 0 1px color-mix(in srgb, var(--rb-neon-green, #39ff6a) 22%, transparent),
        0 0 22px var(--rb-neon-glow-cyan, rgba(0, 229, 255, 0.28)),
        0 0 32px var(--rb-neon-glow-green, rgba(57, 255, 106, 0.18)),
        0 12px 30px rgba(4, 12, 28, 0.5);
    }}
"""


def free_download_cta_href(*, default_platform: str = "") -> str:
    """Free CTA: direct latest Suite installer for detected device (no /pay, no picker).

    Unknown device → Downloads Map (Suite-latest pay rows only); never a platform
    picker on the free button itself.
    """
    def_plat = (default_platform or "").strip().lower()
    known = {a.platform for a in available_downloads()}
    if def_plat and def_plat in known:
        return suite_free_direct_download_href(def_plat)
    return DOWNLOADS_MAP_PATH


def render_free_download_cta_html(
    *,
    version: str = "",
    default_platform: str = "",
) -> str:
    """Full-width rectangular FREE DOWNLOAD button (text + data-path chrome, no logo face).

    When *default_platform* is a known catalog OS (from User-Agent), the button
    starts an **immediate** latest Suite download for that device (no /pay).
    Unknown/empty → Downloads Map (Suite latest via /pay only).
    """
    ver = (version or FREE_DOWNLOAD_FACE_VERSION).strip() or FREE_DOWNLOAD_FACE_VERSION
    def_plat = (default_platform or "").strip().lower()
    known = {a.platform for a in available_downloads()}
    if def_plat and def_plat not in known:
        def_plat = ""
    href = free_download_cta_href(default_platform=def_plat)
    if def_plat:
        title = platform_face_title(def_plat)
        aria = (
            f"FREE DOWNLOAD — latest Restore Privacy Suite for {title} "
            f"(v{ver}, no payment)"
        )
        detect_attrs = (
            f' data-platform="{_esc_html(def_plat)}"'
            f' data-detected-platform="{_esc_html(def_plat)}"'
        )
        href_kind = "suite_free_direct"
        pay_attr = ' data-pay="0" data-free-direct="1"'
    else:
        aria = (
            "FREE DOWNLOAD — open Downloads Map for Restore Privacy Suite "
            f"v{ver} (device not detected)"
        )
        detect_attrs = ' data-fallback-map="1"'
        href_kind = "map"
        pay_attr = ' data-pay="0"'
    label = FREE_DOWNLOAD_CTA_LABEL
    return f"""
    <div class="free-download-cta-wrap" id="free-download-cta-wrap"
         data-free-download-cta="1" data-face-version="{_esc_html(ver)}"
         data-catalog-version="{_esc_html(RELEASE_VERSION)}"
         data-cta-shape="rectangle" data-cta-face="typewriter"
         data-suite-latest="1"{detect_attrs}>
      <a class="free-download-cta free-download-cta-rect neon-type" id="{FREE_DOWNLOAD_CTA_ID}"
         href="{_esc_html(href)}" data-free-download-v1="1"
         data-version="{_esc_html(ver)}" data-href-kind="{href_kind}"
         data-cta-shape="rectangle" data-cta-face="typewriter"
         data-suite-latest="1"{pay_attr}
         {detect_attrs}
         aria-label="{_esc_html(aria)}">
        <span class="free-download-cta-label">{_esc_html(label)}</span>
      </a>
    </div>
"""


def free_packages_page_css() -> str:
    """Legacy alias — Downloads Map styles."""
    return downloads_map_page_css()


def downloads_map_page_css() -> str:
    """Downloads Map: grouped product → platform installer links."""
    return """
    .downloads-map-page, .free-packages-page {
      min-height: 70vh; display: flex; flex-direction: column;
      align-items: stretch; justify-content: flex-start;
      text-align: left; position: relative; width: 100%;
      box-sizing: border-box; padding: 1.5rem 1rem 3rem;
    }
    .downloads-map-page .downloads-map-center,
    .free-packages-page .free-packages-center {
      width: min(100%, 42rem); margin: 0 auto; z-index: 2;
      padding: 1rem 0.5rem 2rem;
    }
    .downloads-map-page h1, .free-packages-page h1 {
      margin: 0 0 0.5rem; font-size: clamp(1.2rem, 3.5vw, 1.65rem);
      letter-spacing: 0.04em; color: #e8f2ff; font-weight: 800;
      text-align: center;
    }
    .downloads-map-page .downloads-map-blurb,
    .free-packages-page .free-packages-blurb {
      margin: 0 0 1.25rem; font-size: 0.92rem; line-height: 1.45;
      color: #aed0ea; font-weight: 600; text-align: center;
    }
    .downloads-map-section {
      margin: 0 0 1.35rem; padding: 0.85rem 0.9rem 1rem;
      border: 1px solid rgba(174, 208, 234, 0.28);
      border-radius: 12px; background: rgba(10, 22, 40, 0.55);
    }
    .downloads-map-section h2 {
      margin: 0 0 0.55rem; font-size: 1.02rem; font-weight: 800;
      color: #dbeafe; letter-spacing: 0.03em;
    }
    .downloads-map-section .downloads-map-list,
    .free-packages-page .free-packages-list {
      list-style: none; margin: 0; padding: 0;
      display: flex; flex-direction: column; gap: 0.55rem;
      align-items: stretch;
    }
    .downloads-map-page a.downloads-map-link,
    .free-packages-page a.free-package-link {
      display: block; font-size: clamp(0.92rem, 2.4vw, 1.08rem);
      font-weight: 700; text-decoration: none;
      color: #ff7a18;
      text-shadow: 0 0 10px rgba(255, 122, 24, 0.28);
      padding: 0.3rem 0.15rem;
      border-bottom: 1px solid rgba(255, 122, 24, 0.35);
      word-break: break-word;
    }
    .downloads-map-page a.downloads-map-link:hover,
    .free-packages-page a.free-package-link:hover {
      color: #ff9a4a; border-bottom-color: #ff9a4a;
    }
    .downloads-map-page a.downloads-map-link.is-detected,
    .free-packages-page a.free-package-link.is-detected {
      color: #ffb347; border-bottom-color: #ffb347;
    }
    .downloads-map-page .downloads-map-detect-hint,
    .free-packages-page .free-packages-detect-hint {
      margin: 0 0 1rem; font-size: 0.9rem; line-height: 1.4;
      color: #c8e0f5; font-weight: 600; text-align: center;
    }
    .downloads-map-page .downloads-map-back,
    .free-packages-page .free-packages-back {
      margin-top: 1.5rem; font-size: 0.85rem; text-align: center;
    }
    .downloads-map-page .downloads-map-back a,
    .free-packages-page .free-packages-back a {
      color: #93c5fd; font-weight: 700; text-decoration: none;
    }
"""


def list_downloads_map_rows(
    *, version: str | None = None
) -> list[dict[str, str]]:
    """Downloads Map rows: Restore Privacy Suite latest clients only → /pay.

    Each row is one Suite monopin platform at *version* (default RELEASE_VERSION).
    Non-Suite products are not listed.
    """
    ver = (version or RELEASE_VERSION).strip() or RELEASE_VERSION
    rows: list[dict[str, str]] = []
    for p in list_catalog_platform_packages(version=ver):
        plat = str(p.get("platform") or "")
        fname = str(p.get("filename") or "")
        rows.append(
            {
                "product": "Restore Privacy Suite",
                "kind": "suite_client",
                "platform": plat,
                "filename": fname,
                "href": suite_pay_href(plat),
                "version": ver,
                "label": f"{platform_face_title(plat)} — Suite v{ver}",
            }
        )
    return rows


def downloads_map_products(
    rows: list[dict[str, str]] | None = None,
) -> list[tuple[str, list[dict[str, str]]]]:
    """Group map rows by product (stable order)."""
    items = rows if rows is not None else list_downloads_map_rows()
    order: list[str] = []
    groups: dict[str, list[dict[str, str]]] = {}
    for r in items:
        prod = str(r.get("product") or "Other")
        if prod not in groups:
            groups[prod] = []
            order.append(prod)
        groups[prod].append(r)
    return [(p, groups[p]) for p in order]


def render_free_packages_page_html(
    *,
    version: str = "",
    default_platform: str = "",
) -> bytes:
    """Back-compat alias: free-packages hub is the Downloads Map."""
    return render_downloads_map_page_html(
        version=version, default_platform=default_platform
    )


def render_downloads_map_page_html(
    *,
    version: str = "",
    default_platform: str = "",
) -> bytes:
    """Downloads Map: every brand inventory installer, per platform.

    *default_platform* (User-Agent OS) highlights matching Suite client links.
    """
    ver = (version or RELEASE_VERSION).strip() or RELEASE_VERSION
    def_plat = (default_platform or "").strip().lower()
    known = {a.platform for a in available_downloads()}
    if def_plat and def_plat not in known:
        def_plat = ""
    sections_html: list[str] = []
    for product, rows in downloads_map_products():
        links: list[str] = []
        for r in rows:
            plat = str(r.get("platform") or "")
            href = str(r.get("href") or "")
            label = str(r.get("label") or r.get("filename") or plat)
            fname = str(r.get("filename") or "")
            kind = str(r.get("kind") or "")
            is_det = (
                " is-detected"
                if def_plat
                and kind == "suite_client"
                and plat == def_plat
                else ""
            )
            det_attr = ' data-detected-platform="1"' if is_det else ""
            pid = f"map-{kind}-{plat}-{fname}"[:80]
            links.append(
                f'<li><a class="downloads-map-link free-package-link{_esc_html(is_det)}" '
                f'id="{_esc_html(pid)}" '
                f'href="{_esc_html(href)}" data-platform="{_esc_html(plat)}" '
                f'data-filename="{_esc_html(fname)}" data-product="{_esc_html(product)}" '
                f'data-kind="{_esc_html(kind)}" data-map-package="1"{det_attr}>'
                f"{_esc_html(label)}</a></li>"
            )
        list_body = "\n          ".join(links) if links else (
            "<li><p class=\"downloads-map-blurb\">No packages in this group.</p></li>"
        )
        sec_id = "map-sec-" + "".join(
            ch if ch.isalnum() else "-" for ch in product.lower()
        )[:48]
        sections_html.append(
            f'<section class="downloads-map-section" id="{_esc_html(sec_id)}" '
            f'data-map-product="{_esc_html(product)}">'
            f"<h2>{_esc_html(product)}</h2>"
            f'<ul class="downloads-map-list free-packages-list" data-free-packages="1">'
            f"\n          {list_body}\n        </ul></section>"
        )
    sections = "\n      ".join(sections_html) if sections_html else (
        '<p class="downloads-map-blurb">No packages listed for this pin.</p>'
    )
    if def_plat:
        face = platform_face_title(def_plat)
        detect_hint = (
            f'<p class="downloads-map-detect-hint free-packages-detect-hint" '
            f'id="downloads-map-detect-hint" '
            f'data-detected-platform="{_esc_html(def_plat)}">'
            f"Detected your device as <strong>{_esc_html(face)}</strong> — "
            f"Suite v{_esc_html(ver)} /pay link highlighted; all Suite platforms below.</p>"
        )
        detect_main_attr = f' data-detected-platform="{_esc_html(def_plat)}"'
    else:
        detect_hint = ""
        detect_main_attr = ""
    try:
        from public_chrome import (
            public_brand_header_html,
            public_data_path_layer_html,
            public_head_open,
            public_page_close,
            public_site_css,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            public_brand_header_html,
            public_data_path_layer_html,
            public_head_open,
            public_page_close,
            public_site_css,
        )

    extra_css = public_site_css() + downloads_map_page_css()
    header = public_brand_header_html(active="home", product_active="vpn")
    motif = public_data_path_layer_html()
    body = f"""{public_head_open(title=f"Downloads Map · Suite {ver}", extra_css=extra_css)}
{motif}
  <div class="page-shell" id="page-shell" data-page="downloads-map"
       data-product="suite" data-suite-version="{_esc_html(ver)}" data-chrome="pro">
{header}
    <main class="downloads-map-page free-packages-page panel-card"
          id="{DOWNLOADS_MAP_PAGE_ID}" data-downloads-map-page="1"
          data-free-packages-page="1" data-version="{_esc_html(ver)}"
          aria-label="Downloads Map — Restore Privacy Suite latest only"{detect_main_attr}>
      <div class="downloads-map-center free-packages-center" id="downloads-map-center">
        <h1 id="downloads-map-heading">Downloads Map</h1>
        <p class="downloads-map-blurb free-packages-blurb" id="downloads-map-blurb">
          <strong>Restore Privacy Suite v{_esc_html(ver)}</strong> only — one link
          per device platform (no companion products). Each link opens the
          <a href="/pay?product=suite">/pay</a> flow (Stripe KEYGEN) so you can
          confirm or change platform before checkout.
          For an immediate free Suite download matched to this device, use the
          home <strong>FREE DOWNLOAD</strong> button.
        </p>
        {detect_hint}
        {sections}
        <p class="downloads-map-back free-packages-back">
          <a href="/#free-download-cta-wrap">Back to home</a>
        </p>
      </div>
    </main>
  </div>
{public_page_close()}
"""
    return body.encode("utf-8")


def suite_product_submenu_links() -> list[tuple[str, str, str, str]]:
    """(href, label, data-key, title) for Suite ecosystem submenu.

    *title* is optional expanded meaning (e.g. rpOS → Restore Privacy Operating
    System) for ``title`` / ``aria-label``; empty string when label is enough.
    """
    return [
        (SUITE_RPOS_HREF, SUITE_RPOS_LABEL, SUITE_RPOS_KEY, SUITE_RPOS_TITLE),
        (
            SUITE_RX_BROWSER_HREF,
            SUITE_RX_BROWSER_LABEL,
            SUITE_RX_BROWSER_KEY,
            SUITE_RX_BROWSER_LABEL,
        ),
        (
            SUITE_ECOSYSTEM_VPN_HREF,
            SUITE_ECOSYSTEM_VPN_LABEL,
            SUITE_ECOSYSTEM_VPN_KEY,
            "Restore Privacy residual VPN / Connect",
        ),
        (SUITE_PERC_EXPLORER_HREF, SUITE_PERC_EXPLORER_LABEL, "perc-explorer", ""),
        (SUITE_EVOLVE_DOCS_HREF, SUITE_EVOLVE_DOCS_LABEL, "evolve-docs", ""),
        (
            SUITE_EVOLVE_WHITEPAPER_HREF,
            SUITE_EVOLVE_WHITEPAPER_LABEL,
            "evolve-whitepaper",
            "",
        ),
        (SUITE_EVOLVE_SOURCE_HREF, SUITE_EVOLVE_SOURCE_LABEL, "evolve-source", ""),
        (SUITE_PERCCENT_WALLET_HREF, SUITE_PERCCENT_WALLET_LABEL, "perccent-wallet", ""),
        (
            SUITE_PERCCENT_WALLET_README_HREF,
            SUITE_PERCCENT_WALLET_README_LABEL,
            "perccent-readme",
            "",
        ),
    ]


def render_suite_product_submenu_html() -> str:
    """Sub-menu: product family (rpOS / browser / VPN) + Perc / Evolve / wallet."""
    items: list[str] = []
    for href, label, key, title in suite_product_submenu_links():
        external = href.startswith("http://") or href.startswith("https://")
        target_rel = (
            ' target="_blank" rel="noopener noreferrer"' if external else ""
        )
        title_attr = ""
        aria = _esc_html(label)
        if title and title != label:
            title_attr = f' title="{_esc_html(title)}"'
            aria = _esc_html(title)
        items.append(
            f'<a class="suite-sub-link" id="suite-sub-{_esc_html(key)}" '
            f'href="{_esc_html(href)}" data-suite-sub="{_esc_html(key)}" '
            f'aria-label="{aria}"{title_attr}{target_rel}>'
            f"{_esc_html(label)}</a>"
        )
    return f"""
    <nav class="suite-product-submenu" id="{SUITE_SUBMENU_ID}"
         data-suite-product-submenu="1"
         aria-label="Suite ecosystem — rpOS, Rx Privacy Browser, VPN, Perc, Evolve">
      <p class="suite-product-submenu-label" id="suite-product-submenu-label">
        Suite ecosystem
      </p>
      {" ".join(items)}
    </nav>
"""


def render_suite_perc_wallet_explorer_iframe_html() -> str:
    """Iframe the live Perccent block explorer into the Suite storefront.

    Uses :data:`SUITE_PERC_EXPLORER_HREF` (Helsinki public ``/perc/`` base) so
    the framed document's ``location.pathname`` is under ``/perc/`` and the
    explorer's :func:`explorerApiBase` prefixes API calls to ``/perc/api/…``.
    Trailing slash is required. Load is eager so first homepage visit connects
    without requiring a top-level open of the external explorer link.
    """
    src_href = SUITE_PERC_WALLET_EXPLORER_IFRAME_SRC
    if not src_href.endswith("/"):
        src_href = src_href.rstrip("/") + "/"
    # Host for CSP / data markers (no path).
    try:
        from urllib.parse import urlparse

        host = urlparse(src_href).netloc or "135.181.152.10.sslip.io"
    except Exception:  # noqa: BLE001
        host = "135.181.152.10.sslip.io"
    return f"""
    <div class="suite-perc-wallet-explorer" id="{SUITE_PERC_WALLET_EXPLORER_ID}"
         data-suite-perc-wallet-explorer="1" data-product="perccent-wallet"
         data-explorer-host="{_esc_html(host)}" data-explorer-iframe-wrap="1">
      <p class="suite-perc-wallet-explorer-label"
         id="suite-perc-wallet-explorer-label">
        {_esc_html(SUITE_PERC_WALLET_EXPLORER_LABEL)}
      </p>
      <div class="suite-perc-wallet-explorer-frame-wrap"
           id="suite-perc-wallet-explorer-frame-wrap">
        <iframe class="suite-perc-wallet-explorer-frame"
                id="{SUITE_PERC_WALLET_EXPLORER_IFRAME_ID}"
                src="{_esc_html(src_href)}"
                title="Perccent Network Explorer — Chronoflux Principia chain"
                loading="eager"
                referrerpolicy="no-referrer-when-downgrade"
                allow="fullscreen"
                sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-popups-to-escape-sandbox"
                data-explorer-iframe="1"
                data-src-host="{_esc_html(host)}"
                data-src-path="/perc/"></iframe>
      </div>
      <p class="suite-perc-wallet-explorer-open">
        <a class="suite-sub-link" id="suite-perc-wallet-explorer-open"
           href="{_esc_html(src_href)}" target="_blank" rel="noopener noreferrer"
           data-suite-sub="perc-wallet-explorer-open">
          Open block explorer full page
        </a>
      </p>
    </div>
"""


def suite_storefront_css() -> str:
    """CSS for the Suite storefront card (above VPN downloads)."""
    return """
    .suite-storefront {
      width: 100%; text-align: center; box-sizing: border-box;
      margin: 0 0 1.25rem;
      border: 1px solid rgba(174, 208, 234, 0.45);
      background:
        linear-gradient(165deg, rgba(30, 80, 140, 0.55) 0%, rgba(10, 22, 40, 0.92) 70%);
      box-shadow: 0 10px 28px rgba(4, 12, 28, 0.4), inset 0 1px 0 rgba(255,255,255,0.08);
    }
    .suite-storefront h2 {
      font-size: clamp(1.05rem, 2.8vw, 1.35rem);
      letter-spacing: 0.06em; font-weight: 800;
      margin: 0 0 0.35rem; color: #ffffff;
      text-transform: uppercase;
    }
    .suite-storefront .suite-version-badge {
      display: inline-block; margin: 0 0 0.65rem;
      padding: 0.2rem 0.65rem; border-radius: 999px;
      font-size: 0.78rem; font-weight: 700; letter-spacing: 0.04em;
      color: #0a1628; background: #aed0ea;
    }
    .suite-storefront .suite-blurb {
      margin: 0 auto 0.85rem; max-width: 36rem;
      font-size: clamp(0.88rem, 2.1vw, 1rem);
      line-height: 1.45; color: #dbeafe; font-weight: 600;
    }
    .suite-storefront .suite-keygen-line {
      margin: 0 auto 1rem; max-width: 34rem;
      font-size: 0.92rem; line-height: 1.45; color: #fecaca; font-weight: 700;
    }
    .suite-product-submenu {
      display: flex; flex-wrap: wrap; gap: 0.4rem; justify-content: center;
      margin: 0.35rem auto 0.85rem; max-width: 36rem; padding: 0;
      list-style: none;
    }
    /* Neon-gradient underline menu (not filled pill/box chips) */
    .suite-product-submenu a,
    .suite-product-submenu a.suite-sub-link {
      display: inline-block; padding: 0.28rem 0.35rem 0.4rem;
      margin: 0 0.15rem 0.2rem; border-radius: 0;
      font-size: 0.78rem; font-weight: 700; text-decoration: none;
      color: #e8f2ff; background: transparent; border: 0;
      letter-spacing: 0.03em;
      border-bottom: 2px solid transparent;
      background-image: none;
      transition: color 0.12s ease, border-color 0.12s ease, filter 0.12s ease;
    }
    .suite-product-submenu a:hover,
    .suite-product-submenu a:focus-visible,
    .suite-product-submenu a.is-active {
      color: #ffffff;
      /* Brand neon underline: cyan → blue → green (matches site chrome) */
      border-bottom: 2px solid transparent;
      border-image: linear-gradient(
        90deg,
        #00e5ff 0%,
        #2694e8 42%,
        #39ff6a 100%
      ) 1;
      filter: brightness(1.06);
      background: transparent;
      outline: none;
    }
    .suite-product-submenu-label {
      width: 100%; margin: 0 0 0.35rem; font-size: 0.72rem; font-weight: 700;
      letter-spacing: 0.06em; text-transform: uppercase; color: rgba(174,208,234,0.9);
    }
    /* Perccent explorer embed — forces connect on first homepage visit */
    .suite-perc-wallet-explorer {
      width: 100%; max-width: 100%; box-sizing: border-box;
      margin: 0.75rem 0 1rem; text-align: left;
    }
    .suite-perc-wallet-explorer-label {
      margin: 0 0 0.4rem; font-size: 0.82rem; font-weight: 700;
      color: #dbeafe; letter-spacing: 0.03em;
    }
    .suite-perc-wallet-explorer-frame-wrap {
      width: 100%; box-sizing: border-box; border-radius: 12px; overflow: hidden;
      border: 1px solid rgba(174, 208, 234, 0.4);
      background: rgba(4, 12, 28, 0.55); min-height: 22rem;
    }
    .suite-perc-wallet-explorer-frame,
    iframe#suite-perc-wallet-explorer-frame {
      display: block; width: 100%; height: min(70vh, 36rem);
      min-height: 22rem; border: 0; background: #0a1628;
    }
    .suite-perc-wallet-explorer-open {
      margin: 0.45rem 0 0; text-align: center; font-size: 0.8rem;
    }
    .suite-free-primary {
      margin: 0.35rem auto 0.65rem; max-width: 28rem; text-align: center;
    }
    .suite-free-primary a.suite-dl-primary {
      display: inline-block; width: 100%; max-width: 22rem; box-sizing: border-box;
      padding: 0.85rem 1.1rem; border-radius: 12px; font-weight: 800; font-size: 1.02rem;
      text-decoration: none; color: #0a1628; background: #7dd3fc;
      border: 2px solid rgba(255,255,255,0.45);
      box-shadow: 0 6px 18px rgba(0, 120, 200, 0.35);
    }
    .suite-free-primary a.suite-dl-primary:hover { background: #bae6fd; }
    .suite-detect-hint {
      margin: 0.45rem auto 0; max-width: 28rem; font-size: 0.78rem;
      color: rgba(174, 208, 234, 0.95); line-height: 1.35;
    }
    .suite-free-grid {
      display: flex; flex-wrap: wrap; gap: 0.65rem; justify-content: center;
      margin: 0.5rem auto 1rem; max-width: 40rem;
    }
    .suite-free-grid a.suite-dl {
      display: inline-block; min-width: 8.5rem; padding: 0.65rem 0.9rem;
      border-radius: 12px; font-weight: 700; font-size: 0.92rem;
      text-decoration: none; color: #0a1628; background: #aed0ea;
      border: 1px solid rgba(255,255,255,0.25);
    }
    .suite-free-grid a.suite-dl:hover { background: #c5e0f4; }
    .suite-free-grid a.suite-dl.is-detected {
      outline: 2px solid #7dd3fc; outline-offset: 2px;
      background: #bae6fd;
    }
    .suite-keygen-cta {
      margin: 0.35rem auto 0.25rem; max-width: 28rem;
    }
    .suite-keygen-cta .dl-buy-now {
      width: 100%; max-width: 22rem;
    }
    .suite-storefront .suite-pay-hint {
      margin: 0.75rem auto 0; max-width: 34rem;
      font-size: 0.82rem; color: rgba(174, 208, 234, 0.95); line-height: 1.4;
    }
    /* World flags strip — bottom of right-hand downloads (#downloads) box */
    .downloads .suite-world-flags,
    .suite-world-flags {
      display: flex; flex-wrap: wrap; gap: 1px; justify-content: center;
      align-content: flex-start;
      margin: 0.55rem 0 0; padding: 0.3rem 0.1rem 0.1rem;
      /* Compact density so full pack fits the leftover bottom without huge card growth */
      max-height: 6.5rem; overflow-y: auto; overflow-x: hidden;
      border-top: 1px solid rgba(174, 208, 234, 0.25);
      width: 100%; box-sizing: border-box;
      scrollbar-width: thin;
    }
    .downloads .suite-world-flags img.suite-world-flag,
    .suite-world-flags img.suite-world-flag {
      width: 12px; height: 9px; object-fit: cover;
      border-radius: 1px; flex: 0 0 auto;
      display: block; opacity: 0.9;
    }
    /* Full business package / commercial deposit (standalone home box) */
    .download-node-preference {
      margin: 0 auto clamp(0.95rem, 2.2vw, 1.35rem);
      max-width: min(42rem, 100%);
      width: 100%;
      padding: 0.85rem 1rem;
      text-align: center; box-sizing: border-box;
      border: 1px dashed rgba(174, 208, 234, 0.4);
      border-radius: 12px;
      /* Transparent fill so page background / motif shows through */
      background: rgba(8, 18, 32, 0.18);
    }
    /* Homepage placement: span full content column (not the narrow 42rem card). */
    .download-node-preference.home-business-package {
      display: block;
      width: 100%;
      max-width: 100%;
      margin-left: 0;
      margin-right: 0;
      box-sizing: border-box;
    }
    .download-node-preference h3 {
      margin: 0 0 0.45rem; font-size: 0.92rem; font-weight: 800;
      letter-spacing: 0.04em; color: #e8eef5; text-transform: none;
    }
    .download-node-preference .node-pref-blurb {
      margin: 0 auto 0.65rem; max-width: 34rem;
      font-size: 0.82rem; line-height: 1.45; color: rgba(174, 208, 234, 0.95);
      font-weight: 500;
    }
    .download-node-preference .node-pref-deposit-note {
      margin: 0 auto 0.65rem; max-width: 32rem;
      font-size: 0.78rem; line-height: 1.4; color: #fde68a; font-weight: 600;
    }
    .download-node-preference .node-pref-deposit-form {
      margin: 0.35rem auto 0.75rem; max-width: 22rem;
      display: flex; flex-direction: column; gap: 0.4rem; align-items: stretch;
    }
    .download-node-preference button.node-pref-deposit-btn,
    .download-node-preference a.node-pref-deposit-link {
      display: inline-block; width: 100%; max-width: 100%; box-sizing: border-box;
      margin: 0; padding: 0.7rem 0.9rem; border: 0; border-radius: 12px;
      cursor: pointer; font: 800 0.88rem/1.25 system-ui, sans-serif;
      letter-spacing: 0.03em; text-decoration: none; text-align: center;
      color: #041018;
      background: linear-gradient(180deg, #fde68a, #f59e0b 55%, #d97706);
      box-shadow: 0 6px 16px rgba(217, 119, 6, 0.35);
    }
    .download-node-preference button.node-pref-deposit-btn:hover,
    .download-node-preference a.node-pref-deposit-link:hover {
      filter: brightness(1.05);
    }
    .download-node-preference .node-pref-links {
      display: flex; flex-wrap: wrap; gap: 0.45rem; justify-content: center;
      margin: 0;
    }
    .download-node-preference a.node-pref-link {
      display: inline-block; padding: 0.4rem 0.7rem; border-radius: 999px;
      font-size: 0.78rem; font-weight: 700; text-decoration: none;
      color: #0a1628; background: #aed0ea;
      border: 1px solid rgba(255,255,255,0.2);
    }
    .download-node-preference a.node-pref-link:hover { background: #c5e0f4; }
    .downloads .download-node-preference {
      margin-top: 1.1rem;
    }
"""


def render_node_preference_html(*, standalone: bool = True) -> str:
    """Full business package block: residual node / Raskul host + £3000 deposit.

    Primary copy is commercial deposit framing (not KEYGEN client preference).
    £3000 control posts into the same commercial Stripe checkout as /service.

    When *standalone* is True (homepage placement above the Node data clear
    timer), adds ``home-business-package`` for full-width layout styling.
    """
    links = [
        (NODE_OPERATOR_DOCS_HREF, NODE_OPERATOR_DOCS_LABEL, "node-docs"),
        (NODE_OPERATOR_DOCS_ALIAS_HREF, "Node operator (short path)", "node-docs-alias"),
        (NODE_PUBLIC_SUITE_PAGES_HREF, NODE_PUBLIC_SUITE_PAGES_LABEL, "suite-pages"),
        (NODE_PUBLIC_SUITE_SOURCE_HREF, NODE_PUBLIC_SUITE_SOURCE_LABEL, "suite-source"),
        (
            NODE_PREFERENCE_COMMERCIAL_HREF,
            "Commercial Service page",
            "commercial-service",
        ),
    ]
    anchors: list[str] = []
    for href, label, key in links:
        anchors.append(
            f'<a class="node-pref-link" id="node-pref-link-{_esc_html(key)}" '
            f'href="{_esc_html(href)}" data-node-pref-link="{_esc_html(key)}" '
            f'rel="noopener noreferrer">'
            f"{_esc_html(label)}</a>"
        )
    stand_cls = " home-business-package" if standalone else ""
    stand_attr = ' data-home-business-package="1"' if standalone else ""
    return f"""
    <aside class="download-node-preference{stand_cls}" id="{NODE_PREFERENCE_SECTION_ID}"
           data-node-preference="1" data-business-package="1"
           data-commercial-deposit="1"{stand_attr}
           data-price-pence="{NODE_PREFERENCE_DEPOSIT_PENCE}"
           aria-label="Full business package — residual node and deposit">
      <h3 id="node-pref-heading">{_esc_html(NODE_PREFERENCE_HEADING)}</h3>
      <p class="node-pref-blurb" id="node-pref-blurb">{NODE_PREFERENCE_BLURB}</p>
      <p class="node-pref-deposit-note" id="node-pref-deposit-note"
         data-deposit="1">
        {NODE_PREFERENCE_DEPOSIT_NOTE}
      </p>
      <form class="node-pref-deposit-form" id="node-pref-deposit-form"
            method="post" action="{_esc_html(NODE_PREFERENCE_COMMERCIAL_CHECKOUT)}"
            data-pay-via="commercial-suite" data-billing="one_time"
            data-product="{_esc_html(NODE_PREFERENCE_PRODUCT_KEY)}"
            data-price-pence="{NODE_PREFERENCE_DEPOSIT_PENCE}"
            data-commercial-deposit-form="1">
        <input type="hidden" name="product"
               value="{_esc_html(NODE_PREFERENCE_PRODUCT_KEY)}"/>
        <input type="hidden" name="product_line"
               value="{_esc_html(NODE_PREFERENCE_PRODUCT_LINE)}"/>
        <input type="hidden" name="billing" value="one_time"/>
        <input type="hidden" name="amount_pence"
               value="{NODE_PREFERENCE_DEPOSIT_PENCE}"/>
        <button type="submit" class="node-pref-deposit-btn"
                id="node-pref-deposit-btn"
                data-commercial-deposit="1"
                data-price-pence="{NODE_PREFERENCE_DEPOSIT_PENCE}">
          {_esc_html(NODE_PREFERENCE_DEPOSIT_CTA)}
        </button>
      </form>
      <p class="node-pref-deposit-note" id="node-pref-deposit-service-link">
        <a class="node-pref-deposit-link" id="node-pref-deposit-service"
           href="{_esc_html(NODE_PREFERENCE_COMMERCIAL_HREF)}"
           data-commercial-deposit-link="1"
           data-price-label="{_esc_html(NODE_PREFERENCE_DEPOSIT_LABEL)}">
          {_esc_html(NODE_PREFERENCE_DEPOSIT_LABEL)} deposit details on Service →
        </a>
      </p>
      <div class="node-pref-links" id="node-pref-links" data-node-pref-links="1">
        {" ".join(anchors)}
      </div>
    </aside>
"""


def world_flag_codes() -> tuple[str, ...]:
    """Shipped flag codes (ISO alpha-2 + UK home-nation extras)."""
    try:
        from world_flag_codes import WORLD_FLAG_CODES
    except ImportError:  # pragma: no cover
        try:
            from status_page.world_flag_codes import WORLD_FLAG_CODES  # type: ignore
        except ImportError:  # pragma: no cover
            return ()
    return tuple(WORLD_FLAG_CODES)


def world_flag_title(code: str) -> str:
    """Human title for a flag code (home nations get full names)."""
    cc = (code or "").strip().lower()
    try:
        from world_flag_codes import UK_HOME_NATION_TITLES
    except ImportError:  # pragma: no cover
        try:
            from status_page.world_flag_codes import UK_HOME_NATION_TITLES  # type: ignore
        except ImportError:  # pragma: no cover
            UK_HOME_NATION_TITLES = {}  # type: ignore[misc, assignment]
    if cc in UK_HOME_NATION_TITLES:
        return str(UK_HOME_NATION_TITLES[cc])
    return cc.upper()


def world_flag_static_url(code: str) -> str:
    """Public static path for a tiny w20 flag PNG."""
    cc = (code or "").strip().lower()
    return f"/static/flags/w20/{cc}.png"


def render_suite_world_flags_html() -> str:
    """Dense strip of world (+ UK home-nation) flags for the downloads box bottom.

    Historical name kept; call site is the right-hand ``#downloads`` panel.
    """
    codes = world_flag_codes()
    if not codes:
        return ""
    imgs: list[str] = []
    for cc in codes:
        src = world_flag_static_url(cc)
        title = world_flag_title(cc)
        is_home = cc in ("sct", "eng", "nir", "wls")
        home_attr = (
            f' data-flag-home-nation="1" data-flag-nation="{_esc_html(title)}"'
            if is_home
            else ""
        )
        imgs.append(
            f'<img class="suite-world-flag" src="{_esc_html(src)}" '
            f'width="20" height="15" alt="{_esc_html(title)}" loading="lazy" '
            f'decoding="async" data-flag-cc="{_esc_html(cc)}" '
            f'title="{_esc_html(title)}"{home_attr}/>'
        )
    return f"""
    <div class="suite-world-flags" id="suite-world-flags"
         data-suite-world-flags="1" data-downloads-world-flags="1"
         data-flag-count="{len(codes)}"
         aria-label="Flags of the world" role="img">
      {"".join(imgs)}
    </div>
"""


def render_suite_storefront_html(
    assets: Iterable[DownloadAsset] | None = None,
    *,
    coming_soon: bool | None = None,
    accept_language: str = "",
    country: str = "",
    currency: str = "",
    default_platform: str = "",
    default_interval: str = "month",
) -> str:
    """Homepage **Restore Privacy Suite** block (above VPN downloads).

    Installers unlock after you start the **3-day KEYGEN free trial** (or hold an
    active licence). Residual Connect still needs the KEYGEN from the
    monthly (£3) subscription — same entitlement model as the VPN client.
    """
    _ = (coming_soon, accept_language, country, currency, default_interval)
    items = list(assets) if assets is not None else available_downloads()
    if not items:
        return ""

    def_plat = (default_platform or "").strip().lower()
    # Only accept catalog platforms
    known = {a.platform for a in items}
    if def_plat and def_plat not in known:
        def_plat = ""
    free_links: list[str] = []
    # Detected platform first + highlighted for free download
    ordered = list(items)
    if def_plat:
        ordered = sorted(
            items,
            key=lambda a: (0 if a.platform == def_plat else 1, a.platform),
        )
    primary_free = ""
    if def_plat:
        title = platform_face_title(def_plat)
        href = suite_pay_href(def_plat)
        primary_free = (
            f'<a class="suite-dl suite-dl-primary" id="suite-dl-primary" '
            f'href="{_esc_html(href)}" data-platform="{_esc_html(def_plat)}" '
            f'data-pay="1" data-product="suite" data-suite-latest="1" '
            f'data-detected-platform="1">'
            f"Get Suite for {_esc_html(title)} — KEYGEN /pay</a>"
            f'<p class="suite-detect-hint" id="suite-detect-hint" data-detected-platform="{_esc_html(def_plat)}">'
            f"Detected your device as <strong>{_esc_html(title)}</strong> — "
            f"choose another platform below if needed, then continue on /pay.</p>"
        )
    for a in ordered:
        title = platform_face_title(a.platform)
        href = suite_pay_href(a.platform)
        is_det = " is-detected" if def_plat and a.platform == def_plat else ""
        det_attr = ' data-detected-platform="1"' if is_det else ""
        free_links.append(
            f'<a class="suite-dl{_esc_html(is_det)}" id="suite-dl-{_esc_html(a.platform)}" '
            f'href="{_esc_html(href)}" data-platform="{_esc_html(a.platform)}" '
            f'data-pay="1" data-product="suite" data-suite-latest="1"{det_attr}>'
            f"Get Suite {_esc_html(title)} — /pay</a>"
        )
    free_grid = "\n      ".join(free_links)

    # KEYGEN licence: monthly only (£3), product=suite
    plat_opts: list[str] = []
    for a in items:
        sel = " selected" if a.platform == def_plat else ""
        title = platform_face_title(a.platform)
        plat_opts.append(
            f'<option value="{_esc_html(a.platform)}"{sel}>'
            f"{_esc_html(title)}</option>"
        )
    platform_options = "\n            ".join(plat_opts)

    # Cart entry: GET /pay (platform + monthly Suite KEYGEN). Auto-renew is
    # chosen on the plan cart page — never a silent hidden force-on here.
    keygen_form = f"""
    <form class="dl-buy-form suite-keygen-cta" id="suite-keygen-form" method="get"
          action="/pay" data-pay-via="suite-keygen-cart" data-product="suite"
          data-billing-intervals="month" data-cart-step="1">
      <input type="hidden" name="product" value="suite" id="suite-product-field"/>
      <input type="hidden" name="interval" value="month" id="suite-interval-field"/>
      <div class="dl-buy-field" id="suite-keygen-platform-field">
        <label class="dl-buy-label" for="suite-keygen-platform">Device for KEYGEN licence</label>
        <select name="platform" id="suite-keygen-platform" required
                aria-label="Platform for Suite KEYGEN">
          <option value="" disabled{" selected" if not def_plat else ""}>Choose device…</option>
            {platform_options}
        </select>
      </div>
      <button type="submit" class="dl-buy-now" id="suite-keygen-buy"
              data-product="suite" data-cart-cta="1">
        Get KEYGEN — {PRICE_LABEL}/month</button>
      <p class="suite-cart-hint" id="suite-cart-hint">
        Continues to a short cart: confirm device, one-month KEYGEN licence, and
        choose whether to auto-renew — then secure Stripe checkout.
      </p>
      <p class="dl-stripe-branding" id="suite-stripe-branding">{STRIPE_CHECKOUT_BRANDING_NOTE}</p>
    </form>
"""
    detect_attr = (
        f' data-detected-platform="{_esc_html(def_plat)}"' if def_plat else ""
    )

    return f"""
  <section class="suite-storefront panel-card" id="{SUITE_SECTION_ID}"
           aria-label="Download Restore Privacy Suite"
           data-product="suite" data-storefront="suite" data-pay-packages="1"
           data-suite-version="{_esc_html(RELEASE_VERSION)}"{detect_attr}>
    <h2 id="suite-storefront-title">{SUITE_PRODUCT_TITLE}</h2>
    <span class="suite-version-badge" id="suite-version-badge">{SUITE_VERSION_LABEL}</span>
    <p class="suite-blurb" id="suite-blurb">{SUITE_PRODUCT_SUBTITLE}</p>
{render_suite_product_submenu_html()}
    <p class="suite-keygen-line" id="suite-keygen-line">{SUITE_KEYGEN_HINT}</p>
    <div class="suite-free-primary" id="suite-free-primary" data-pay-packages="1">
      {primary_free}
    </div>
    <div class="suite-free-grid" id="suite-free-grid" data-pay-packages="1">
      {free_grid}
    </div>
    <div class="dl-buttons" id="suite-dl-buttons" data-buy-mode="suite-keygen"
         data-product="suite">
{keygen_form}
    </div>
    <p class="suite-pay-hint" id="suite-pay-hint">
      <strong>Start the 3-day free trial first</strong> (Get KEYGEN above) — installers
      refuse anonymous download. After checkout, use your fulfilment KEYGEN and the
      download links (session_id / token from thank-you). Yearly plans are in the
      client box below. Business-Class requires a separate <strong>£3000 deposit</strong>
      on Service.
    </p>
  </section>
"""


def render_download_section_html(
    assets: Iterable[DownloadAsset] | None = None,
    *,
    coming_soon: bool | None = None,
    accept_language: str = "",
    country: str = "",
    currency: str = "",
    default_platform: str = "",
    default_interval: str = "month",
) -> str:
    """HTML: Download client box with embedded platform + plan + Buy now form.

    Live mode posts to ``/pay/checkout`` (subscription Checkout Session).
    *coming_soon* defaults to :func:`catalog_buy_buttons_coming_soon`.

    Local-currency display uses GBP anchors £3.00 / £30.00 with
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

    buy_form = render_homepage_buy_form_html(
        items,
        coming_soon=coming_soon,
        local_price=local,
        default_platform=default_platform,
        default_interval=default_interval,
    )

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
            f"(from {PRICE_LABEL} / {PRICE_YEARLY_LABEL} GBP) · {accept}"
        )
    if coming_soon:
        price_line = (
            f"{PRICE_LABEL} GBP · {PACKAGE_IDENTITY} — "
            f"{TRIAL_SUBSCRIPTION_SENTENCE} — buy buttons coming soon"
        )
        buttons_mode = ' data-buy-mode="coming-soon"'
    else:
        price_line = (
            f"{PRICE_LABEL} GBP · {PACKAGE_IDENTITY} — "
            f"{TRIAL_SUBSCRIPTION_SENTENCE} — {PAY_AND_KEYGEN_CLAUSE}"
        )
        buttons_mode = (
            ' data-buy-mode="homepage-buy-form" data-billing-intervals="month,year"'
            f' data-display-currency="{local.currency}"'
            f' data-stripe-presentment="{local.stripe_presentment_currency}"'
        )
    # Order: title → price → form → note → world flags (bottom of right box).
    return f"""
  <section class="downloads panel-card" id="downloads"
    aria-label="Download Restore Privacy Suite client"
    data-product="suite" data-catalog-version="{RELEASE_VERSION}"
    data-price-currency="{local.currency}" data-accept-currency="{local.currency}">
    <h2>Download Suite client v{RELEASE_VERSION}</h2>
    <p class="dl-only-price" id="dl-only-price">{ONLY_PRICE_BANNER}</p>
    <p class="dl-local-price" id="dl-local-price">{local_line}</p>
    <p class="dl-accept-currency" id="dl-accept-currency" hidden>{accept}</p>
    <div class="dl-price-box" id="dl-price-box">
      <p class="dl-price" id="dl-price">{price_line}</p>
      <p class="dl-interval-note" id="dl-interval-note">{YEARLY_PLAN_NOTE}</p>
    </div>
    <div class="dl-buttons" id="dl-buttons"{buttons_mode}>
{buy_form}
    </div>
    <div class="dl-platform-note-box" id="dl-platform-note-box">
      <p class="dl-platform-note" id="dl-platform-note">{PLATFORM_SELECT_NOTE}</p>
    </div>
{render_suite_world_flags_html()}
  </section>
"""