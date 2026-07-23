#!/usr/bin/env python3
"""Build local free-tier client packages labeled **3.3.3** (not published).

Free flavor:
- Version string always ``3.3.3``
- ``RPT_FREE_TIER=1`` / ``--dart-define=RPT_FREE_TIER=true``
- Locked lean Iceland residual (see client/free_tier.py)

Outputs under ``releases/free/3.3.3/`` only — never GH/VPS paid catalog.

Usage::

  # After flutter build macos --release --dart-define=RPT_FREE_TIER=true
  python3 scripts/build_free_3.3.3.py --apple-stage
  python3 scripts/build_free_3.3.3.py --linux
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREE_VERSION = "3.3.3"
OUT = ROOT / "releases" / "free" / FREE_VERSION

MACOS_APP = (
    ROOT
    / "client_app"
    / "build"
    / "macos"
    / "Build"
    / "Products"
    / "Release"
    / "restore_privacy_client.app"
)
IOS_APP = ROOT / "client_app" / "build" / "ios" / "iphoneos" / "Runner.app"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _assert_no_priv(root: Path) -> None:
    for p in root.rglob("*.priv"):
        raise RuntimeError(f"refusing to package private key material: {p}")


def stage_macos() -> Path | None:
    if not MACOS_APP.is_dir():
        print(
            f"skip macos: missing {MACOS_APP}\n"
            "  Build: cd client_app && flutter build macos --release "
            "--dart-define=RPT_FREE_TIER=true",
            file=sys.stderr,
        )
        return None
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"restore-privacy-client-free-{FREE_VERSION}-macos.zip"
    # Inject VERSION marker into Resources
    ver_path = MACOS_APP / "Contents" / "Resources" / "FREE_TIER_VERSION"
    ver_path.parent.mkdir(parents=True, exist_ok=True)
    ver_path.write_text(FREE_VERSION + "\n", encoding="utf-8")
    if dest.is_file():
        dest.unlink()
    subprocess.check_call(
        ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(MACOS_APP), str(dest)]
    )
    print(f"macos free: {dest} ({dest.stat().st_size} bytes)")
    return dest


def stage_ios() -> Path | None:
    if not IOS_APP.is_dir():
        print(f"skip ios: missing {IOS_APP}", file=sys.stderr)
        return None
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"restore-privacy-client-free-{FREE_VERSION}-ios.zip"
    if dest.is_file():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in IOS_APP.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(IOS_APP.parent).as_posix())
    print(f"ios free: {dest} ({dest.stat().st_size} bytes)")
    return dest


def stage_linux() -> Path | None:
    """Build free Linux via package_linux with RPT_FREE_TIER (does not touch paid OUT)."""
    script = ROOT / "scripts" / "package_linux.py"
    if not script.is_file():
        return None
    env = os.environ.copy()
    env["RPT_FREE_TIER"] = "1"
    env["RPT_PRODUCT_VERSION"] = FREE_VERSION
    # Never leave free env in the parent process after package_linux.
    print("linux: packaging free 3.3.3 via package_linux RPT_FREE_TIER=1 …")
    try:
        subprocess.check_call([sys.executable, str(script)], cwd=str(ROOT), env=env)
    except subprocess.CalledProcessError as exc:
        print(f"linux package failed: {exc}", file=sys.stderr)
        return None
    dest = OUT / f"restore-privacy-client-free-{FREE_VERSION}-linux-x64.tar.gz"
    if not dest.is_file():
        print(f"skip linux: expected {dest}", file=sys.stderr)
        return None
    # Structural proof: VERSION pin + free launcher markers
    import tarfile

    with tarfile.open(dest, "r:gz") as tf:
        names = tf.getnames()
        ver_members = [n for n in names if n.endswith("client/VERSION")]
        if not ver_members:
            print("ERROR: free linux missing client/VERSION", file=sys.stderr)
            return None
        ver = tf.extractfile(ver_members[0]).read().decode().strip()  # type: ignore[union-attr]
        if ver != FREE_VERSION:
            print(f"ERROR: free linux VERSION={ver!r} want {FREE_VERSION}", file=sys.stderr)
            return None
        launch_m = [n for n in names if n.endswith("bin/privacy-restored")]
        launch = tf.extractfile(launch_m[0]).read().decode()  # type: ignore[union-attr]
        if "RPT_FREE_TIER=1" not in launch:
            print("ERROR: free launcher missing RPT_FREE_TIER=1", file=sys.stderr)
            return None
    print(f"linux free: {dest} (VERSION={FREE_VERSION}, free launcher ok)")
    return dest


def write_manifest(artifacts: dict[str, Path]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    assets = []
    for name, path in artifacts.items():
        assets.append(
            {
                "filename": path.name,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "free_tier": True,
                "version": FREE_VERSION,
            }
        )
    man = {
        "version": FREE_VERSION,
        "free_tier": True,
        "publish": False,
        "note": (
            "Local free-tier packages only. Do not upload to GH/VPS paid_assets. "
            "Locked: Iceland single-hop, no privacy-scale Settings."
        ),
        "assets": assets,
    }
    (OUT / "manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    (OUT / "DO_NOT_PUBLISH.txt").write_text(
        "Free tier 3.3.3 — local only. Not for GH release or VPS paid catalog.\n",
        encoding="utf-8",
    )
    print(f"manifest: {OUT / 'manifest.json'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apple-stage", action="store_true", help="Zip existing free Flutter Apple builds")
    ap.add_argument("--linux", action="store_true", help="Build/stage free Linux package")
    ap.add_argument("--all", action="store_true", help="Stage whatever is available")
    args = ap.parse_args()
    if not (args.apple_stage or args.linux or args.all):
        args.all = True

    artifacts: dict[str, Path] = {}
    if args.apple_stage or args.all:
        m = stage_macos()
        if m:
            artifacts["macos"] = m
        i = stage_ios()
        if i:
            artifacts["ios"] = i
    if args.linux or args.all:
        l = stage_linux()
        if l:
            artifacts["linux"] = l

    if not artifacts:
        print("No free packages staged (build Flutter with RPT_FREE_TIER first).", file=sys.stderr)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "DO_NOT_PUBLISH.txt").write_text(
            "Free tier 3.3.3 placeholder dir — packages not yet built.\n",
            encoding="utf-8",
        )
        return 0

    _assert_no_priv(OUT)
    write_manifest(artifacts)
    print("OK free 3.3.3 (not published):", list(artifacts.keys()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
