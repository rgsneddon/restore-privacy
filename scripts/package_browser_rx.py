#!/usr/bin/env python3
"""Package browser extension + Rx Privacy Browser zips for the Suite catalog pin.

Outputs under ``releases/{suite_version}/``:

  restore-privacy-browser-extension-{ver}.zip
  restore-privacy-rx-browser-{ver}.zip

Both ship the same ``browser_extension/`` tree (Rx is the Suite companion brand).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT_SRC = ROOT / "browser_extension"


def suite_version() -> str:
    try:
        sys.path.insert(0, str(ROOT / "status_page"))
        from downloads import RELEASE_VERSION

        return str(RELEASE_VERSION).strip() or "1.0.2"
    except Exception:
        return "1.0.2"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(version: str | None = None) -> list[dict[str, str]]:
    ver = (version or suite_version()).strip()
    return [
        {
            "kind": "browser",
            "product": "Browser Extension",
            "filename": f"restore-privacy-browser-extension-{ver}.zip",
            "relative_path": f"{ver}/restore-privacy-browser-extension-{ver}.zip",
            "version": ver,
        },
        {
            "kind": "browser",
            "product": "Rx Privacy Browser",
            "filename": f"restore-privacy-rx-browser-{ver}.zip",
            "relative_path": f"{ver}/restore-privacy-rx-browser-{ver}.zip",
            "version": ver,
        },
    ]


def _zip_tree(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.name.startswith("."):
                continue
            zf.write(path, path.relative_to(src).as_posix())


def package(*, version: str | None = None) -> list[Path]:
    ver = (version or suite_version()).strip()
    if not EXT_SRC.is_dir():
        raise FileNotFoundError(EXT_SRC)
    out_dir = ROOT / "releases" / ver
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for row in inventory(ver):
        dest = out_dir / row["filename"]
        _zip_tree(EXT_SRC, dest)
        print(f"package {dest} bytes={dest.stat().st_size} sha256={sha256_file(dest)[:16]}…")
        paths.append(dest)
    # light README
    (out_dir / "BROWSER_RX_README.txt").write_text(
        f"Browser extension + Rx Privacy Browser companion packages for Suite {ver}.\n",
        encoding="utf-8",
    )
    man = {
        "suite_version": ver,
        "packages": [
            {"filename": p.name, "sha256": sha256_file(p), "bytes": p.stat().st_size}
            for p in paths
        ],
    }
    (out_dir / "browser_rx_manifest.json").write_text(
        json.dumps(man, indent=2) + "\n", encoding="utf-8"
    )
    return paths


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", default="")
    p.add_argument("--inventory", action="store_true")
    args = p.parse_args(argv)
    ver = (args.version or "").strip() or suite_version()
    if args.inventory:
        print(json.dumps(inventory(ver), indent=2))
        return 0
    package(version=ver)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
