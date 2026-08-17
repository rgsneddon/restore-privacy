"""Snapshot every published downloadable asset per operator repo.

The commit/ship path calls :func:`refresh_github_release_inventory` via
``scripts/refresh_downloads_map_inventory.py`` (pre-commit + CI).
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, Callable

# Public installer apps only. Restore Privacy clients are the Helsinki
# suite_client rows (GitHub latest is the old 1.2.5 Windows exe).
# Mishi is private. 666Stitches.mov is gone. perc-stratum-pool has no installer.
REPOS = (
    ("GNFP wallet", "gnfp-wallet"),
    ("Evolve", "evolve"),
    ("MY PERC", "perccent-wallet"),
    ("perc-mine", "perc-mine"),
    ("beam-mine", "beam-mine"),
)

# Never render these even if a leftover snapshot still lists them.
MAP_SKIP_REPOS = frozenset(
    {
        "restore-privacy",
        "mishi",
        "666Stitches.mov",
        "perc-stratum-pool",
        "gnfp",  # superseded by gnfp-wallet
    }
)

SKIP_SUFFIX = (
    ".sha256",
    ".sha256sum",
    ".sha512",
    ".sig",
    ".asc",
    ".blockmap",
    ".yml",
    ".yaml",
    ".dmg.blockmap",
    ".md",
    ".txt",
    ".html",
    ".mov",
    ".mp4",
    ".mkv",
)
SKIP_NAMES = frozenset(
    {
        "latest.yml",
        "latest-mac.yml",
        "checksums.json",
        "checksums.sha256",
        "checksums.sha512",
        "manifest.json",
        "signing-status.json",
        "pkgbuild",
    }
)
SKIP_NAME_PARTS = (
    "github-pages",
    "checksums.",
    "sha256sums",
)
INSTALLER_SUFFIX = (
    ".exe",
    ".msi",
    ".apk",
    ".ipa",
    ".zip",
    ".tar.gz",
    ".tgz",
    ".tar.zst",
    ".pkg.tar.zst",
    ".deb",
    ".rpm",
    ".appimage",
)
_SEMVER_RE = re.compile(r"(\d+\.\d+\.\d+)")
_GONE_MARKERS = ("404", "Not Found", "Could not resolve to a Repository")


class RepoGone(Exception):
    """GitHub repo or releases endpoint no longer exists."""


def guess_platform(name: str) -> str:
    n = name.lower()
    if "ipad" in n:
        return "ipad"
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
    if n in SKIP_NAMES or n.endswith(SKIP_SUFFIX):
        return True
    if any(part in n for part in SKIP_NAME_PARTS):
        return True
    if n.startswith("checksums") or n.startswith("sha256sums"):
        return True
    return not any(n.endswith(suf) for suf in INSTALLER_SUFFIX)


def filename_semver(text: str) -> str:
    """First ``X.Y.Z`` in a tag or basename, else empty."""
    match = _SEMVER_RE.search(str(text or ""))
    return match.group(1) if match else ""


def asset_matches_tag(filename: str, tag: str) -> bool:
    """Drop leftover older packages attached to a newer tag (0.0.2 on v0.0.5)."""
    file_ver = filename_semver(filename)
    tag_ver = filename_semver(tag)
    if file_ver and tag_ver and file_ver != tag_ver:
        return False
    return True


def prune_duplicate_archives(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer ``.ipa`` / ``.apk`` / ``.exe`` over a same-stem ``.zip``."""
    names = {str(a.get("filename") or "") for a in assets}
    names_l = {n.lower() for n in names}
    out: list[dict[str, Any]] = []
    for asset in assets:
        name = str(asset.get("filename") or "")
        if not name.lower().endswith(".zip"):
            out.append(asset)
            continue
        stem = name[: -len(".zip")]
        if any((stem + ext).lower() in names_l for ext in (".ipa", ".apk", ".exe")):
            continue
        out.append(asset)
    return out


