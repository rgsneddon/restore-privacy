#!/usr/bin/env python3
"""Package residual **node installer** materials for every product platform.

Monopin **1.0.0** under ``releases/node-installer/1.0.0/``.

Platform matrix (honest residual capability)::

  linux   — residual-capable full TUN node host install (install.sh + node tree)
  macos   — lab / operator materials (no full residual TUN host claim)
  windows — lab / operator materials (no full residual TUN host claim)
  android — honest lab/reference package (cannot host residual TUN node)
  ios     — honest lab/reference package (cannot host residual TUN node)

Produces archives + SHA256SUMS.json + manifest.json. Pure inventory helpers
(``platform_package_matrix``) are testable without building archives.

Usage::

  python3 scripts/package_node_installers.py              # all platforms
  python3 scripts/package_node_installers.py --inventory  # matrix JSON only
  python3 scripts/package_node_installers.py --platform linux
  python3 scripts/package_node_installers.py --skip-wheels
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
NODE_INSTALLER_VERSION = "1.0.0"
OUT_DIR = ROOT / "releases" / "node-installer" / NODE_INSTALLER_VERSION

# Residual node host install scripts that ship in every package tree.
NODE_INSTALL_SCRIPTS = (
    "install.sh",
    "install_disk_encryption.sh",
    "install_dns.sh",
    "install_host_privacy.sh",
    "install_shutdown_wipe.sh",
    "install_zram_luks.sh",
    "rpt_shutdown_wipe.sh",
)

# Optional conf files bundled with residual install.
NODE_INSTALL_CONFS = ("unbound-rpt.conf",)

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def platform_package_matrix(
    version: str = NODE_INSTALLER_VERSION,
) -> list[dict[str, Any]]:
    """Pure inventory of platform package slots (no I/O).

    Each slot names the archive, residual capability, install entry, and
    honesty note for lab-only platforms.
    """
    ver = (version or NODE_INSTALLER_VERSION).strip() or NODE_INSTALLER_VERSION
    return [
        {
            "platform": "linux",
            "version": ver,
            "archive_name": f"restore-privacy-node-installer-{ver}-linux-x64.tar.gz",
            "stage_top": f"restore-privacy-node-installer-{ver}-linux",
            "format": "tar.gz",
            "residual_capable": True,
            "capability": "residual",
            "install_entry": "install.sh",
            "launch_entry": "bin/rpt-node-install",
            "includes_node_tree": True,
            "includes_node_operator": True,
            "honesty": (
                "Full residual TUN node host. Run install.sh as root on a Linux VPS "
                "(apt/systemd, CAP_NET_ADMIN). Includes node/*.sh residual installers "
                "and node_operator lab GUI."
            ),
        },
        {
            "platform": "macos",
            "version": ver,
            "archive_name": f"restore-privacy-node-installer-{ver}-macos.zip",
            "stage_top": f"restore-privacy-node-installer-{ver}-macos",
            "format": "zip",
            "residual_capable": False,
            "capability": "lab",
            "install_entry": "install.sh",
            "launch_entry": "bin/rpt-node-operator",
            "includes_node_tree": True,
            "includes_node_operator": True,
            "honesty": (
                "Lab / operator package only. Full residual TUN node host is Linux-only. "
                "macOS can run node_operator lab mode and inspect installer materials; "
                "do not claim production residual node hosting on this platform."
            ),
        },
        {
            "platform": "windows",
            "version": ver,
            "archive_name": f"restore-privacy-node-installer-{ver}-windows-x64.zip",
            "stage_top": f"restore-privacy-node-installer-{ver}-windows",
            "format": "zip",
            "residual_capable": False,
            "capability": "lab",
            "install_entry": "install.ps1",
            "launch_entry": "bin/rpt-node-operator.cmd",
            "includes_node_tree": True,
            "includes_node_operator": True,
            "honesty": (
                "Lab / operator package only. Full residual TUN node host is Linux-only. "
                "Windows can run node_operator lab mode and hold residual installer "
                "scripts for deploy to a Linux host; no Windows residual TUN host."
            ),
        },
        {
            "platform": "android",
            "version": ver,
            "archive_name": f"restore-privacy-node-installer-{ver}-android.zip",
            "stage_top": f"restore-privacy-node-installer-{ver}-android",
            "format": "zip",
            "residual_capable": False,
            "capability": "lab_reference",
            "install_entry": "README.md",
            "launch_entry": None,
            "includes_node_tree": True,
            "includes_node_operator": False,
            "honesty": (
                "Honest reference package. Android devices cannot host a residual "
                "TUN VPN node. Materials are for operator review / documentation; "
                "deploy residual nodes on Linux. End-user Connect uses the Suite client APK."
            ),
        },
        {
            "platform": "ios",
            "version": ver,
            "archive_name": f"restore-privacy-node-installer-{ver}-ios.zip",
            "stage_top": f"restore-privacy-node-installer-{ver}-ios",
            "format": "zip",
            "residual_capable": False,
            "capability": "lab_reference",
            "install_entry": "README.md",
            "launch_entry": None,
            "includes_node_tree": True,
            "includes_node_operator": False,
            "honesty": (
                "Honest reference package. iOS devices cannot host a residual "
                "TUN VPN node. Materials are for operator review / documentation; "
                "deploy residual nodes on Linux. End-user Connect uses the Suite client."
            ),
        },
    ]


def catalog_platforms(version: str = NODE_INSTALLER_VERSION) -> list[str]:
    """Ordered platform ids from the product matrix."""
    return [s["platform"] for s in platform_package_matrix(version)]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_ignore(_dir: str, names: list[str]) -> list[str]:
    skip = {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "node_modules",
        ".dart_tool",
        "build",
        "windows",
        "native",
    }
    out: list[str] = []
    for n in names:
        if n in skip or n.endswith(".pyc") or n.endswith(".priv") or n.endswith(".dll"):
            out.append(n)
    return out


def _copy_node_tree(stage: Path) -> None:
    """Copy residual node runtime + installer scripts into stage/node/."""
    src = ROOT / "node"
    dst = stage / "node"
    if not src.is_dir():
        raise FileNotFoundError(f"missing node tree: {src}")
    shutil.copytree(src, dst, ignore=_copy_ignore, dirs_exist_ok=True)
    # Ensure residual install scripts are present and executable-bit preserved.
    for name in NODE_INSTALL_SCRIPTS:
        p = dst / name
        if not p.is_file():
            raise FileNotFoundError(f"node installer script missing: {name}")
        p.chmod(p.stat().st_mode | 0o111)
    for name in NODE_INSTALL_CONFS:
        p = dst / name
        if p.is_file():
            continue  # optional but preferred


def _copy_node_operator(stage: Path) -> None:
    src = ROOT / "node_operator"
    if not src.is_dir():
        return
    shutil.copytree(src, stage / "node_operator", ignore=_copy_ignore, dirs_exist_ok=True)


def _copy_requirements(stage: Path) -> None:
    req = ROOT / "requirements.txt"
    if req.is_file():
        shutil.copy2(req, stage / "requirements.txt")
    else:
        (stage / "requirements.txt").write_text("cryptography>=41\n", encoding="utf-8")


def _write_capability(stage: Path, slot: dict[str, Any]) -> None:
    residual = "yes" if slot["residual_capable"] else "no"
    body = (
        f"# Capability — {slot['platform']}\n\n"
        f"- **version:** {slot['version']}\n"
        f"- **capability:** {slot['capability']}\n"
        f"- **residual_capable:** {residual}\n"
        f"- **install_entry:** {slot['install_entry']}\n"
        f"- **launch_entry:** {slot.get('launch_entry') or '(none)'}\n\n"
        f"## Honesty\n\n{slot['honesty']}\n"
    )
    (stage / "CAPABILITY.md").write_text(body, encoding="utf-8")
    (stage / "CAPABILITY.json").write_text(
        json.dumps(
            {
                "platform": slot["platform"],
                "version": slot["version"],
                "capability": slot["capability"],
                "residual_capable": slot["residual_capable"],
                "install_entry": slot["install_entry"],
                "launch_entry": slot.get("launch_entry"),
                "honesty": slot["honesty"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_version_files(stage: Path, version: str) -> None:
    (stage / "VERSION").write_text(version + "\n", encoding="utf-8")
    (stage / "NODE_INSTALLER_VERSION").write_text(version + "\n", encoding="utf-8")


def _write_linux_install(stage: Path) -> None:
    content = r'''#!/usr/bin/env bash
# Residual node installer entry — Linux only (full TUN host).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Full residual node install is Linux-only. See CAPABILITY.md." >&2
  exit 1
fi
if [[ ! -f "$ROOT/node/install.sh" ]]; then
  echo "missing node/install.sh" >&2
  exit 1
fi
echo "[node-installer] residual install via node/install.sh"
# Prefer running residual installer from the packaged node tree
export INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
bash "$ROOT/node/install.sh" "$@"
'''
    p = stage / "install.sh"
    p.write_text(content, encoding="utf-8")
    p.chmod(p.stat().st_mode | 0o111)

    bin_dir = stage / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / "rpt-node-install"
    launcher.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/install.sh" "$@"
""",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | 0o111)

    # Operator lab launcher on residual hosts too
    op = bin_dir / "rpt-node-operator"
    op.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python" ]; then
  exec "$ROOT/.venv/bin/python" -m node_operator "$@"
