"""Release download catalog + paid download UI (Restore Privacy Suite v1.0.0).

Primary path: pay **£3.00** (GBP) via Stripe Checkout per package, then a
time-limited download token (default **12 hours**, reusable until expiry).
Free permanent GitHub ``href`` is not used on the public buttons. After payment
the status host **proxies** the installer (authenticated GitHub API / local
assets) so fulfilment works when the restore-privacy repo is **private**.
Buy Me a Coffee is tip/support only.

Current catalog packages: Restore Privacy Suite **1.0.0**
(Windows setup needs no separate Python install; macOS Developer ID notarized;
iOS Team-signed sideload).
"""

from __future__ import annotations

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

RELEASE_VERSION = "1.0.0"
GITHUB_OWNER = "rgsneddon"
GITHUB_REPO = "restore-privacy"
RELEASE_TAG = "1.0.0"
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
    """Public page bottom bar: ``(c) Raskul - all rights reserved``.

    Historical name retained for imports; no longer renders Buy Me a Coffee.
    Stable anchors: ``#site-footer`` / ``#site-footer-copyright``.
    """
    return render_site_copyright_footer_html()


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
    "VPN, Perccent wallet (%), and Evolve in one app — free to install"
)
SUITE_VERSION_LABEL = f"v {RELEASE_VERSION}"
SUITE_KEYGEN_HINT = (
    f"Connect needs a KEYGEN. Licence is {PRICE_LABEL}/month "
    "(same residual entitlement path as the VPN client)."
)
SUITE_FREE_DOWNLOAD_PATH = "/suite/download"
DOWNLOADS_SECTION_ID = "downloads"

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
SUITE_EVOLVE_PAGES_HREF = "https://rgsneddon.github.io/evolve/"
SUITE_EVOLVE_PAGES_LABEL = "Evolve docs (GitHub Pages)"
SUITE_EVOLVE_WHITEPAPER_HREF = "https://rgsneddon.github.io/evolve/fcg_white_paper.html"
SUITE_EVOLVE_WHITEPAPER_LABEL = "Evolve FCG white paper"
SUITE_EVOLVE_SOURCE_HREF = "https://github.com/rgsneddon/evolve"
SUITE_EVOLVE_SOURCE_LABEL = "Evolve source (GitHub)"
SUITE_PERCCENT_WALLET_HREF = "https://github.com/rgsneddon/perccent-wallet"
SUITE_PERCCENT_WALLET_LABEL = "Perccent wallet (GitHub)"
SUITE_PERCCENT_WALLET_README_HREF = (
    "https://github.com/rgsneddon/perccent-wallet/blob/main/README.md"
)
SUITE_PERCCENT_WALLET_README_LABEL = "Perccent wallet README"

# Prefer-to-host residual node (operator path) — separate from Suite client installers.
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
NODE_PREFERENCE_HEADING = "Prefer to run a residual node?"
NODE_PREFERENCE_BLURB = (
    "The free Suite installers and KEYGEN above are for residual <strong>Connect</strong> "
    "on your own device. We also keep a dedicated <strong>node / operator path</strong> "
    "for people who prefer to <strong>host</strong> a residual VPN node "
    "(self-host, Node Operator lab GUI, operator tooling) instead of only installing the "
    "client. That is a different role: not a fifth Suite client platform, and not unlocked "
    "by the monthly KEYGEN checkout."
)


def suite_free_download_href(platform: str) -> str:
    """Relative free-download URL for a Suite platform installer."""
    plat = (platform or "").strip().lower()
    if not plat:
        return SUITE_FREE_DOWNLOAD_PATH
    return f"{SUITE_FREE_DOWNLOAD_PATH}?platform={plat}"


def suite_product_submenu_links() -> list[tuple[str, str, str]]:
    """(href, label, data-key) for Suite box sub-menu — public docs only."""
    return [
        (SUITE_PERC_EXPLORER_HREF, SUITE_PERC_EXPLORER_LABEL, "perc-explorer"),
        (SUITE_EVOLVE_PAGES_HREF, SUITE_EVOLVE_PAGES_LABEL, "evolve-docs"),
        (SUITE_EVOLVE_WHITEPAPER_HREF, SUITE_EVOLVE_WHITEPAPER_LABEL, "evolve-whitepaper"),
        (SUITE_EVOLVE_SOURCE_HREF, SUITE_EVOLVE_SOURCE_LABEL, "evolve-source"),
        (SUITE_PERCCENT_WALLET_HREF, SUITE_PERCCENT_WALLET_LABEL, "perccent-wallet"),
        (
            SUITE_PERCCENT_WALLET_README_HREF,
            SUITE_PERCCENT_WALLET_README_LABEL,
            "perccent-readme",
        ),
    ]


