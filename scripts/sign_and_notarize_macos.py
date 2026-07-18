#!/usr/bin/env python3
"""Sign (Developer ID), notarize, and staple the Restore Privacy macOS app.

This is the **distribution** path that avoids Gatekeeper's
"Apple could not verify … free of malware" rejection for downloaded apps.

Usage:
  python3 scripts/sign_and_notarize_macos.py \\
      [--app path/to/restore_privacy_client.app] \\
      [--zip path/to/out.zip] \\
      [--skip-notarize]

Environment (notarization):
  RP_NOTARY_KEY      path to AuthKey_XXXX.p8  (or default perccent-codesign key)
  RP_NOTARY_KEY_ID   key id (default from key-id.txt / filename)
  RP_NOTARY_ISSUER   issuer UUID
  RP_CODESIGN_IDENTITY  override identity string

Requires: Developer ID Application identity in keychain; network for notarytool.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP = (
    ROOT
    / "client_app"
    / "build"
    / "macos"
    / "Build"
    / "Products"
    / "Release"
    / "restore_privacy_client.app"
)
DEFAULT_IDENTITY = "Developer ID Application: Russell Sneddon (SFCBP95595)"
TEAM_ID = "SFCBP95595"

# Default notary key location used on this developer machine (optional).
DEFAULT_KEY_DIR = Path.home() / "Library/Developer/perccent-codesign"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check, text=True, capture_output=False)


def run_capture(cmd: list[str]) -> str:
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return (p.stdout or "") + (p.stderr or "")


def codesign_identity() -> str:
    return os.environ.get("RP_CODESIGN_IDENTITY", DEFAULT_IDENTITY)


def find_signables(app: Path) -> list[Path]:
    """Inside-out order: nested frameworks/dylibs/appex, then main executable, then .app."""
    items: list[Path] = []
    # Nested code first
    for pattern in (
        "Contents/Frameworks/**/*.framework",
        "Contents/Frameworks/**/*.dylib",
        "Contents/PlugIns/**/*.appex",
        "Contents/MacOS/*",
    ):
        for p in sorted(app.glob(pattern)):
            if p.is_file() or p.suffix in {".framework", ".appex"}:
                if p not in items:
                    items.append(p)
    # Whole app last
    items.append(app)
    # De-dupe while preserving order
    seen: set[Path] = set()
    out: list[Path] = []
    for p in items:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out


def entitlements_for(path: Path) -> Path | None:
    """Optional entitlements file for host app / PacketTunnel."""
    name = path.name
    if name.endswith(".appex") or name == "PacketTunnel":
        ent = ROOT / "client_app/macos/PacketTunnel/PacketTunnel.entitlements"
        return ent if ent.is_file() else None
    if path.suffix == ".app" or name == "restore_privacy_client":
        # Host: use Release entitlements (sandbox + network). NE keys stay on appex.
        ent = ROOT / "client_app/macos/Runner/Release.entitlements"
        return ent if ent.is_file() else None
    return None


def sign_path(path: Path, identity: str) -> None:
    cmd = [
        "codesign",
        "--force",
        "--timestamp",
        "--options",
        "runtime",
        "--sign",
        identity,
    ]
    ent = entitlements_for(path)
    if ent is not None:
        # For frameworks, don't force host entitlements
        if path.suffix in {".app", ".appex"} or path.name in {
            "restore_privacy_client",
            "PacketTunnel",
        }:
            cmd.extend(["--entitlements", str(ent)])
    cmd.append(str(path))
    run(cmd)


def sign_app(app: Path, identity: str) -> None:
    if not app.is_dir():
        raise FileNotFoundError(f"app not found: {app}")
    # Sign deepest nested first
    nested: list[Path] = []
    for root, dirs, files in os.walk(app / "Contents"):
        for d in dirs:
            p = Path(root) / d
            if p.suffix in {".framework", ".appex"}:
                nested.append(p)
        for f in files:
            p = Path(root) / f
            if p.suffix in {".dylib", ".so"} or (
                os.access(p, os.X_OK) and "MacOS" in p.parts
            ):
                nested.append(p)
    # Sort by path depth descending (inside-out)
    nested.sort(key=lambda p: len(p.parts), reverse=True)
    seen: set[str] = set()
    for p in nested:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        # Skip signing raw files inside .framework that aren't the binary — codesign framework bundle
        if ".framework/" in str(p) and p.suffix != ".framework":
            # Prefer signing the framework bundle once
            continue
        try:
            sign_path(p, identity)
        except subprocess.CalledProcessError:
            # Retry without entitlements for pure binaries
            run(
                [
                    "codesign",
                    "--force",
                    "--timestamp",
                    "--options",
                    "runtime",
                    "--sign",
                    identity,
                    str(p),
                ]
            )
    # Explicitly sign each .framework and .appex
    for p in sorted(app.glob("Contents/Frameworks/*.framework"), reverse=True):
        sign_path(p, identity)
    for p in sorted(app.glob("Contents/PlugIns/*.appex"), reverse=True):
        sign_path(p, identity)
    # Main binary then app bundle
    main_bin = app / "Contents/MacOS/restore_privacy_client"
    if main_bin.is_file():
        sign_path(main_bin, identity)
    sign_path(app, identity)
    # Verify
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)])


def resolve_notary_args() -> list[str]:
    key = os.environ.get("RP_NOTARY_KEY")
    key_id = os.environ.get("RP_NOTARY_KEY_ID")
    issuer = os.environ.get("RP_NOTARY_ISSUER")
    if not key and (DEFAULT_KEY_DIR / "key-id.txt").is_file():
        for line in (DEFAULT_KEY_DIR / "key-id.txt").read_text().splitlines():
            if line.startswith("KEY_ID="):
                key_id = key_id or line.split("=", 1)[1].strip()
            if line.startswith("P8="):
                key = key or line.split("=", 1)[1].strip()
        if not key:
            # AuthKey_*.p8 in dir
            keys = list(DEFAULT_KEY_DIR.glob("AuthKey_*.p8"))
            if keys:
                key = str(keys[0])
                if not key_id:
                    key_id = keys[0].stem.replace("AuthKey_", "")
    if not issuer and (DEFAULT_KEY_DIR / "issuer-id.txt").is_file():
        issuer = (DEFAULT_KEY_DIR / "issuer-id.txt").read_text().strip()
    if not (key and key_id and issuer):
        raise RuntimeError(
            "Must provide credentials: set RP_NOTARY_KEY, RP_NOTARY_KEY_ID, RP_NOTARY_ISSUER "
            "or install AuthKey + issuer-id under ~/Library/Developer/perccent-codesign/"
        )
    return ["--key", key, "--key-id", key_id, "--issuer", issuer]


def notarize_and_staple(app: Path, skip_notarize: bool = False) -> None:
    if skip_notarize:
        print("skip notarize (flag)", flush=True)
        return
    creds = resolve_notary_args()
    with tempfile.TemporaryDirectory() as td:
        zip_path = Path(td) / "restore_privacy_client-for-notary.zip"
        # ditto zip preserves macOS metadata for notary
        run(
            [
                "ditto",
                "-c",
                "-k",
                "--keepParent",
                str(app),
                str(zip_path),
            ]
        )
        run(
            [
                "xcrun",
                "notarytool",
                "submit",
                str(zip_path),
                *creds,
                "--wait",
            ]
        )
    run(["xcrun", "stapler", "staple", str(app)])
    run(["xcrun", "stapler", "validate", str(app)])


def assess(app: Path) -> str:
    try:
        return run_capture(["spctl", "--assess", "--type", "execute", "-vv", str(app)])
    except subprocess.CalledProcessError as e:
        return (e.stdout or "") + (e.stderr or "") + f"\nexit={e.returncode}"


def package_zip(app: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    run(
        [
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(app),
            str(dest),
        ]
    )
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app", type=Path, default=DEFAULT_APP)
    ap.add_argument(
        "--zip",
        type=Path,
        default=None,
        help="Output zip path (default: releases/<ver>/restore-privacy-client-*-macos.zip)",
    )
    ap.add_argument("--skip-notarize", action="store_true")
    ap.add_argument("--identity", default=None)
    args = ap.parse_args(argv)

    identity = args.identity or codesign_identity()
    app = args.app.resolve()
    print(f"Signing {app} with {identity}", flush=True)
    sign_app(app, identity)

    cs = run_capture(["codesign", "-dv", "--verbose=2", str(app)])
    print(cs)
    if "Developer ID Application" not in cs and "Signature=adhoc" in cs:
        print("ERROR: still ad-hoc after sign", file=sys.stderr)
        return 2

    try:
        notarize_and_staple(app, skip_notarize=args.skip_notarize)
    except RuntimeError as e:
        print(f"NOTARY_CREDENTIALS: {e}", file=sys.stderr)
        if not args.skip_notarize:
            # Still leave Developer-ID-signed app; packaging may proceed
            print("Continuing with Developer ID signature only (no staple).", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"NOTARY_FAILED: {e}", file=sys.stderr)
        return e.returncode or 3

    sp = assess(app)
    print(sp)

    if args.zip:
        package_zip(app, args.zip.resolve())
        print(f"Wrote {args.zip}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
