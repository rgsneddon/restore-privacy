#!/usr/bin/env python3
"""Package **rpOS** installers for desktop platforms only.

Monopin **0.2.0** under ``releases/rpos/0.2.0/`` (includes **RxShell** CLI).

Installable matrix (desktop only)::

  windows  — zip + install.ps1 / RESTORE warning entry + RxShell
  macos    — zip + install.sh / RESTORE warning entry + RxShell
  linux    — tar.gz for **x86_64** and **aarch64** (any Linux relatives)

**Not installable for this product surface:** iOS, Android (no packages).

Produces archives + SHA256SUMS + manifest.json. Pure inventory via
``platform_package_matrix`` (testable without building).

Usage::

  python3 scripts/package_rpos.py
  python3 scripts/package_rpos.py --inventory
  python3 scripts/package_rpos.py --platform linux-x86_64
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
RPOS_VERSION = "0.2.0"
OUT_DIR = ROOT / "releases" / "rpos" / RPOS_VERSION
RPOS_SRC = ROOT / "rpos"
RXSHELL_PRODUCT = "RxShell"

# Desktop-only product slots — never iOS/Android for rpOS installers.
INSTALLABLE_PLATFORMS: tuple[str, ...] = (
    "windows",
    "macos",
    "linux-x86_64",
    "linux-aarch64",
)


def platform_package_matrix(version: str = RPOS_VERSION) -> list[dict[str, Any]]:
    """Pure inventory of desktop install slots (no I/O)."""
    ver = (version or RPOS_VERSION).strip() or RPOS_VERSION
    return [
        {
            "platform": "windows",
            "arch": "x86_64",
            "os": "windows",
            "version": ver,
            "archive_name": f"rpos-{ver}-windows-x64.zip",
            "stage_top": f"rpos-{ver}-windows",
            "format": "zip",
            "install_entry": "install.ps1",
            "restore_entry": "RESTORE_rpos.ps1",
            "restore_click": "RESTORE_click.ps1",
            "installable": True,
            "mobile": False,
            "honesty": (
                "Desktop install of the rpOS commercial foundation tree. "
                "RESTORE_rpos.ps1 shows a wipe warning before any destructive path; "
                "this package stages product materials — it does not silently reformat disks."
            ),
        },
        {
            "platform": "macos",
            "arch": "universal",
            "os": "macos",
            "version": ver,
            "archive_name": f"rpos-{ver}-macos.zip",
            "stage_top": f"rpos-{ver}-macos",
            "format": "zip",
            "install_entry": "install.sh",
            "restore_entry": "RESTORE_rpos.sh",
            "restore_click": "RESTORE_click.sh",
            "installable": True,
            "mobile": False,
            "honesty": (
                "Desktop install of the rpOS commercial foundation tree on macOS. "
                "RESTORE_rpos.sh warns before wipe intent; Apple platforms may require "
                "additional MDM for full-disk workflows."
            ),
        },
        {
            "platform": "linux-x86_64",
            "arch": "x86_64",
            "os": "linux",
            "version": ver,
            "archive_name": f"rpos-{ver}-linux-x86_64.tar.gz",
            "stage_top": f"rpos-{ver}-linux-x86_64",
            "format": "tar.gz",
            "install_entry": "install.sh",
            "restore_entry": "RESTORE_rpos.sh",
            "restore_click": "RESTORE_click.sh",
            "installable": True,
            "mobile": False,
            "honesty": (
                "Linux x86_64 / amd64 relatives (Ubuntu, Debian, Fedora, Arch, …). "
                "install.sh stages under /opt/rpos; RESTORE_click.sh is the single-click path (advisories + gate + dry-run wipe intent + Ned OOBE)."
            ),
        },
        {
            "platform": "linux-aarch64",
            "arch": "aarch64",
            "os": "linux",
            "version": ver,
            "archive_name": f"rpos-{ver}-linux-aarch64.tar.gz",
            "stage_top": f"rpos-{ver}-linux-aarch64",
            "format": "tar.gz",
            "install_entry": "install.sh",
            "restore_entry": "RESTORE_rpos.sh",
            "restore_click": "RESTORE_click.sh",
            "installable": True,
            "mobile": False,
            "honesty": (
                "Linux aarch64 / arm64 relatives (Raspberry Pi OS 64-bit, ARM servers, …). "
                "Same single-click RESTORE_click path as x86_64; arch tag for operator targeting."
            ),
        },
    ]


def catalog_platforms(version: str = RPOS_VERSION) -> list[str]:
    return [s["platform"] for s in platform_package_matrix(version)]


def linux_arches(version: str = RPOS_VERSION) -> list[str]:
    return [s["arch"] for s in platform_package_matrix(version) if s["os"] == "linux"]


def excluded_mobile_platforms() -> list[str]:
    """Explicit non-installable slots for this goal."""
    return ["ios", "android"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_rpos_tree(stage: Path) -> None:
    """Copy monorepo rpos/ foundation into stage/rpos/."""
    if not RPOS_SRC.is_dir():
        raise FileNotFoundError(f"missing rpOS source tree: {RPOS_SRC}")
    dst = stage / "rpos"
    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        ".git",
        ".DS_Store",
        "*.priv",
    )
    shutil.copytree(RPOS_SRC, dst, ignore=ignore, dirs_exist_ok=True)


def _write_capability(stage: Path, slot: dict[str, Any]) -> None:
    body = (
        f"# rpOS capability — {slot['platform']}\n\n"
        f"- **version:** {slot['version']}\n"
        f"- **os:** {slot['os']}\n"
        f"- **arch:** {slot['arch']}\n"
        f"- **installable:** yes (desktop)\n"
        f"- **install_entry:** {slot['install_entry']}\n"
        f"- **restore_entry:** {slot['restore_entry']}\n"
        f"- **RxShell:** `{RXSHELL_PRODUCT}` multi-language CLI "
        f"(`python -m rpos.rxshell` / `./RxShell`)\n"
        f"- **mobile (iOS/Android):** not supported for this installer surface\n\n"
        f"## Honesty\n\n{slot['honesty']}\n\n"
        "## RxShell\n\n"
        f"{RXSHELL_PRODUCT} is the PowerShell-type CLI of rpOS. It accepts "
        "shell / Python / JavaScript / PowerShell-style snippets via host "
        "interpreters. It is **not** full Microsoft PowerShell parity and does "
        "not embed every language runtime — missing runtimes fail closed.\n\n"
        "## RESTORE wipe intent\n\n"
        "The RESTORE entry **warns** the operator/user before any destructive path. "
        "This package is an **installable commercial foundation** (docs, SDK scaffolds, "
        "launchers). It does **not** ship a silent instant full-disk reformat binary. "
        f"{RXSHELL_PRODUCT} launches without RESTORE wipe.\n"
    )
    (stage / "CAPABILITY.md").write_text(body, encoding="utf-8")
    (stage / "CAPABILITY.json").write_text(
        json.dumps(
            {
                "product": "rpOS",
                "platform": slot["platform"],
                "os": slot["os"],
                "arch": slot["arch"],
                "version": slot["version"],
                "installable": True,
                "mobile": False,
                "install_entry": slot["install_entry"],
                "restore_entry": slot["restore_entry"],
                "rxshell": RXSHELL_PRODUCT,
                "rxshell_entry": "python -m rpos.rxshell",
                "rxshell_launcher": "RxShell" if slot["os"] != "windows" else "RxShell.cmd",
                "excluded_mobile": excluded_mobile_platforms(),
                "honesty": slot["honesty"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_rxshell_launchers(stage: Path, slot: dict[str, Any]) -> None:
    """Ship RxShell launch scripts at package root (no RESTORE required)."""
    if slot["os"] == "windows":
        (stage / "RxShell.cmd").write_text(
            """@echo off
