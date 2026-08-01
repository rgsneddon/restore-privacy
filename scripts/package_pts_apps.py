#!/usr/bin/env python3
"""Package free Pens · Tables · Slides installers (bundled with rpOS).

Outputs under ``releases/rpos-apps/0.1.0/``:

  pens-0.1.0-installer.zip
  tables-0.1.0-installer.zip
  slides-0.1.0-installer.zip

Each archive installs a Desktop launcher and ships the rpoffice domain module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
OUT = ROOT / "releases" / "rpos-apps" / VERSION
APPS_SRC = ROOT / "rpos" / "apps"

APPS = (
    {"brand": "Pens", "key": "pens", "module": "rpoffice.apps.pens"},
    {"brand": "Tables", "key": "tables", "module": "rpoffice.apps.tables"},
    {"brand": "Slides", "key": "slides", "module": "rpoffice.apps.slides"},
)


def inventory() -> list[dict[str, str]]:
    return [
        {
            "brand": a["brand"],
            "key": a["key"],
            "archive_name": f"{a['key']}-{VERSION}-installer.zip",
            "module": a["module"],
            "free_with_rpos": "true",
        }
        for a in APPS
    ]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _stage_one(app: dict[str, str], stage: Path) -> None:
    stage.mkdir(parents=True, exist_ok=True)
    # Bundle rpoffice tree
    if not APPS_SRC.is_dir():
        raise FileNotFoundError(APPS_SRC)
    shutil.copytree(
        APPS_SRC,
        stage / "apps",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        dirs_exist_ok=True,
    )
    (stage / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    (stage / "PRODUCT").write_text(app["brand"] + "\n", encoding="utf-8")
    (stage / "README.md").write_text(
        f"# {app['brand']} — Restore Privacy\n\n"
        f"Free with **rpOS**. Standalone installer package.\n\n"
        f"```bash\n"
        f"bash install.sh\n"
        f"# places {app['brand']} on Desktop and under install prefix\n"
        f"```\n",
        encoding="utf-8",
    )
    install = stage / "install.sh"
    install.write_text(
        f'''#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${{RPOS_PREFIX:-$HOME/.rpos/install}}"
DESKTOP="${{RPOS_DESKTOP:-$PREFIX/Desktop}}"
mkdir -p "$PREFIX/apps" "$DESKTOP"
cp -a "$ROOT/apps/." "$PREFIX/apps/"
export PYTHONPATH="$PREFIX/apps${{PYTHONPATH:+:$PYTHONPATH}}"
cat > "$DESKTOP/{app["brand"]}" <<LAUNCH
#!/usr/bin/env bash
export PYTHONPATH="$PREFIX/apps${{PYTHONPATH:+:$PYTHONPATH}}"
exec python3 -m {app["module"]} "$@"
LAUNCH
chmod +x "$DESKTOP/{app["brand"]}"
echo "[install] {app["brand"]} launcher → $DESKTOP/{app["brand"]}"
python3 -m {app["module"]} --version || true
''',
        encoding="utf-8",
    )
    install.chmod(install.stat().st_mode | 0o111)
    (stage / "install.ps1").write_text(
        f'''$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Prefix = if ($env:RPOS_PREFIX) {{ $env:RPOS_PREFIX }} else {{ Join-Path $env:USERPROFILE ".rpos\\install" }}
$Desktop = if ($env:RPOS_DESKTOP) {{ $env:RPOS_DESKTOP }} else {{ Join-Path $Prefix "Desktop" }}
New-Item -ItemType Directory -Force -Path (Join-Path $Prefix "apps") | Out-Null
New-Item -ItemType Directory -Force -Path $Desktop | Out-Null
Copy-Item -Recurse -Force (Join-Path $Root "apps\\*") (Join-Path $Prefix "apps")
$Launcher = Join-Path $Desktop "{app["brand"]}.cmd"
@"
@echo off
set PYTHONPATH=$Prefix\\apps;%PYTHONPATH%
python -m {app["module"]} %*
"@ | Set-Content -Path $Launcher -Encoding ASCII
Write-Host "[install] {app["brand"]} launcher → $Launcher"
''',
        encoding="utf-8",
    )


def package_all(*, out_dir: Path | None = None) -> dict[str, Any]:
    out = out_dir or OUT
    out.mkdir(parents=True, exist_ok=True)
    packages: list[dict[str, Any]] = []
    for app in APPS:
        name = f"{app['key']}-{VERSION}-installer.zip"
        dest = out / name
        with tempfile.TemporaryDirectory() as td:
            stage = Path(td) / f"{app['key']}-{VERSION}"
            _stage_one(app, stage)
            if dest.exists():
                dest.unlink()
            with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for path in sorted(stage.rglob("*")):
                    if path.is_file():
                        zf.write(
                            path,
                            arcname=f"{stage.name}/{path.relative_to(stage).as_posix()}",
                        )
        packages.append(
            {
                "ok": dest.stat().st_size > 0,
                "brand": app["brand"],
                "archive": str(dest),
                "archive_name": name,
                "bytes": dest.stat().st_size,
                "sha256": sha256_file(dest),
            }
        )
        print(f"  [{app['brand']}] {name} ({dest.stat().st_size} bytes)", flush=True)
    result = {
        "ok": all(p["ok"] for p in packages),
        "version": VERSION,
        "out_dir": str(out),
        "packages": packages,
        "inventory": inventory(),
        "free_with_rpos": True,
    }
    (out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.inventory:
        print(json.dumps({"version": VERSION, "apps": inventory()}, indent=2))
        return 0
    r = package_all(out_dir=args.out_dir)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
