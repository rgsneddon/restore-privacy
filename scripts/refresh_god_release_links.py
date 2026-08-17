#!/usr/bin/env python3
"""Refresh GOD / Downloads Map installer inventory from GitHub.

Helsinki runs this on a systemd timer so Mac and Windows releases both
show up on https://god.restoreprivacy.online without a laptop deploy.

    python scripts/refresh_god_release_links.py

Failed fetches keep the previous snapshot. The GOD page reads the JSON
on each request — no service restart required.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))


def main() -> int:
    from _refresh_github_release_inventory import (
        REPOS,
        refresh_github_release_inventory,
    )
    from downloads import latest_repo_pin, list_repo_hub_hrefs

    result = refresh_github_release_inventory()
    dest = result.get("dest")
    print("wrote" if result.get("wrote") else "unchanged", dest)
    if result.get("errors"):
        for err in result["errors"]:
            print("error", err, file=sys.stderr)
    for _product, repo in REPOS:
        pin = latest_repo_pin(repo)
        hrefs = list_repo_hub_hrefs(repo)
        print(f"{repo}\t{pin or '-'}")
        for label, href in hrefs:
            print(f"  {label}\t{href}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
