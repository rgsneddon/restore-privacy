#!/usr/bin/env python3
"""Copy catalog release packages into status_page/assets/{VERSION}/ for paid proxy.

Use after ``build_release_*.py`` so Render (rootDir=status_page) can open installers
without a public GitHub repo. Large files are gitignored — stage on the host/CI.

  python scripts/stage_paid_assets.py
  python scripts/stage_paid_assets.py --version 0.3.0
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="", help="Catalog version (default: client/VERSION)")
    args = ap.parse_args()
    ver = (args.version or "").strip()
    if not ver:
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
    src = ROOT / "releases" / ver
    dst = ROOT / "status_page" / "assets" / ver
    if not src.is_dir():
        print(f"missing source dir: {src}", file=sys.stderr)
        return 1
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for path in sorted(src.iterdir()):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() in (".json", ".md"):
            # optional: still copy checksums
            pass
        shutil.copy2(path, dst / path.name)
        n += 1
        print(f"staged {path.name} -> {dst / path.name}")
    print(f"done: {n} files in {dst}")
    return 0 if n else 2


if __name__ == "__main__":
    raise SystemExit(main())
