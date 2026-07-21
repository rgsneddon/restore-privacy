"""Release download catalog + paid download UI (version 0.3.0).

Primary path: pay **£2.45** (GBP) via Stripe Checkout per package, then a
single-use download token. Free permanent GitHub ``href`` is not used on the
public buttons. After payment the status host **proxies** the installer
(authenticated GitHub API / local assets) so fulfilment works when the
restore-privacy repo is **private**. Buy Me a Coffee is tip/support only.

Current catalog packages: restore-privacy release **0.3.0**
(macOS Developer ID notarized; iOS Team-signed sideload).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from coffee_link import COFFEE_LINK_URL, coffee_tip_url

RELEASE_VERSION = "0.3.0"
GITHUB_OWNER = "rgsneddon"
GITHUB_REPO = "restore-privacy"
RELEASE_TAG = "0.3.0"
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


# Canonical public asset filenames (must match GitHub Release 0.3.0 assets).
WINDOWS_EXE_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-windows-x64-setup.exe"
ANDROID_APK_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-android.apk"
MACOS_ZIP_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-macos.zip"
IOS_ZIP_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-ios.zip"
LINUX_TGZ_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-linux-x64.tar.gz"

PRICE_LABEL = "£2.45"
# Default tip identity; runtime public page uses coffee_tip_url() (env override).
BMC_TIP_URL = COFFEE_LINK_URL


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
    """Return download assets advertised on the public status page."""
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
RUST_REPO_URL = "https://restore-privacy-status.onrender.com/#downloads"
RUST_REPO_LABEL = (
    f"Catalog v{RELEASE_VERSION} — installers after £2.45 payment only (signed packages)"
)


# Compatibility aliases used by older tests (map to 0.3.0 installers).
WINDOWS_ZIP_FILENAME = WINDOWS_EXE_FILENAME


def download_css() -> str:
    return """
    .downloads { margin-top: 2.5rem; text-align: center; max-width: 28rem; padding: 0 1rem; }
    .downloads h2 { font-size: 1.1rem; letter-spacing: 0.08em; font-weight: 600; margin: 0 0 0.4rem; }
    .dl-sub { opacity: 0.75; font-size: 0.95rem; margin: 0 0 1.1rem; }
    .dl-price { opacity: 0.9; font-size: 0.95rem; margin: 0 0 1rem; font-weight: 600; color: #fde68a; }
    .dl-buttons { display: flex; flex-direction: column; gap: 0.75rem; align-items: center; }
    a.dl, button.dl {
      display: inline-block; min-width: 18rem; padding: 0.85rem 1.35rem;
      background: #1d4ed8; color: #fff; text-decoration: none; border-radius: 8px;
      font-weight: 600; font-size: 0.98rem; box-sizing: border-box; border: 0; cursor: pointer;
      font-family: inherit; text-align: center;
    }
    a.dl:hover, button.dl:hover { background: #2563eb; }
    a.dl#dl-android, button.dl#dl-android { background: #047857; }
    a.dl#dl-android:hover, button.dl#dl-android:hover { background: #059669; }
    a.dl#dl-macos, button.dl#dl-macos { background: #4b5563; }
    a.dl#dl-macos:hover, button.dl#dl-macos:hover { background: #6b7280; }
    a.dl#dl-ios, button.dl#dl-ios { background: #6d28d9; }
    a.dl#dl-ios:hover, button.dl#dl-ios:hover { background: #7c3aed; }
    a.dl#dl-linux, button.dl#dl-linux { background: #b45309; }
    a.dl#dl-linux:hover, button.dl#dl-linux:hover { background: #d97706; }
    .dl-footer { margin-top: 1.25rem; font-size: 0.9rem; line-height: 1.45; }
    .dl-footer a.rust-link { color:#93c5fd; text-decoration:underline; font-weight:600; }
    .dl-footer a.rust-link:hover { color:#bfdbfe; }
    .dl-tip { margin-top: 0.85rem; font-size: 0.88rem; opacity: 0.85; }
    .dl-tip a { color:#f9a8d4; text-decoration:underline; font-weight:600; }
"""


def render_rust_footer_html() -> str:
    """Footer under download buttons — catalog identity + tip (no generic Stripe link).

    Platform Pay buttons carry Stripe Payment Link hrefs; a separate bottom
    “Stripe payment page” link is intentionally not shown.
    """
    tip = coffee_tip_url()
    tip_label = tip.replace("https://", "").replace("http://", "")
    return (
        f'    <p class="dl-footer" id="rust-repo-footer">'
        f'<a class="rust-link" id="rust-repo-link" href="{RUST_REPO_URL}" '
        f'rel="noopener noreferrer" target="_blank">{RUST_REPO_LABEL}</a></p>\n'
        f'    <p class="dl-tip" id="bmc-tip">'
        f'<a id="how-to-buy-footer-link" href="/how-to-buy">How to buy</a>'
        f' · Tip / support (not a paid download): '
        f'<a id="bmc-tip-link" href="{tip}" rel="noopener noreferrer" '
        f'target="_blank">{tip_label}</a></p>'
    )


def render_download_section_html(assets: Iterable[DownloadAsset] | None = None) -> str:
    """HTML: pay via Stripe payment page, then one-time download after webhook grant."""
    items = list(assets) if assets is not None else available_downloads()
    if not items:
        return ""
    links = []
    for a in items:
        href = a.pay_path
        links.append(
            f'    <a class="dl" id="dl-{a.platform}" href="{href}" '
            f'rel="noopener noreferrer" target="_blank" '
            f'data-platform="{a.platform}" data-filename="{a.filename}" '
            f'data-price-pence="245" data-pay-via="stripe-payment-page">'
            f"Pay {PRICE_LABEL} - {a.label}</a>"
        )
    links_html = "\n".join(links)
    return f"""
  <section class="downloads" id="downloads" aria-label="Download Restore Privacy client">
    <h2>Download client v{RELEASE_VERSION}</h2>
    <p class="dl-sub">Windows | Linux | macOS | iOS | Android — catalog
      <span id="catalog-version">v{RELEASE_VERSION}</span>
      (paid download only; installers delivered after Stripe payment)</p>
    <p class="dl-price" id="dl-price">{PRICE_LABEL} GBP per package — pay on Stripe, then get a one-time download link</p>
    <div class="dl-buttons">
{links_html}
{render_rust_footer_html()}
    </div>
  </section>
"""
