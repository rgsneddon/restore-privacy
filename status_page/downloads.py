"""Release download link catalog for the public status page (version 0.0.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

RELEASE_VERSION = "0.0.1"
GITHUB_OWNER = "rgsneddon"
GITHUB_REPO = "restore-privacy"
RELEASE_TAG = "0.0.1"


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


# Artifacts attached to GitHub Release 0.0.1 (built from shipped clients)
RELEASE_ASSETS: tuple[DownloadAsset, ...] = (
    DownloadAsset(
        platform="windows",
        label="Windows (x64) — full client package",
        filename=f"restore-privacy-client-{RELEASE_VERSION}-windows-x64.zip",
    ),
    DownloadAsset(
        platform="windows-standalone",
        label="Windows (x64) — standalone package",
        filename=f"restore-privacy-client-{RELEASE_VERSION}-windows-standalone-x64.zip",
    ),
    DownloadAsset(
        platform="android",
        label="Android — APK installer",
        filename=f"restore-privacy-client-{RELEASE_VERSION}-android.apk",
    ),
)


def available_downloads(include_android: bool = True) -> list[DownloadAsset]:
    """Return download assets for platforms shipped in this release."""
    out: list[DownloadAsset] = []
    for a in RELEASE_ASSETS:
        if a.platform == "android" and not include_android:
            continue
        out.append(a)
    return out


def render_download_section_html(assets: Iterable[DownloadAsset] | None = None) -> str:
    """HTML fragment: Download button/section with real https release URLs."""
    items = list(assets) if assets is not None else available_downloads()
    if not items:
        return ""
    links = []
    for a in items:
        links.append(
            f'    <li><a class="dl" href="{a.url}" '
            f'download="{a.filename}">{a.label}</a></li>'
        )
    links_html = "\n".join(links)
    return f"""
  <section class="downloads" aria-label="Download Restore Privacy client">
    <h2>Download client v{RELEASE_VERSION}</h2>
    <p class="dl-sub">Full installer packages · all available platforms</p>
    <ul class="dl-list">
{links_html}
    </ul>
    <p class="dl-note">Release tag <code>{RELEASE_TAG}</code> on GitHub · run Windows package as Administrator for full VPN</p>
  </section>
"""


def download_css() -> str:
    return """
    .downloads { margin-top: 2.5rem; text-align: center; max-width: 36rem; padding: 0 1rem; }
    .downloads h2 { font-size: 1.1rem; letter-spacing: 0.08em; font-weight: 600; margin: 0 0 0.4rem; }
    .dl-sub { opacity: 0.75; font-size: 0.95rem; margin: 0 0 1rem; }
    .dl-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.65rem; }
    .dl-list li { margin: 0; }
    a.dl {
      display: inline-block; min-width: 16rem; padding: 0.75rem 1.25rem;
      background: #1d4ed8; color: #fff; text-decoration: none; border-radius: 6px;
      font-weight: 600; font-size: 0.95rem;
    }
    a.dl:hover { background: #2563eb; }
    .dl-note { margin-top: 1rem; font-size: 0.8rem; opacity: 0.55; }
    .dl-note code { font-size: 0.85em; }
"""
