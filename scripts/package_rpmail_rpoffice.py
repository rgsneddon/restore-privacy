#!/usr/bin/env python3
"""Package rpMail and rpOffice installers for desktop platforms.

Domain sources live next to the monorepo (``~/rpMail``, ``~/rpOffice``) or under
``ROOT/../rpMail`` / ``ROOT/../rpOffice``. Desktop matrix only (no iOS/Android)::

  windows, macos, linux-x86_64, linux-aarch64

Outputs under ``releases/rpmail/{ver}/`` and ``releases/rpoffice/{ver}/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.1"

PRODUCTS = (
    {
        "key": "rpmail",
        "product": "rpMail",
        "src_names": ("rpMail", "rpmail"),
        "module_hint": "rpmail",
    },
    {
        "key": "rpoffice",
        "product": "rpOffice",
        "src_names": ("rpOffice", "rpoffice"),
        "module_hint": "rpoffice",
    },
)

DESKTOP_PLATFORMS = (
    ("windows", "zip", "x64"),
    ("macos", "zip", "universal"),
    ("linux-x86_64", "tar.gz", "x86_64"),
    ("linux-aarch64", "tar.gz", "aarch64"),
)


def _find_src(names: tuple[str, ...]) -> Path | None:
    candidates: list[Path] = []
    home = Path.home()
    for n in names:
        candidates.extend(
            [
                home / n,
                ROOT.parent / n,
                ROOT / n,
                ROOT / "rpos" / "apps" / n,
            ]
        )
    for c in candidates:
        if c.is_dir() and any(c.iterdir()):
            return c
    return None


def platform_package_matrix(version: str = VERSION) -> list[dict[str, Any]]:
    """Pure inventory of desktop install slots for both products."""
    ver = (version or VERSION).strip() or VERSION
    rows: list[dict[str, Any]] = []
    for prod in PRODUCTS:
        for plat, fmt, arch in DESKTOP_PLATFORMS:
            if fmt == "zip":
                fname = f"{prod['key']}-{ver}-{plat}.zip"
            else:
                fname = f"{prod['key']}-{ver}-{plat}.tar.gz"
            rows.append(
                {
                    "kind": prod["key"],
                    "product": prod["product"],
                    "platform": plat,
                    "arch": arch,
                    "version": ver,
                    "filename": fname,
                    "relative_path": f"{prod['key']}/{ver}/{fname}",
                    "format": fmt,
                    "installable": True,
                    "mobile": False,
                }
            )
    return rows


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_installers(stage: Path, product: str, key: str) -> None:
    (stage / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    (stage / "PRODUCT").write_text(product + "\n", encoding="utf-8")
    (stage / "README.md").write_text(
        f"# {product}\n\n"
        f"Desktop installer for **{product}** (Restore Privacy brand).\n\n"
        f"```bash\nbash install.sh\n```\n\n"
        f"Windows: ``powershell -File install.ps1``\n",
        encoding="utf-8",
    )
    (stage / "install.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'ROOT="$(cd "$(dirname "$0")" && pwd)"\n'
        'PREFIX="${RPT_INSTALL_PREFIX:-$HOME/.local/share/restore-privacy/'
        + key
        + '}"\n'
        'mkdir -p "$PREFIX"\n'
        'cp -R "$ROOT"/* "$PREFIX/" 2>/dev/null || true\n'
        f'echo "Installed {product} under $PREFIX"\n'
        'DESKTOP="${XDG_DESKTOP_DIR:-$HOME/Desktop}"\n'
        'mkdir -p "$DESKTOP" 2>/dev/null || true\n'
        f'ln -sfn "$PREFIX" "$DESKTOP/{product}" 2>/dev/null || true\n',
        encoding="utf-8",
    )
    (stage / "install.sh").chmod(0o755)
    (stage / "install.ps1").write_text(
        f'# {product} Windows installer\n'
        f'$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n'
        f'$Prefix = Join-Path $env:LOCALAPPDATA "restore-privacy\\{key}"\n'
        f'New-Item -ItemType Directory -Force -Path $Prefix | Out-Null\n'
        f'Copy-Item -Recurse -Force (Join-Path $Root "*") $Prefix\n'
        f'Write-Host "Installed {product} under $Prefix"\n'
        f'$Desk = [Environment]::GetFolderPath("Desktop")\n'
        f'if ($Desk) {{ New-Item -ItemType Junction -Force -Path (Join-Path $Desk "{product}") -Target $Prefix | Out-Null }}\n',
        encoding="utf-8",
    )


def _archive(stage: Path, dest: Path, fmt: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    if fmt == "zip":
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(stage).as_posix())
    else:
        with tarfile.open(dest, "w:gz") as tf:
            tf.add(stage, arcname=stage.name)


def package(*, version: str = VERSION) -> list[Path]:
    ver = (version or VERSION).strip() or VERSION
    out_paths: list[Path] = []
    for prod in PRODUCTS:
        src = _find_src(tuple(prod["src_names"]))
        if src is None:
            print(f"WARN: source not found for {prod['product']}; skipping", file=sys.stderr)
            continue
        out_dir = ROOT / "releases" / prod["key"] / ver
        out_dir.mkdir(parents=True, exist_ok=True)
        for plat, fmt, _arch in DESKTOP_PLATFORMS:
            with tempfile.TemporaryDirectory(prefix=f"{prod['key']}-") as td:
                stage = Path(td) / f"{prod['key']}-{ver}-{plat}"
                stage.mkdir(parents=True)
                # copy domain sources
                for item in src.iterdir():
                    if item.name in (".git", "__pycache__", ".venv", "venv", "dist", "build"):
                        continue
                    dest_i = stage / item.name
                    if item.is_dir():
                        shutil.copytree(
                            item,
                            dest_i,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
                        )
                    else:
                        shutil.copy2(item, dest_i)
                _write_installers(stage, prod["product"], prod["key"])
                if fmt == "zip":
                    fname = f"{prod['key']}-{ver}-{plat}.zip"
                else:
                    fname = f"{prod['key']}-{ver}-{plat}.tar.gz"
                dest = out_dir / fname
                _archive(stage, dest, fmt)
                print(
                    f"package {dest} bytes={dest.stat().st_size} "
                    f"sha256={sha256_file(dest)[:16]}…"
                )
                out_paths.append(dest)
        man = {
            "product": prod["product"],
            "version": ver,
            "platforms": [p[0] for p in DESKTOP_PLATFORMS],
            "packages": [
                {
                    "filename": p.name,
                    "sha256": sha256_file(p),
                    "bytes": p.stat().st_size,
                }
                for p in out_paths
                if p.parent == out_dir
            ],
        }
        (out_dir / "manifest.json").write_text(
            json.dumps(man, indent=2) + "\n", encoding="utf-8"
        )
    return out_paths


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", action="store_true")
    p.add_argument("--version", default=VERSION)
    args = p.parse_args(argv)
    if args.inventory:
        print(json.dumps(platform_package_matrix(args.version), indent=2))
        return 0
    paths = package(version=args.version)
    if not paths:
        print("ERROR: no packages produced", file=sys.stderr)
        return 1
    print(f"total_packages={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