def select_release_installers(tag: str, assets: list[Any]) -> list[dict[str, Any]]:
    """Latest-tag installer rows only (no checksums, no leftover pins)."""
    picked: list[dict[str, Any]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        fname = str(asset.get("filename") or asset.get("name") or "").strip()
        href = str(asset.get("href") or asset.get("browser_download_url") or "").strip()
        if not fname or not href or skip_asset(fname) or not asset_matches_tag(fname, tag):
            continue
        plat = str(asset.get("platform") or "").strip() or guess_platform(fname)
        picked.append({"platform": plat, "filename": fname, "href": href})
    return prune_duplicate_archives(picked)


def default_inventory_path() -> Path:
    return Path(__file__).with_name("github_release_inventory.json")


def inventory_note() -> str:
    return (
        "Newest installer packages per public rgsneddon app. "
        "Checksums, private repos, and superseded pins omitted. "
        "Rendered by list_downloads_map_rows."
    )


def _output_says_gone(text: str) -> bool:
    blob = text or ""
    return any(marker in blob for marker in _GONE_MARKERS)


def normalize_release_assets(raw_releases: Any) -> list[dict[str, Any]]:
    """Turn a GitHub /releases JSON list into ``[{tag, assets}]``."""
    if not isinstance(raw_releases, list):
        return []
    out: list[dict[str, Any]] = []
    for rel in raw_releases:
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        tag = str(rel.get("tag_name") or rel.get("tag") or "").strip()
        assets = select_release_installers(tag, rel.get("assets") or [])
        if tag and assets:
            out.append({"tag": tag, "assets": assets})
    return out


def _gh_json(args: list[str]) -> Any:
    last_err: Exception | None = None
    for _ in range(4):
        try:
            raw = subprocess.check_output(args, text=True)
            last_err = None
            return json.loads(raw)
        except subprocess.CalledProcessError as err:
            last_err = err
            blob = str(err.stderr or "") + str(err.output or "") + str(err)
            if _output_says_gone(blob):
                raise RepoGone(blob.strip()[:240]) from err
        except json.JSONDecodeError as err:
            last_err = err
    if last_err is not None:
        raise last_err
    return None


def fetch_releases(repo: str) -> list[dict]:
    """Published installer releases via ``gh release`` (more reliable than /releases API)."""
    listed = _gh_json(
        [
            "gh",
            "release",
            "list",
            "-R",
            f"rgsneddon/{repo}",
            "--exclude-drafts",
            "--limit",
            "20",
            "--json",
            "tagName,isLatest",
        ]
    )
    if not isinstance(listed, list) or not listed:
        return []
    raw_releases: list[dict[str, Any]] = []
    for item in listed:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tagName") or "").strip()
        if not tag:
            continue
        viewed = _gh_json(
            [
                "gh",
                "release",
                "view",
                tag,
                "-R",
                f"rgsneddon/{repo}",
                "--json",
                "tagName,isDraft,assets",
            ]
        )
        if not isinstance(viewed, dict) or viewed.get("isDraft"):
            continue
        assets = []
        for asset in viewed.get("assets") or []:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "").strip()
            if not name:
                continue
            assets.append(
                {
                    "name": name,
                    "browser_download_url": (
                        f"https://github.com/rgsneddon/{repo}/releases/download/"
                        f"{tag}/{name}"
                    ),
                }
            )
        raw_releases.append({"tag_name": tag, "draft": False, "assets": assets})
    return normalize_release_assets(raw_releases)


def load_existing_repos(dest: Path) -> list[dict[str, Any]]:
    if not dest.is_file():
        return []
    try:
        raw = json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return []
    repos = raw.get("repos") if isinstance(raw, dict) else None
    if not isinstance(repos, list):
        return []
    return [r for r in repos if isinstance(r, dict)]


def build_inventory_payload(repos: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "updated": date.today().isoformat(),
        "note": inventory_note(),
        "repos": repos,
    }


def write_inventory(payload: dict[str, Any], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest


def refresh_github_release_inventory(
    *,
    dest: Path | None = None,
    fetch_fn: Callable[[str], list[dict[str, Any]]] | None = None,
    allow_network: bool = True,
) -> dict[str, Any]:
    """Refresh ``github_release_inventory.json`` from published GitHub releases.

    This is the function the commit/ship path runs. Failed fetches keep the
    previous repo rows; a total network miss leaves the file unchanged.
    """
    dest = Path(dest) if dest is not None else default_inventory_path()
    existing = load_existing_repos(dest)
    by_repo = {str(r.get("repo") or ""): r for r in existing if r.get("repo")}
    fetch = fetch_fn
    skipped_network = False
    reason = ""
    if fetch is None:
        if not allow_network:
            return {
                "ok": True,
                "dest": dest,
                "repos": existing,
                "wrote": False,
                "skipped_network": True,
                "reason": "network_disabled",
                "errors": [],
            }
        fetch = fetch_releases
    errors: list[str] = []
    fetched = 0
    for product, repo in REPOS:
        print("fetch", repo, flush=True)
        try:
            releases = fetch(repo)
        except RepoGone as exc:
            by_repo.pop(repo, None)
            msg = f"{repo}: gone ({exc})"
            errors.append(msg)
            print(f"  (drop {msg})", flush=True)
            continue
        except Exception as exc:  # noqa: BLE001 — keep prior snapshot
            skipped_network = True
            msg = f"{repo}: {exc}"
            errors.append(msg)
            print(f"  (skip {msg})", flush=True)
            continue
        if not releases:
            by_repo.pop(repo, None)
            print("  (no installer assets)", flush=True)
            continue
        by_repo[repo] = {"product": product, "repo": repo, "releases": releases}
        fetched += 1
        print(f"  {len(releases)} releases", flush=True)
    repos = [by_repo[name] for _, name in REPOS if name in by_repo]
    if not repos:
        return {
            "ok": True,
            "dest": dest,
            "repos": existing,
            "wrote": False,
            "skipped_network": True,
            "reason": reason or "no_releases",
            "errors": errors,
        }
    prev_repos = json.dumps(existing, sort_keys=True)
    next_repos = json.dumps(repos, sort_keys=True)
    if prev_repos == next_repos and dest.is_file():
        return {
            "ok": True,
            "dest": dest,
            "repos": repos,
            "wrote": False,
            "skipped_network": skipped_network,
            "reason": "unchanged",
            "errors": errors,
            "fetched": fetched,
        }
    payload = build_inventory_payload(repos)
    write_inventory(payload, dest)
    print("wrote", dest)
    return {
        "ok": True,
        "dest": dest,
        "repos": repos,
        "wrote": True,
        "skipped_network": skipped_network,
        "reason": "updated",
        "errors": errors,
        "fetched": fetched,
    }


def main() -> int:
    result = refresh_github_release_inventory()
    if result.get("wrote"):
        print("refresh ok wrote", result["dest"])
    else:
        print("refresh ok", result.get("reason") or "unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
