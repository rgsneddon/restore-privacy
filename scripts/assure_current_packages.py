#!/usr/bin/env python3
"""Assure paid downloads use the **current** per-device package set.

Run on every commit via the installed pre-commit hook (see
``install_commit_package_task.py``), or manually::

  python scripts/assure_current_packages.py --list
  python scripts/assure_current_packages.py --check

Exits non-zero when the catalog pin, client/VERSION, or any of the five
device package filenames are not current. Fast: no network, no VPS upload.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from downloads import assure_current_catalog_packages  # noqa: E402


def print_list(result: dict) -> None:
    ver = result["catalog_version"]
    pin = result["product_pin"]
    print(f"catalog_version={ver}")
    print(f"product_pin={pin if pin is not None else '(absent)'}")
    pkgs = result["platforms"]
    print(f"platforms={len(pkgs)}")
    for p in pkgs:
        print(
            f"  platform={p['platform']:<8} file={p['filename']} "
            f"rel={p['relative_path']}"
        )


def print_check(result: dict) -> int:
    print_list(result)
    if result["ok"]:
        print("ASSURE_OK: current per-device packages are consistent")
        return 0
    print("ASSURE_FAIL:", file=sys.stderr)
    for err in result["errors"]:
        print(f"  - {err}", file=sys.stderr)
    print(
        "Fix: align client/VERSION, status_page/downloads.py RELEASE_VERSION/"
        "RELEASE_TAG/filenames, then re-stage paid assets.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Assure current catalog packages for each device platform"
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="Print current version + five platform filenames",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Validate currency (default if no flags); exit 1 on failure",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print full assure result as JSON",
    )
    args = ap.parse_args(argv)
    result = assure_current_catalog_packages()
    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    if args.list and not args.check:
        print_list(result)
        return 0
    # Default and --check: full assurance
    return print_check(result)


if __name__ == "__main__":
    raise SystemExit(main())