setlocal
set ROOT=%~dp0
set PYTHONPATH=%ROOT%;%PYTHONPATH%
cd /d "%ROOT%"
python -m rpos.rxshell %*
""",
            encoding="utf-8",
        )
    else:
        sh = stage / "RxShell"
        sh.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
exec python3 -m rpos.rxshell "$@"
""",
            encoding="utf-8",
        )
        sh.chmod(sh.stat().st_mode | 0o111)
    # Short docs
    (stage / "RXSHELL.md").write_text(
        f"# {RXSHELL_PRODUCT} (rpOS {slot['version']})\n\n"
        "PowerShell-type multi-language CLI for rpOS.\n\n"
        "## Launch\n\n"
        "```bash\n"
        "./RxShell                 # interactive (Unix)\n"
        "RxShell.cmd               # interactive (Windows)\n"
        "python3 -m rpos.rxshell\n"
        "python3 -m rpos.rxshell -c ':python print(2+2)'\n"
        "python3 -m rpos.rxshell --list-languages\n"
        "```\n\n"
        "## Languages\n\n"
        "shell · python · javascript · powershell (host interpreters).\n"
        "Unknown languages and missing runtimes **fail closed** — no fake success.\n"
        "Not full Microsoft PowerShell feature parity.\n",
        encoding="utf-8",
    )