fi
exec python3 -m node_operator "$@"
""",
        encoding="utf-8",
    )
    op.chmod(op.stat().st_mode | 0o111)

    (stage / "README.md").write_text(
        f"# Restore Privacy — Node Installer {NODE_INSTALLER_VERSION} (Linux)\n\n"
        "**Residual-capable** full TUN node host package.\n\n"
        "```bash\n"
        "sudo bash install.sh\n"
        "# or\n"
        "sudo ./bin/rpt-node-install\n"
        "```\n\n"
        "Lab operator GUI (optional):\n\n"
        "```bash\n"
        "./bin/rpt-node-operator --smoke\n"
        "```\n\n"
        "See `CAPABILITY.md` and `node/install.sh`.\n",
        encoding="utf-8",
    )


def _write_macos_install(stage: Path) -> None:
    content = r'''#!/usr/bin/env bash
# Node installer lab setup — macOS (not residual TUN host).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
echo "[node-installer] macOS lab package — see CAPABILITY.md (not residual TUN host)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 required" >&2
  exit 1
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q -r requirements.txt || \
  python -m pip install -q 'cryptography>=41'
chmod +x bin/rpt-node-operator 2>/dev/null || true
echo "Lab ready. Launch: $ROOT/bin/rpt-node-operator --smoke"
echo "Residual node host install remains Linux-only (node/install.sh on a VPS)."
'''
    p = stage / "install.sh"
    p.write_text(content, encoding="utf-8")
    p.chmod(p.stat().st_mode | 0o111)

    bin_dir = stage / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    op = bin_dir / "rpt-node-operator"
    op.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python" ]; then
  exec "$ROOT/.venv/bin/python" -m node_operator "$@"
fi
exec python3 -m node_operator "$@"
""",
        encoding="utf-8",
    )
    op.chmod(op.stat().st_mode | 0o111)

    (stage / "README.md").write_text(
        f"# Restore Privacy — Node Installer {NODE_INSTALLER_VERSION} (macOS)\n\n"
        "**Lab package** — not a residual TUN node host.\n\n"
        "```bash\n"
        "bash install.sh\n"
        "./bin/rpt-node-operator --smoke\n"
        "```\n\n"
        "Deploy residual nodes with the **Linux** package on a VPS.\n"
        "See `CAPABILITY.md`.\n",
        encoding="utf-8",
    )


