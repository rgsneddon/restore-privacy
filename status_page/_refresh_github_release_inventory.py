"""One-shot: snapshot every published downloadable asset per operator repo."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPOS = (
    ("GNFP wallet", "gnfp"),
    ("Evolve", "evolve"),
    ("MY PERC", "perccent-wallet"),
    ("perc-mine", "perc-mine"),
    ("beam-mine", "beam-mine"),
    ("Restore Privacy", "restore-privacy"),
    ("Mishi", "mishi"),
    ("perc-stratum-pool", "perc-stratum-pool"),
    ("666Stitches", "666Stitches.mov"),
)

SKIP_SUFFIX = (
    ".sha256",
    ".sha256sum",
    ".sig",
    ".asc",
    ".blockmap",
    ".yml",
    ".yaml",
    ".dmg.blockmap",
)


def guess_platform(name: str) -> str:
    n = name.lower()
    if n.endswith((".mov", ".mp4", ".mkv")):
        return "video"
    if "android" in n or n.endswith(".apk"):
        return "android"
    if "ios" in n or n.endswith(".ipa"):
        return "ios"
    if "macos" in n or "darwin" in n or "osx" in n:
        return "macos"
    if "windows" in n or "win64" in n or "win32" in n or n.endswith(".exe"):
        return "windows"
    if "linux" in n or "arch" in n or n.endswith((".deb", ".rpm", ".appimage")):
        return "linux"
    return "other"


def skip_asset(name: str) -> bool:
    n = name.lower()
    return n.endswith(SKIP_SUFFIX) or n in ("latest.yml", "latest-mac.yml")


def fetch_releases(repo: str) -> list[dict]:
    last_err: Exception | None = None
    raw = ""
    for _ in range(4):
        try:
            raw = subprocess.check_output(
                [
                    "gh",
                    "api",
                    f"repos/rgsneddon/{repo}/releases",
                    "--paginate",
                ],
                text=True,
            )
            last_err = None
            break
        except subprocess.CalledProcessError as err:
            last_err = err
    if last_err is not None:
        raise last_err
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for rel in data:
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        tag = str(rel.get("tag_name") or "").strip()
        assets = []
        for a in rel.get("assets") or []:
            if not isinstance(a, dict):
                continue
            name = str(a.get("name") or "").strip()
            url = str(a.get("browser_download_url") or "").strip()
            if not name or not url or skip_asset(name):
                continue
            assets.append(
                {
                    "platform": guess_platform(name),
                    "filename": name,
                    "href": url,
                }
            )
        if tag and assets:
            out.append({"tag": tag, "assets": assets})
    return out


def main() -> None:
    repos = []
    for product, repo in REPOS:
        print("fetch", repo, flush=True)
        releases = fetch_releases(repo)
        if not releases:
            print("  (no assets)", flush=True)
            continue
        repos.append({"product": product, "repo": repo, "releases": releases})
        print(f"  {len(releases)} releases", flush=True)
    dest = Path(__file__).with_name("github_release_inventory.json")
    dest.write_text(
        json.dumps(
            {
                "updated": "2026-08-15",
                "note": "Every published downloadable asset per public rgsneddon repo. Sidecars omitted. Rendered by list_downloads_map_rows.",
                "repos": repos,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("wrote", dest)


if __name__ == "__main__":
    main()
