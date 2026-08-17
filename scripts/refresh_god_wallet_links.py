#!/usr/bin/env python3
"""Refresh GNFP wallet download hrefs after a Windows zip upload.

Run from the restore_privacy repo (or HEL /opt/restore-privacy):

    python scripts/refresh_god_wallet_links.py

Fetches rgsneddon/gnfp-wallet releases into github_release_inventory.json
so the GOD hub publisher (list_gnfp_wallet_hub_hrefs) emits the latest
pin that actually has a *-windows.zip. Restart rpt-god-rpai after deploy.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))


def main() -> int:
    from downloads import (
        GNFP_WALLET_REPO,
        latest_gnfp_wallet_pin_with_windows,
        list_gnfp_wallet_hub_hrefs,
    )
    from _refresh_github_release_inventory import (
        fetch_releases,
        load_existing_repos,
        write_inventory,
        build_inventory_payload,
        default_inventory_path,
        REPOS,
    )

    dest = default_inventory_path()
    existing = load_existing_repos(dest)
    by_repo = {str(r.get("repo") or ""): r for r in existing if r.get("repo")}
    releases = fetch_releases(GNFP_WALLET_REPO)
    if not releases:
        print("no gnfp-wallet releases", file=sys.stderr)
        return 1
    by_repo[GNFP_WALLET_REPO] = {
        "product": "GNFP wallet",
        "repo": GNFP_WALLET_REPO,
        "releases": releases,
    }
    order = [name for _, name in REPOS]
    if GNFP_WALLET_REPO not in order:
        order.insert(0, GNFP_WALLET_REPO)
    repos = [by_repo[name] for name in order if name in by_repo]
    write_inventory(build_inventory_payload(repos), dest)
    pin = latest_gnfp_wallet_pin_with_windows(releases)
    hrefs = list_gnfp_wallet_hub_hrefs(releases)
    print("pin", pin)
    for label, href in hrefs:
        print(f"{label}\t{href}")
    print("wrote", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