def _write_windows_install(stage: Path) -> None:
    ps1 = r'''# Node installer lab setup — Windows (not residual TUN host).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
Write-Host "[node-installer] Windows lab package — see CAPABILITY.md (not residual TUN host)"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { throw "python required on PATH" }
if (-not (Test-Path ".venv")) {
  & $py.Source -m venv .venv
}
$pip = Join-Path $Root ".venv\Scripts\pip.exe"
$python = Join-Path $Root ".venv\Scripts\python.exe"
& $pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
  & $pip install -q "cryptography>=41"
}
Write-Host "Lab ready. Launch: .\bin\rpt-node-operator.cmd --smoke"
Write-Host "Residual node host install remains Linux-only (node\install.sh on a VPS)."
'''
    (stage / "install.ps1").write_text(ps1, encoding="utf-8")

    bin_dir = stage / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "rpt-node-operator.cmd").write_text(
        """@echo off
setlocal
set ROOT=%~dp0..
cd /d "%ROOT%"
if exist "%ROOT%\\.venv\\Scripts\\python.exe" (
  "%ROOT%\\.venv\\Scripts\\python.exe" -m node_operator %*
  exit /b %ERRORLEVEL%
)
python -m node_operator %*
""",
        encoding="utf-8",
    )

    (stage / "README.md").write_text(
        f"# Restore Privacy — Node Installer {NODE_INSTALLER_VERSION} (Windows)\n\n"
        "**Lab package** — not a residual TUN node host.\n\n"
        "```powershell\n"
        ".\\install.ps1\n"
        ".\\bin\\rpt-node-operator.cmd --smoke\n"
        "```\n\n"
        "Deploy residual nodes with the **Linux** package on a VPS.\n"
        "See `CAPABILITY.md`.\n",
        encoding="utf-8",
    )


