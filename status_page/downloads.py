"""Release download catalog + paid download UI (version 0.2.9).

Primary path: pay **£2.45** (GBP) via Stripe Checkout per package, then a
single-use download token. Free permanent GitHub ``href`` is not used on the
public buttons. After payment the status host **proxies** the installer
(authenticated GitHub API / local assets) so fulfilment works when the
restore-privacy repo is **private**. Buy Me a Coffee is tip/support only.

Current catalog packages: restore-privacy release **0.2.9**
(macOS Developer ID notarized; iOS Team-signed sideload).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from coffee_link import COFFEE_LINK_URL, coffee_tip_url

RELEASE_VERSION = "0.2.9"
GITHUB_OWNER = "rgsneddon"
GITHUB_REPO = "restore-privacy"
RELEASE_TAG = "0.2.9"
RELEASE_PAGE_URL = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tag/{RELEASE_TAG}"
)
RELEASE_DOWNLOAD_BASE = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/{RELEASE_TAG}"
)

# Canonical public asset filenames (must match GitHub Release 0.2.9 assets).
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
        """Paid checkout entry on this status site (not a free GitHub href)."""
        return f"/pay?platform={self.platform}"


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


# Footer: catalog identity (repo may be private — installers only after pay).
RUST_REPO_URL = RELEASE_PAGE_URL
RUST_REPO_LABEL = (
    f"Catalog v{RELEASE_VERSION} — installers after £2.45 payment only (signed packages)"
)


# Compatibility aliases used by older tests (map to 0.2.9 installers).
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
    """Footer under download buttons — release source + tip / Stripe payment page."""
    # Local import avoids circular import (payments → downloads).
    from payments import stripe_payment_page_url

    tip = coffee_tip_url()
    tip_label = tip.replace("https://", "").replace("http://", "")
    pay_page = stripe_payment_page_url()
    return (
        f'    <p class="dl-footer" id="rust-repo-footer">'
        f'<a class="rust-link" id="rust-repo-link" href="{RUST_REPO_URL}" '
        f'rel="noopener noreferrer" target="_blank">{RUST_REPO_LABEL}</a></p>\n'
        f'    <p class="dl-tip" id="bmc-tip">'
        f'Tip / support (not a paid download): '
        f'<a id="bmc-tip-link" href="{tip}" rel="noopener noreferrer" '
        f'target="_blank">{tip_label}</a>'
        f' · <a id="stripe-payment-page-link" href="{pay_page}" rel="noopener noreferrer" '
        f'target="_blank">Stripe payment page</a></p>'
    )


def render_download_section_html(assets: Iterable[DownloadAsset] | None = None) -> str:
    """HTML fragment: paid download buttons (£2.45) — not free permanent GitHub hrefs."""
    items = list(assets) if assets is not None else available_downloads()
    if not items:
        return ""
    links = []
    for a in items:
        # Paid entry: /pay?platform=… (server starts Stripe Checkout)
        links.append(
            f'    <a class="dl" id="dl-{a.platform}" href="{a.pay_path}" '
            f'data-platform="{a.platform}" data-filename="{a.filename}" '
            f'data-price-pence="245">'
            f"Pay {PRICE_LABEL} - {a.label}</a>"
        )
    links_html = "\n".join(links)
    return f"""
  <section class="downloads" id="downloads" aria-label="Download Restore Privacy client">
    <h2>Download client v{RELEASE_VERSION}</h2>
    <p class="dl-sub">Windows | Linux | macOS | iOS | Android — catalog
      <span id="catalog-version">v{RELEASE_VERSION}</span>
      (paid download only; installers delivered after Stripe payment)</p>
    <p class="dl-price" id="dl-price">{PRICE_LABEL} GBP per package download (Stripe Checkout)</p>
    <div class="dl-buttons">
{links_html}
{render_rust_footer_html()}
    </div>
  </section>
"""
