"""Snapshot every published downloadable asset per operator repo.

The commit/ship path calls :func:`refresh_github_release_inventory` via
``scripts/refresh_downloads_map_inventory.py`` (pre-commit + CI).
"""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, Callable

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


def default_inventory_path() -> Path:
    return Path(__file__).with_name("github_release_inventory.json")


def inventory_note() -> str:
    return (
        "Every published downloadable asset per public rgsneddon repo. "
        "Sidecars omitted. Rendered by list_downloads_map_rows."
    )


def normalize_release_assets(raw_releases: Any) -> list[dict[str, Any]]:
    """Turn a GitHub /releases JSON list into ``[{tag, assets}]``."""
    if not isinstance(raw_releases, list):
        return []
    out: list[dict[str, Any]] = []
    for rel in raw_releases:
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        tag = str(rel.get("tag_name") or rel.get("tag") or "").strip()
        assets = []
        for a in rel.get("assets") or []:
            if not isinstance(a, dict):
                continue
            name = str(a.get("name") or a.get("filename") or "").strip()
            url = str(a.get("browser_download_url") or a.get("href") or "").strip()
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
    return normalize_release_assets(json.loads(raw))


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
        except Exception as exc:  # noqa: BLE001 — keep prior snapshot
            skipped_network = True
            msg = f"{repo}: {exc}"
            errors.append(msg)
            print(f"  (skip {msg})", flush=True)
            continue
        if not releases:
            print("  (no assets)", flush=True)
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