def _write_mobile_readme(stage: Path, slot: dict[str, Any]) -> None:
    plat = slot["platform"]
    (stage / "README.md").write_text(
        f"# Restore Privacy — Node Installer {slot['version']} ({plat})\n\n"
        f"**Honest reference package** — `{plat}` cannot host a residual TUN VPN node.\n\n"
        "This archive ships residual **node installer materials** for operator review "
        "and documentation. Production residual nodes run on **Linux** "
        f"(see `restore-privacy-node-installer-{slot['version']}-linux-x64.tar.gz`).\n\n"
        "End-user Connect on this device uses the Suite client package, not this archive.\n\n"
        "Contents:\n"
        "- `node/` — residual node Python runtime + Linux install scripts\n"
        "- `CAPABILITY.md` / `CAPABILITY.json` — honesty pin\n"
        "- `VERSION` / `NODE_INSTALLER_VERSION`\n\n"
        f"{slot['honesty']}\n",
        encoding="utf-8",
    )


def _stage_platform(slot: dict[str, Any], stage: Path) -> None:
    """Populate stage directory for one platform slot."""
    stage.mkdir(parents=True, exist_ok=True)
    _write_version_files(stage, slot["version"])
    _write_capability(stage, slot)
    _copy_node_tree(stage)
    _copy_requirements(stage)

    if slot.get("includes_node_operator"):
        _copy_node_operator(stage)

    plat = slot["platform"]
    if plat == "linux":
        _write_linux_install(stage)
    elif plat == "macos":
        _write_macos_install(stage)
    elif plat == "windows":
        _write_windows_install(stage)
    elif plat in ("android", "ios"):
        _write_mobile_readme(stage, slot)
    else:
        raise ValueError(f"unknown platform: {plat}")

    # Refuse private keys
    for p in stage.rglob("*.priv"):
        raise RuntimeError(f"refusing private key in package: {p}")


def _archive_stage(slot: dict[str, Any], stage: Path, dest: Path) -> None:
    if dest.exists():
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fmt = slot["format"]
    if fmt == "tar.gz":
        with tarfile.open(dest, "w:gz") as tf:
            tf.add(stage, arcname=stage.name)
    elif fmt == "zip":
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    arcname = f"{stage.name}/{path.relative_to(stage).as_posix()}"
                    zf.write(path, arcname=arcname)
    else:
        raise ValueError(f"unknown format: {fmt}")


