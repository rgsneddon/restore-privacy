#!/usr/bin/env python3
"""Package **Node Operator GUI** for Linux as monopin **1.0.0**.

Distinct from the end-user client monopin (0.6.0): this archive is the residual
node operator shell (``python -m node_operator``) only.

Produces::

  releases/node-operator/1.0.0/restore-privacy-node-operator-1.0.0-linux-x64.tar.gz

Layout inside the archive::

  restore-privacy-node-operator-1.0.0-linux/
    node_operator/ node/ client/ scripts/ status_page/ product/ secrets/
    requirements.txt VERSION NODE_OPERATOR_VERSION
    wheels/          # full manylinux × CPython matrix (same as package_linux)
    install.sh
    bin/rpt-node-operator

**All Linux versionables:** reuses ``package_linux._PY_VERSIONS`` ×
``_PLATFORMS`` (CPython 3.8–3.13 × manylinux2014 / 2_17 / 2_28 x86_64).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NODE_OPERATOR_VERSION = "1.0.0"
OUT_DIR = ROOT / "releases" / "node-operator" / NODE_OPERATOR_VERSION
ARCHIVE_NAME = (
    f"restore-privacy-node-operator-{NODE_OPERATOR_VERSION}-linux-x64.tar.gz"
)
STAGE_TOP = f"restore-privacy-node-operator-{NODE_OPERATOR_VERSION}-linux"

# Ensure scripts/ is importable for package_linux helpers
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def linux_versionable_matrix() -> dict[str, Any]:
    """Product manylinux × CPython matrix (same set as client Linux packager)."""
    import package_linux as pl

    py_versions = list(pl._PY_VERSIONS)
    platforms = list(pl._PLATFORMS)
    pairs = [(py, plat) for py in py_versions for plat in platforms]
    return {
        "python_abi_tags": py_versions,
        "platforms": platforms,
        "pair_count": len(pairs),
        "pairs": [{"python": py, "platform": plat} for py, plat in pairs],
        "source": "scripts/package_linux.py",
        "node_operator_version": NODE_OPERATOR_VERSION,
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory_wheels(wheels_dir: Path) -> dict[str, Any]:
    """Summarize downloaded wheels vs matrix tags (honest coverage report)."""
    matrix = linux_versionable_matrix()
    wheels = sorted(wheels_dir.glob("*.whl")) if wheels_dir.is_dir() else []
    names = [w.name for w in wheels]
    crypto = [n for n in names if n.startswith("cryptography-") and "manylinux" in n]
    # Which py/plat tags appear in filenames
    seen_py: set[str] = set()
    seen_plat: set[str] = set()
    for n in names:
        for py in matrix["python_abi_tags"]:
            if f"cp{py}" in n or f"py3" in n:
                seen_py.add(py)
        for plat in matrix["platforms"]:
            if plat in n:
                seen_plat.add(plat)
    return {
        "wheel_count": len(wheels),
        "cryptography_manylinux_count": len(crypto),
        "matrix_pair_count": matrix["pair_count"],
        "python_abi_tags_requested": matrix["python_abi_tags"],
        "platforms_requested": matrix["platforms"],
        "python_tags_seen_in_wheels": sorted(seen_py),
        "platforms_seen_in_wheels": sorted(seen_plat),
        "wheel_names": names[:80],
    }


def write_install_sh(stage: Path) -> None:
    content = r'''#!/usr/bin/env bash
# Node Operator Linux installer — bundled manylinux wheels only (no network pip).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 required" >&2
  exit 1
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --no-index --find-links=wheels -r requirements.txt \
  || python -m pip install --no-index --find-links=wheels cryptography cffi pycparser
chmod +x bin/rpt-node-operator 2>/dev/null || true
echo "Installed. Launch: $ROOT/bin/rpt-node-operator"
echo "Or: cd $ROOT && .venv/bin/python -m node_operator --smoke"
'''
    path = stage / "install.sh"
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def write_launcher(stage: Path) -> None:
    bin_dir = stage / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / "rpt-node-operator"
    launcher.write_text(
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
    launcher.chmod(launcher.stat().st_mode | 0o111)


def package_node_operator_linux(
    *,
    version: str = NODE_OPERATOR_VERSION,
    out_dir: Path | None = None,
    skip_wheels: bool = False,
) -> dict[str, Any]:
    """Build the Node Operator 1.0.0 Linux tarball. Returns inventory dict."""
    import package_linux as pl

    ver = (version or NODE_OPERATOR_VERSION).strip() or NODE_OPERATOR_VERSION
    out = out_dir or (ROOT / "releases" / "node-operator" / ver)
    out.mkdir(parents=True, exist_ok=True)
    archive_name = f"restore-privacy-node-operator-{ver}-linux-x64.tar.gz"
    dest = out / archive_name
    stage_name = f"restore-privacy-node-operator-{ver}-linux"
    matrix = linux_versionable_matrix()
    matrix["node_operator_version"] = ver

    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        "*.priv",
        "windows",
        "native",
        "*.dll",
        "build",
        ".dart_tool",
        "node_modules",
    )

    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / stage_name
        stage.mkdir()

        # Core operator tree
        for rel in (
            "node_operator",
            "node",
            "client",
            "requirements.txt",
            "README.md",
            "LICENSE",
        ):
            src = ROOT / rel
            if not src.exists():
                continue
            dst = stage / rel
            if src.is_dir():
                shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        # host_paid + downloads catalog helpers for upload-by-path / inventory
        scripts_dst = stage / "scripts"
        scripts_dst.mkdir(exist_ok=True)
        for name in (
            "host_paid_assets_vps.py",
            "package_linux.py",
            "package_node_operator_linux.py",
        ):
            src = ROOT / "scripts" / name
            if src.is_file():
                shutil.copy2(src, scripts_dst / name)

        sp_src = ROOT / "status_page"
        sp_dst = stage / "status_page"
        sp_dst.mkdir(exist_ok=True)
        for name in (
            "downloads.py",
            "payments.py",
            "coffee_link.py",
            "apple_package_audit.py",
            "__init__.py",
        ):
            src = sp_src / name
            if src.is_file():
                shutil.copy2(src, sp_dst / name)
            elif name == "__init__.py":
                (sp_dst / name).write_text("", encoding="utf-8")

        # Public product pubs only
        for dname in ("product", "secrets"):
            d = stage / dname
            d.mkdir(exist_ok=True)
            for pub in (
                "node_elgamal.pub",
                "de_node_elgamal.pub",
                "exit_node_elgamal.pub",
                "us_node_elgamal.pub",
            ):
                for base in (ROOT / "product", ROOT / "secrets"):
                    src = base / pub
                    if src.is_file() and src.stat().st_size >= 32:
                        shutil.copy2(src, d / pub)
                        break

        (stage / "VERSION").write_text(ver + "\n", encoding="utf-8")
        (stage / "NODE_OPERATOR_VERSION").write_text(ver + "\n", encoding="utf-8")
        # Operator identity pin (not client monopin)
        (stage / "client" / "VERSION").parent.mkdir(parents=True, exist_ok=True)
        # Keep client VERSION as-is from monorepo copy; operator pin is NODE_OPERATOR_VERSION

        wheels_dir = stage / "wheels"
        wheel_inv: dict[str, Any]
        if skip_wheels:
            wheels_dir.mkdir(exist_ok=True)
            wheel_inv = {
                "wheel_count": 0,
                "skipped": True,
                "reason": "skip_wheels",
                "matrix_pair_count": matrix["pair_count"],
            }
        else:
            print(
                f"Downloading manylinux wheels for full matrix "
                f"({matrix['pair_count']} py×plat pairs)…",
                flush=True,
            )
            wheels = pl.download_linux_wheels(wheels_dir)
            print(f"  {len(wheels)} wheel file(s)", flush=True)
            wheel_inv = inventory_wheels(wheels_dir)

        write_install_sh(stage)
        write_launcher(stage)

        (stage / "WHEEL_MATRIX.json").write_text(
            json.dumps({"matrix": matrix, "wheels": wheel_inv}, indent=2) + "\n",
            encoding="utf-8",
        )
        (stage / "NODE_OPERATOR_README.md").write_text(
            f"# Restore Privacy — Node Operator {ver} (Linux)\n\n"
            "Operator GUI for residual node lab + package deploy (not end-user Connect).\n\n"
            "```bash\n"
            "bash install.sh\n"
            "./bin/rpt-node-operator --smoke\n"
            "./bin/rpt-node-operator --port 18765\n"
            "```\n\n"
            f"Wheel matrix pairs: **{matrix['pair_count']}** "
            f"(CPython {', '.join(matrix['python_abi_tags'])} × "
            f"{len(matrix['platforms'])} manylinux tags).\n",
            encoding="utf-8",
        )

        for p in stage.rglob("*.priv"):
            raise RuntimeError(f"refusing private key in package: {p}")

        if dest.exists():
            dest.unlink()
        with tarfile.open(dest, "w:gz") as tf:
            tf.add(stage, arcname=stage.name)

    size = dest.stat().st_size
    digest = sha256_file(dest)
    result = {
        "ok": True,
        "version": ver,
        "archive": str(dest),
        "archive_name": archive_name,
        "bytes": size,
        "sha256": digest,
        "matrix": matrix,
        "wheels": wheel_inv,
        "entry": "python -m node_operator",
        "launcher": "bin/rpt-node-operator",
    }
    man_path = out / "manifest.json"
    man_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"node_operator package: {dest} ({size} bytes)")
    print(f"sha256: {digest}")
    if not skip_wheels and size < 200_000:
        print("WARNING: package smaller than expected for wheeled bundle", file=sys.stderr)
        result["ok"] = False
        result["error"] = "package too small for wheeled matrix"
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--version",
        default=NODE_OPERATOR_VERSION,
        help=f"Node Operator package version (default {NODE_OPERATOR_VERSION})",
    )
    ap.add_argument(
        "--skip-wheels",
        action="store_true",
        help="Skip pip download (structure-only; tests)",
    )
    ap.add_argument(
        "--matrix-only",
        action="store_true",
        help="Print versionable matrix JSON and exit",
    )
    args = ap.parse_args(argv)
    if args.matrix_only:
        print(json.dumps(linux_versionable_matrix(), indent=2))
        return 0
    r = package_node_operator_linux(
        version=args.version,
        skip_wheels=bool(args.skip_wheels),
    )
    if not r.get("ok"):
        print(r.get("error") or "package failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
