"""Release download link catalog for the public status page (version 1.0.0).

Public page advertises packages published on the live GitHub release
``rgsneddon/RUST-IN-PRIVACY`` tag ``v1.0.0`` (Windows, Linux, macOS, iOS, Android).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

RELEASE_VERSION = "1.0.0"
GITHUB_OWNER = "rgsneddon"
GITHUB_REPO = "RUST-IN-PRIVACY"
RELEASE_TAG = "v1.0.0"

# Canonical public asset filenames (must match GitHub Release assets).
WINDOWS_ZIP_FILENAME = f"restore-privacy-rust-{RELEASE_VERSION}-windows-x64.zip"
LINUX_TGZ_FILENAME = f"restore-privacy-rust-{RELEASE_VERSION}-linux-x64.tar.gz"
MACOS_ZIP_FILENAME = f"restore-privacy-rust-{RELEASE_VERSION}-macos.zip"
IOS_ZIP_FILENAME = f"restore-privacy-rust-{RELEASE_VERSION}-ios.zip"
ANDROID_APK_FILENAME = f"restore-privacy-rust-{RELEASE_VERSION}-android.apk"


@dataclass(frozen=True)
class DownloadAsset:
    platform: str
    label: str
    filename: str

    @property
    def url(self) -> str:
        return (
            f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/"
            f"{RELEASE_TAG}/{self.filename}"
        )


RELEASE_ASSETS: tuple[DownloadAsset, ...] = (
    DownloadAsset(
        platform="windows",
        label="Windows (x64) - Client/Node (.zip)",
        filename=WINDOWS_ZIP_FILENAME,
    ),
    DownloadAsset(
        platform="linux",
        label="Linux (x64) - Installer (.tar.gz)",
        filename=LINUX_TGZ_FILENAME,
    ),
    DownloadAsset(
        platform="macos",
        label="macOS - Client (.zip)",
        filename=MACOS_ZIP_FILENAME,
    ),
    DownloadAsset(
        platform="ios",
        label="iOS - Client (.zip)",
        filename=IOS_ZIP_FILENAME,
    ),
    DownloadAsset(
        platform="android",
        label="Android - APK installer",
        filename=ANDROID_APK_FILENAME,
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


# Footer: link to the public Rust product repository.
RUST_REPO_URL = "https://github.com/rgsneddon/RUST-IN-PRIVACY"
RUST_REPO_LABEL = "Rust product (RUST-IN-PRIVACY v1.0.0)"


def download_css() -> str:
    return """
    .downloads { margin-top: 2.5rem; text-align: center; max-width: 28rem; padding: 0 1rem; }
    .downloads h2 { font-size: 1.1rem; letter-spacing: 0.08em; font-weight: 600; margin: 0 0 0.4rem; }
    .dl-sub { opacity: 0.75; font-size: 0.95rem; margin: 0 0 1.1rem; }
    .dl-buttons { display: flex; flex-direction: column; gap: 0.75rem; align-items: center; }
    a.dl {
      display: inline-block; min-width: 18rem; padding: 0.85rem 1.35rem;
      background: #1d4ed8; color: #fff; text-decoration: none; border-radius: 8px;
      font-weight: 600; font-size: 0.98rem; box-sizing: border-box;
    }
    a.dl:hover { background: #2563eb; }
    a.dl#dl-android { background: #047857; }
    a.dl#dl-android:hover { background: #059669; }
    a.dl#dl-macos { background: #4b5563; }
    a.dl#dl-macos:hover { background: #6b7280; }
    a.dl#dl-ios { background: #6d28d9; }
    a.dl#dl-ios:hover { background: #7c3aed; }
    a.dl#dl-linux { background: #b45309; }
    a.dl#dl-linux:hover { background: #d97706; }
    .dl-footer { margin-top: 1.25rem; font-size: 0.9rem; line-height: 1.45; }
    .dl-footer a.rust-link { color:#93c5fd; text-decoration:underline; font-weight:600; }
    .dl-footer a.rust-link:hover { color:#bfdbfe; }
"""


def render_rust_footer_html() -> str:
    """Footer under download buttons — link to the public Rust product repo."""
    return (
        f'    <p class="dl-footer" id="rust-repo-footer">'
        f'<a class="rust-link" id="rust-repo-link" href="{RUST_REPO_URL}" '
        f'rel="noopener noreferrer" target="_blank">{RUST_REPO_LABEL}</a></p>'
    )


def render_download_section_html(assets: Iterable[DownloadAsset] | None = None) -> str:
    """HTML fragment: download buttons with real https release URLs."""
    items = list(assets) if assets is not None else available_downloads()
    if not items:
        return ""
    links = []
    for a in items:
        links.append(
            f'    <a class="dl" id="dl-{a.platform}" href="{a.url}" '
            f'download="{a.filename}">{a.label}</a>'
        )
    links_html = "\n".join(links)
    return f"""
  <section class="downloads" id="downloads" aria-label="Download Restore Privacy client">
    <h2>Download client v{RELEASE_VERSION}</h2>
    <p class="dl-sub">Windows | Linux | macOS | iOS | Android - Rust host</p>
    <div class="dl-buttons">
{links_html}
{render_rust_footer_html()}
    </div>
  </section>
"""