def _write_version(stage: Path, version: str) -> None:
    (stage / "VERSION").write_text(version + "\n", encoding="utf-8")
    (stage / "RPOS_VERSION").write_text(version + "\n", encoding="utf-8")



def _write_single_click(stage: Path, slot: dict[str, Any]) -> None:
    """Primary single-click RESTORE executable entry (post-advisory gate)."""
    installer_dir = stage / "rpos" / "installer"
    if slot["os"] == "windows":
        src = installer_dir / "RESTORE_click.ps1"
        dest = stage / "RESTORE_click.ps1"
        if src.is_file():
            shutil.copy2(src, dest)
        else:
            dest.write_text(
                "# fallback invokes python module\n"
                "python -m rpos.installer restore --yes-advisories --confirm RESTORE\n",
                encoding="utf-8",
            )
        # Primary one-click name
        (stage / "RESTORE_rpOS.cmd").write_text(
            """@echo off
setlocal
set ROOT=%~dp0
set PYTHONPATH=%ROOT%;%PYTHONPATH%
cd /d "%ROOT%"
if "%RPOS_PREFIX%"=="" set RPOS_PREFIX=%USERPROFILE%\\.rpos\\install
echo === RESTORE rpOS single-click (advisories required) ===
python -m rpos.installer advisories
set /p CONFIRM=Type RESTORE to confirm absolute wipe intent: 
python -m rpos.installer restore --yes-advisories --confirm %CONFIRM% --prefix "%RPOS_PREFIX%"
if errorlevel 1 exit /b 1
echo Ned will guide timezone, language, and rpMail email.
python -m rpos.installer oobe --prefix "%RPOS_PREFIX%"
echo Ned: locked guide — Pens, Tables, then Slides.
python -m rpos.installer apps-tour --prefix "%RPOS_PREFIX%"
""",
            encoding="utf-8",
        )
    else:
        src = installer_dir / "RESTORE_click.sh"
        dest = stage / "RESTORE_click.sh"
        if src.is_file():
            shutil.copy2(src, dest)
            dest.chmod(dest.stat().st_mode | 0o111)
        # Primary one-click name
        click = stage / "RESTORE_rpOS"
        click.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
PREFIX="${RPOS_PREFIX:-$HOME/.rpos/install}"
echo "=== RESTORE rpOS single-click (advisories required) ==="
python3 -m rpos.installer advisories
echo ""
read -r -p "Type RESTORE to confirm absolute wipe intent: " CONFIRM
python3 -m rpos.installer restore --yes-advisories --confirm "$CONFIRM" --prefix "$PREFIX"
echo ""
echo "Ned will guide timezone, language, and rpMail email."
python3 -m rpos.installer oobe --prefix "$PREFIX"
echo ""
echo "Ned: locked guide — Pens, then Tables, then Slides."
python3 -m rpos.installer apps-tour --prefix "$PREFIX"
""",
            encoding="utf-8",
        )
        click.chmod(click.stat().st_mode | 0o111)


def _write_unix_install(stage: Path, slot: dict[str, Any]) -> None:
    install = stage / "install.sh"
    install.write_text(
        f'''#!/usr/bin/env bash
# rpOS desktop installer — {slot["platform"]} ({slot["arch"]})
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${{RPOS_PREFIX:-/opt/rpos}}"
echo "[rpos-install] product=rpOS version={slot["version"]} platform={slot["platform"]}"
echo "[rpos-install] staging foundation tree to $PREFIX"
mkdir -p "$PREFIX"
cp -a "$ROOT/rpos/." "$PREFIX/"
cp -f "$ROOT/VERSION" "$PREFIX/VERSION" 2>/dev/null || true
cp -f "$ROOT/CAPABILITY.md" "$PREFIX/CAPABILITY.md" 2>/dev/null || true
echo "[rpos-install] done. Tree: $PREFIX"
echo "[rpos-install] Companion SDKs: see $PREFIX/sdk/ and private GitHub rpMail/rpOffice/mishi"
echo "[rpos-install] For wipe-intent path (WARNED): bash $ROOT/RESTORE_rpos.sh"
''',
        encoding="utf-8",
    )
    install.chmod(install.stat().st_mode | 0o111)

    restore = stage / "RESTORE_rpos.sh"
    restore.write_text(
        f'''#!/usr/bin/env bash
# RESTORE rpOS — DESKTOP WIPE INTENT (requires explicit confirmation)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "============================================================"
echo "  RESTORE rpOS — DESTRUCTIVE PATH WARNING"
echo "  Platform: {slot["platform"]} / {slot["arch"]}"
echo "============================================================"
echo "This entry is the product *intent* for a from-scratch OS install"
echo "after the operator consents to wipe. It will NOT silently reformat"
echo "your disk. Type RESTORE to continue install-only staging, or Ctrl-C."
read -r CONFIRM
if [[ "$CONFIRM" != "RESTORE" ]]; then
  echo "Aborted (confirmation was not RESTORE)."
  exit 1
fi
echo "[rpos-restore] confirmed — running foundation install (no silent disk wipe binary)."
bash "$ROOT/install.sh"
echo "[rpos-restore] foundation installed. Full-disk imaging remains operator-controlled."
''',
        encoding="utf-8",
    )
    restore.chmod(restore.stat().st_mode | 0o111)

    bin_dir = stage / "bin"
    bin_dir.mkdir(exist_ok=True)
    launcher = bin_dir / "rpos-install"
    launcher.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/install.sh" "$@"
""",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | 0o111)

    (stage / "README.md").write_text(
        f"# rpOS {slot['version']} — {slot['platform']}\n\n"
        f"**Desktop installable** ({slot['os']} / {slot['arch']}).\n\n"
        "```bash\n"
        "bash install.sh\n"
        "# optional warned restore path:\n"
        "bash RESTORE_rpos.sh\n"
        "```\n\n"
        f"{slot['honesty']}\n\n"
        "Not for iOS/Android.\n",
        encoding="utf-8",
    )