def package_one_platform(
    slot: dict[str, Any],
    *,
    out_dir: Path,
) -> dict[str, Any]:
    """Build one platform archive. Returns inventory dict for that slot."""
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / slot["archive_name"]
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / slot["stage_top"]
        _stage_platform(slot, stage)
        _archive_stage(slot, stage, dest)

    size = dest.stat().st_size
    digest = sha256_file(dest)
    result: dict[str, Any] = {
        "ok": size > 0,
        "platform": slot["platform"],
        "version": slot["version"],
        "archive": str(dest),
        "archive_name": slot["archive_name"],
        "bytes": size,
        "sha256": digest,
        "format": slot["format"],
        "residual_capable": slot["residual_capable"],
        "capability": slot["capability"],
        "install_entry": slot["install_entry"],
        "launch_entry": slot.get("launch_entry"),
        "honesty": slot["honesty"],
    }
    if size <= 0:
        result["ok"] = False
        result["error"] = "empty archive"
    return result


def package_all_platforms(
    *,
    version: str = NODE_INSTALLER_VERSION,
    out_dir: Path | None = None,
    platforms: list[str] | None = None,
) -> dict[str, Any]:
    """Build node-installer packages for requested platforms (default: all)."""
    ver = (version or NODE_INSTALLER_VERSION).strip() or NODE_INSTALLER_VERSION
    out = out_dir or (ROOT / "releases" / "node-installer" / ver)
    out.mkdir(parents=True, exist_ok=True)
    matrix = platform_package_matrix(ver)
    if platforms:
        wanted = {p.lower().strip() for p in platforms}
        matrix = [s for s in matrix if s["platform"] in wanted]
        if not matrix:
            return {
                "ok": False,
                "error": f"no matching platforms for {sorted(wanted)}",
                "version": ver,
            }

    packages: list[dict[str, Any]] = []
    for slot in matrix:
        print(f"packaging node-installer {slot['platform']}…", flush=True)
        r = package_one_platform(slot, out_dir=out)
        packages.append(r)
        status = "ok" if r.get("ok") else "FAIL"
        print(
            f"  [{status}] {r['archive_name']} ({r.get('bytes', 0)} bytes) "
            f"residual_capable={r.get('residual_capable')}",
            flush=True,
        )

    sha_map = {
        p["archive_name"]: p["sha256"]
        for p in packages
        if p.get("ok") and p.get("sha256")
    }
    sums_path = out / "SHA256SUMS.json"
    sums_path.write_text(json.dumps(sha_map, indent=2) + "\n", encoding="utf-8")

    # GNU-style text sums too
    lines = [f"{digest}  {name}" for name, digest in sorted(sha_map.items())]
    (out / "SHA256SUMS").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    all_ok = all(p.get("ok") for p in packages) and len(packages) > 0
    catalog = [p["platform"] for p in packages]
    result: dict[str, Any] = {
        "ok": all_ok,
        "version": ver,
        "out_dir": str(out),
        "platforms": catalog,
        "required_platforms": catalog_platforms(ver),
        "package_count": len(packages),
        "packages": packages,
        "sha256sums": str(sums_path),
        "matrix": platform_package_matrix(ver),
    }
    if not all_ok:
        result["error"] = "one or more platform packages failed"
    man_path = out / "manifest.json"
    man_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"node-installer manifest: {man_path}", flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--version",
        default=NODE_INSTALLER_VERSION,
        help=f"Node installer monopin (default {NODE_INSTALLER_VERSION})",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Override output directory",
    )
    ap.add_argument(
        "--platform",
        action="append",
        dest="platforms",
        help="Limit to platform id (repeatable): linux macos windows android ios",
    )
    ap.add_argument(
        "--inventory",
        action="store_true",
        help="Print platform matrix JSON and exit (no packaging)",
    )
    # Accepted for CLI parity with package_node_operator_linux; node-installer
    # packages do not download manylinux wheels (operator Linux does).
    ap.add_argument(
        "--skip-wheels",
        action="store_true",
        help="No-op here (node-installer has no wheel matrix); kept for CLI parity",
    )
    args = ap.parse_args(argv)

    if args.inventory:
        inv = {
            "version": args.version,
            "platforms": catalog_platforms(args.version),
            "matrix": platform_package_matrix(args.version),
        }
        print(json.dumps(inv, indent=2))
        return 0

    r = package_all_platforms(
        version=args.version,
        out_dir=args.out_dir,
        platforms=args.platforms,
    )
    if not r.get("ok"):
        print(r.get("error") or "package failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
