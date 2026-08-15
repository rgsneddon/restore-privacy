#!/usr/bin/env python3
"""Commit/ship entry: refresh the downloads-map GitHub inventory.

Every commit runs this via the installed pre-commit hook and CI
(``.github/workflows/downloads-map-inventory.yml``). It calls the shipped
:func:`refresh_github_release_inventory` — not a copy.

Usage (from repo root)::

  python scripts/refresh_downloads_map_inventory.py
  python scripts/refresh_downloads_map_inventory.py --stage
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIPPED_UPDATER = ROOT / "status_page" / "_refresh_github_release_inventory.py"
COMMIT_PATH_MODULE = "_refresh_github_release_inventory"
COMMIT_PATH_FUNCTION = "refresh_github_release_inventory"


def load_shipped_updater():
    spec = importlib.util.spec_from_file_location(COMMIT_PATH_MODULE, SHIPPED_UPDATER)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load shipped updater {SHIPPED_UPDATER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_commit_path_refresh(
    *,
    dest: Path | None = None,
    fetch_fn=None,
    allow_network: bool = True,
    stage: bool = False,
) -> dict:
    """Invoke the shipped updater. This is what the hook/CI call."""
    mod = load_shipped_updater()
    fn = getattr(mod, COMMIT_PATH_FUNCTION)
    result = fn(dest=dest, fetch_fn=fetch_fn, allow_network=allow_network)
    dest_path = Path(result["dest"])
    if stage and dest_path.is_file():
        try:
            subprocess.run(
                ["git", "-C", str(ROOT), "add", "--", str(dest_path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Refresh downloads-map GitHub inventory (commit path)"
    )
    ap.add_argument(
        "--stage",
        action="store_true",
        help="git add the inventory after a successful write",
    )
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Do not call GitHub; keep the on-disk snapshot",
    )
    args = ap.parse_args(argv)
    result = run_commit_path_refresh(
        allow_network=not args.offline,
        stage=args.stage,
    )
    dest = result.get("dest")
    print(
        f"commit_path={COMMIT_PATH_FUNCTION} wrote={result.get('wrote')} "
        f"reason={result.get('reason')} dest={dest}"
    )
    if result.get("errors"):
        for err in result["errors"]:
            print(f"  skip {err}", file=sys.stderr)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