def _write_windows_install(stage: Path, slot: dict[str, Any]) -> None:
    (stage / "install.ps1").write_text(
        f'''# rpOS desktop installer — Windows
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Prefix = if ($env:RPOS_PREFIX) {{ $env:RPOS_PREFIX }} else {{ Join-Path $env:ProgramData "rpos" }}
Write-Host "[rpos-install] product=rpOS version={slot["version"]} platform=windows"
Write-Host "[rpos-install] staging foundation tree to $Prefix"
New-Item -ItemType Directory -Force -Path $Prefix | Out-Null
Copy-Item -Recurse -Force (Join-Path $Root "rpos\\*") $Prefix
if (Test-Path (Join-Path $Root "VERSION")) {{ Copy-Item -Force (Join-Path $Root "VERSION") $Prefix }}
if (Test-Path (Join-Path $Root "CAPABILITY.md")) {{ Copy-Item -Force (Join-Path $Root "CAPABILITY.md") $Prefix }}
Write-Host "[rpos-install] done. Tree: $Prefix"
Write-Host "[rpos-install] For wipe-intent path (WARNED): .\\RESTORE_rpos.ps1"
''',
        encoding="utf-8",
    )
    (stage / "RESTORE_rpos.ps1").write_text(
        f'''# RESTORE rpOS — DESKTOP WIPE INTENT (requires explicit confirmation)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "============================================================"
Write-Host "  RESTORE rpOS — DESTRUCTIVE PATH WARNING"
Write-Host "  Platform: windows / x86_64"
Write-Host "============================================================"
Write-Host "Type RESTORE to continue foundation install (no silent disk wipe)."
$Confirm = Read-Host "Confirmation"
if ($Confirm -ne "RESTORE") {{
  Write-Host "Aborted."
  exit 1
}}
& (Join-Path $Root "install.ps1")
Write-Host "[rpos-restore] foundation installed. Full-disk imaging remains operator-controlled."
''',
        encoding="utf-8",
    )
    bin_dir = stage / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "rpos-install.cmd").write_text(
        """@echo off
setlocal
set ROOT=%~dp0..
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\\install.ps1" %*
""",
        encoding="utf-8",
    )
    (stage / "README.md").write_text(
        f"# rpOS {slot['version']} — windows\n\n"
        "**Desktop installable** (Windows x64).\n\n"
        "```powershell\n"
        ".\\install.ps1\n"
        ".\\RESTORE_rpos.ps1\n"
        "```\n\n"
        f"{slot['honesty']}\n\n"
        "Not for iOS/Android.\n",
        encoding="utf-8",
    )


def _stage_platform(slot: dict[str, Any], stage: Path) -> None:
    stage.mkdir(parents=True, exist_ok=True)
    _write_version(stage, slot["version"])
    _write_capability(stage, slot)
    _copy_rpos_tree(stage)
    if slot["os"] == "windows":
        _write_windows_install(stage, slot)
    else:
        _write_unix_install(stage, slot)
    _write_single_click(stage, slot)
    _write_rxshell_launchers(stage, slot)
    for p in stage.rglob("*.priv"):
        raise RuntimeError(f"refusing private key: {p}")