def render_suite_product_submenu_html() -> str:
    """Sub-menu: Perc explorer + Evolve + Perccent wallet public docs."""
    items: list[str] = []
    for href, label, key in suite_product_submenu_links():
        items.append(
            f'<a class="suite-sub-link" id="suite-sub-{_esc_html(key)}" '
            f'href="{_esc_html(href)}" data-suite-sub="{_esc_html(key)}" '
            f'target="_blank" rel="noopener noreferrer">'
            f"{_esc_html(label)}</a>"
        )
    return f"""
    <nav class="suite-product-submenu" id="{SUITE_SUBMENU_ID}"
         data-suite-product-submenu="1"
         aria-label="Suite product docs — Perc explorer, Evolve, Perccent wallet">
      <p class="suite-product-submenu-label" id="suite-product-submenu-label">
        Suite ecosystem
      </p>
      {" ".join(items)}
    </nav>
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
    .suite-product-submenu a {
      display: inline-block; padding: 0.32rem 0.65rem; border-radius: 999px;
      font-size: 0.72rem; font-weight: 700; text-decoration: none;
      color: #e8f2ff; background: rgba(15, 40, 70, 0.65);
      border: 1px solid rgba(174, 208, 234, 0.4);
      letter-spacing: 0.02em;
    }
    .suite-product-submenu a:hover {
      background: rgba(30, 90, 150, 0.75); border-color: #aed0ea;
    }
    .suite-product-submenu-label {
      width: 100%; margin: 0 0 0.35rem; font-size: 0.72rem; font-weight: 700;
      letter-spacing: 0.06em; text-transform: uppercase; color: rgba(174,208,234,0.9);
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
    /* Node / operator preference (additive; not a Suite client platform) */
    .download-node-preference {
      margin: 1rem auto 0; max-width: 36rem; padding: 0.85rem 1rem;
      text-align: center; box-sizing: border-box;
      border: 1px dashed rgba(174, 208, 234, 0.4);
      border-radius: 12px;
      background: rgba(8, 18, 32, 0.45);
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


def render_node_preference_html() -> str:
    """Additive node/operator preference block for public download boxes.

    Explains Suite client vs residual-node host preference and links only to
    real public destinations (status-host README; public Suite Pages/source).
    """
    links = [
        (NODE_OPERATOR_DOCS_HREF, NODE_OPERATOR_DOCS_LABEL, "node-docs"),
        (NODE_OPERATOR_DOCS_ALIAS_HREF, "Node operator (short path)", "node-docs-alias"),
        (NODE_PUBLIC_SUITE_PAGES_HREF, NODE_PUBLIC_SUITE_PAGES_LABEL, "suite-pages"),
        (NODE_PUBLIC_SUITE_SOURCE_HREF, NODE_PUBLIC_SUITE_SOURCE_LABEL, "suite-source"),
    ]
    anchors: list[str] = []
    for href, label, key in links:
        anchors.append(
            f'<a class="node-pref-link" id="node-pref-link-{_esc_html(key)}" '
            f'href="{_esc_html(href)}" data-node-pref-link="{_esc_html(key)}" '
            f'rel="noopener noreferrer">'
            f"{_esc_html(label)}</a>"
        )
    return f"""
    <aside class="download-node-preference" id="{NODE_PREFERENCE_SECTION_ID}"
           data-node-preference="1" aria-label="Residual node operator preference">
      <h3 id="node-pref-heading">{_esc_html(NODE_PREFERENCE_HEADING)}</h3>
      <p class="node-pref-blurb" id="node-pref-blurb">{NODE_PREFERENCE_BLURB}</p>
      <div class="node-pref-links" id="node-pref-links" data-node-pref-links="1">
        {" ".join(anchors)}
      </div>
    </aside>
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

    Installers are **free**. Residual Connect still needs a KEYGEN from the
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
        href = suite_free_download_href(def_plat)
        primary_free = (
            f'<a class="suite-dl suite-dl-primary" id="suite-dl-primary" '
            f'href="{_esc_html(href)}" data-platform="{_esc_html(def_plat)}" '
            f'data-free-download="1" data-product="suite" data-detected-platform="1">'
            f"Free download for {_esc_html(title)}</a>"
            f'<p class="suite-detect-hint" id="suite-detect-hint" data-detected-platform="{_esc_html(def_plat)}">'
            f"Detected your device as <strong>{_esc_html(title)}</strong> — "
            f"or pick another platform below.</p>"
        )
    for a in ordered:
        title = platform_face_title(a.platform)
        href = suite_free_download_href(a.platform)
        is_det = " is-detected" if def_plat and a.platform == def_plat else ""
        det_attr = ' data-detected-platform="1"' if is_det else ""
        free_links.append(
            f'<a class="suite-dl{_esc_html(is_det)}" id="suite-dl-{_esc_html(a.platform)}" '
            f'href="{_esc_html(href)}" data-platform="{_esc_html(a.platform)}" '
            f'data-free-download="1" data-product="suite"{det_attr}>'
            f"Download {_esc_html(title)}</a>"
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

    keygen_form = f"""
    <form class="dl-buy-form suite-keygen-cta" id="suite-keygen-form" method="post"
          action="/pay/checkout" data-pay-via="suite-keygen" data-product="suite"
          data-billing-intervals="month">
      <input type="hidden" name="product" value="suite" id="suite-product-field"/>
      <input type="hidden" name="interval" value="month" id="suite-interval-field"/>
      <input type="hidden" name="auto_renew" value="1" id="suite-auto-renew-field"/>
      <div class="dl-buy-field" id="suite-keygen-platform-field">
        <label class="dl-buy-label" for="suite-keygen-platform">Device for KEYGEN licence</label>
        <select name="platform" id="suite-keygen-platform" required
                aria-label="Platform for Suite KEYGEN">
          <option value="" disabled{" selected" if not def_plat else ""}>Choose device…</option>
            {platform_options}
        </select>
      </div>
      <button type="submit" class="dl-buy-now" id="suite-keygen-buy"
              data-product="suite">Get KEYGEN — {PRICE_LABEL}/month</button>
      <p class="dl-stripe-branding" id="suite-stripe-branding">{STRIPE_CHECKOUT_BRANDING_NOTE}</p>
    </form>
"""
    detect_attr = (
        f' data-detected-platform="{_esc_html(def_plat)}"' if def_plat else ""
    )

    return f"""
  <section class="suite-storefront panel-card" id="{SUITE_SECTION_ID}"
           aria-label="Download Restore Privacy Suite"
           data-product="suite" data-storefront="suite" data-free-download="1"
           data-suite-version="{_esc_html(RELEASE_VERSION)}"{detect_attr}>
    <h2 id="suite-storefront-title">{SUITE_PRODUCT_TITLE}</h2>
    <span class="suite-version-badge" id="suite-version-badge">{SUITE_VERSION_LABEL}</span>
    <p class="suite-blurb" id="suite-blurb">{SUITE_PRODUCT_SUBTITLE}</p>
{render_suite_product_submenu_html()}
    <p class="suite-keygen-line" id="suite-keygen-line">{SUITE_KEYGEN_HINT}</p>
    <div class="suite-free-primary" id="suite-free-primary" data-free-download="1">
      {primary_free}
    </div>
    <div class="suite-free-grid" id="suite-free-grid" data-free-download="1">
      {free_grid}
    </div>
    <div class="dl-buttons" id="suite-dl-buttons" data-buy-mode="suite-keygen"
         data-product="suite">
{keygen_form}
    </div>
    <p class="suite-pay-hint" id="suite-pay-hint">
      Download first, then enter the KEYGEN from your fulfilment email after checkout.
      Yearly VPN plans remain available in the client download box below.
    </p>
{render_node_preference_html()}
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
    # Order: title → price banner → local line → price box → buy form → note.
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
    <div class="dl-buttons" id="dl-buttons"{buttons_mode}>
{buy_form}
    </div>
    <div class="dl-platform-note-box" id="dl-platform-note-box">
      <p class="dl-platform-note" id="dl-platform-note">{PLATFORM_SELECT_NOTE}</p>
    </div>
  </section>
"""