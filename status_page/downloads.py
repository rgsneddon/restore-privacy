"""Release download link catalog for the public status page (version 0.0.8).

Public page advertises Windows .exe installer + Android .apk only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

RELEASE_VERSION = "0.0.8"
GITHUB_OWNER = "rgsneddon"
GITHUB_REPO = "restore-privacy"
RELEASE_TAG = "0.0.8"

# Canonical public asset filenames (must match releases/0.0.8/ and GitHub Release).
WINDOWS_EXE_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-windows-x64-setup.exe"
ANDROID_APK_FILENAME = f"restore-privacy-client-{RELEASE_VERSION}-android.apk"


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


# Artifacts attached to GitHub Release 0.0.8
RELEASE_ASSETS: tuple[DownloadAsset, ...] = (
    DownloadAsset(
        platform="windows",
        label="Windows (x64) — Installer (.exe)",
        filename=WINDOWS_EXE_FILENAME,
    ),
    DownloadAsset(
        platform="android",
        label="Android — APK installer",
        filename=ANDROID_APK_FILENAME,
    ),
)


def available_downloads(include_android: bool = True) -> list[DownloadAsset]:
    """Return download assets advertised on the public status page."""
    out: list[DownloadAsset] = []
    for a in RELEASE_ASSETS:
        if a.platform == "android" and not include_android:
            continue
        out.append(a)
    return out


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
    <p class="dl-sub">Windows installer (bundled runtime) · Android APK</p>
    <div class="dl-buttons">
{links_html}
    </div>
    <p class="dl-note">Release <code>{RELEASE_TAG}</code> · Windows setup needs no separate Python install · double-click ? UAC once for full VPN (auto-elevate)</p>
  </section>
"""


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
    .dl-note { margin-top: 1rem; font-size: 0.8rem; opacity: 0.55; line-height: 1.4; }
    .dl-note code { font-size: 0.85em; }
"""