def _archive_stage(slot: dict[str, Any], stage: Path, dest: Path) -> None:
    if dest.exists():
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if slot["format"] == "tar.gz":
        with tarfile.open(dest, "w:gz") as tf:
            tf.add(stage, arcname=stage.name)
    elif slot["format"] == "zip":
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    arc = f"{stage.name}/{path.relative_to(stage).as_posix()}"
                    zf.write(path, arcname=arc)
    else:
        raise ValueError(slot["format"])


def package_one(slot: dict[str, Any], *, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / slot["archive_name"]
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / slot["stage_top"]
        _stage_platform(slot, stage)
        _archive_stage(slot, stage, dest)
    size = dest.stat().st_size
    digest = sha256_file(dest)
    return {
        "ok": size > 0,
        "platform": slot["platform"],
        "os": slot["os"],
        "arch": slot["arch"],
        "version": slot["version"],
        "archive": str(dest),
        "archive_name": slot["archive_name"],
        "bytes": size,
        "sha256": digest,
        "install_entry": slot["install_entry"],
        "restore_entry": slot["restore_entry"],
        "installable": True,
        "mobile": False,
    }


def package_all(
    *,
    version: str = RPOS_VERSION,
    out_dir: Path | None = None,
    platforms: list[str] | None = None,
) -> dict[str, Any]:
    ver = (version or RPOS_VERSION).strip() or RPOS_VERSION
    out = out_dir or (ROOT / "releases" / "rpos" / ver)
    out.mkdir(parents=True, exist_ok=True)
    matrix = platform_package_matrix(ver)
    if platforms:
        wanted = {p.lower().strip() for p in platforms}
        matrix = [s for s in matrix if s["platform"] in wanted]
        if not matrix:
            return {"ok": False, "error": f"no platforms match {sorted(wanted)}", "version": ver}

    packages: list[dict[str, Any]] = []
    for slot in matrix:
        print(f"packaging rpOS {slot['platform']}…", flush=True)
        r = package_one(slot, out_dir=out)
        packages.append(r)
        print(
            f"  [{'ok' if r['ok'] else 'FAIL'}] {r['archive_name']} ({r['bytes']} bytes)",
            flush=True,
        )

    sha_map = {p["archive_name"]: p["sha256"] for p in packages if p.get("ok")}
    (out / "SHA256SUMS.json").write_text(json.dumps(sha_map, indent=2) + "\n", encoding="utf-8")
    (out / "SHA256SUMS").write_text(
        "\n".join(f"{h}  {n}" for n, h in sorted(sha_map.items())) + ("\n" if sha_map else ""),
        encoding="utf-8",
    )
    all_ok = all(p.get("ok") for p in packages) and len(packages) > 0
    result: dict[str, Any] = {
        "ok": all_ok,
        "product": "rpOS",
        "version": ver,
        "out_dir": str(out),
        "platforms": [p["platform"] for p in packages],
        "linux_arches": linux_arches(ver),
        "excluded_mobile": excluded_mobile_platforms(),
        "package_count": len(packages),
        "packages": packages,
        "matrix": platform_package_matrix(ver),
    }
    if not all_ok:
        result["error"] = "one or more packages failed"
    (out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out / "README.md").write_text(
        f"# rpOS {ver} desktop installers\n\n"
        "Installable for **Windows**, **macOS**, and **Linux** (x86_64 + aarch64).\n"
        "**Not** for iOS / Android.\n\n"
        "| Platform | Archive |\n|----------|---------|\n"
        + "\n".join(
            f"| `{p['platform']}` | `{p['archive_name']}` |"
            for p in packages
            if p.get("ok")
        )
        + "\n\nBuild: `python3 scripts/package_rpos.py`\n",
        encoding="utf-8",
    )
    print(f"rpos manifest: {out / 'manifest.json'}", flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", default=RPOS_VERSION)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--platform",
        action="append",
        dest="platforms",
        help="Limit slots: windows macos linux-x86_64 linux-aarch64",
    )
    ap.add_argument("--inventory", action="store_true")
    args = ap.parse_args(argv)
    if args.inventory:
        print(
            json.dumps(
                {
                    "version": args.version,
                    "platforms": catalog_platforms(args.version),
                    "linux_arches": linux_arches(args.version),
                    "excluded_mobile": excluded_mobile_platforms(),
                    "matrix": platform_package_matrix(args.version),
                },
                indent=2,
            )
        )
        return 0
    r = package_all(version=args.version, out_dir=args.out_dir, platforms=args.platforms)
    if not r.get("ok"):
        print(r.get("error") or "failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
