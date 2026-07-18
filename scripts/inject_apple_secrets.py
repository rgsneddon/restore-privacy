#!/usr/bin/env python3
"""Inject admission secrets into a macOS/iOS app bundle (Android assets pattern).

Copies **only** client_ed25519.priv + node_elgamal.pub from a source directory
into ``Contents/Resources/secrets/`` (macOS) or ``Runner.app/secrets/`` (iOS).
Never copies ``node_elgamal.priv``.

Source search (first hit wins):
  RPT_SECRETS_DIR env, <repo>/secrets/, ~/.restore-privacy/secrets/

Usage:
  python3 scripts/inject_apple_secrets.py --app path/to/restore_privacy_client.app
  python3 scripts/inject_apple_secrets.py --app path/to/Runner.app --ios
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT_PRIV = "client_ed25519.priv"
NODE_PUB = "node_elgamal.pub"
FORBIDDEN = "node_elgamal.priv"


def candidate_sources() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get("RPT_SECRETS_DIR", "").strip()
    if env:
        out.append(Path(env))
    out.append(ROOT / "secrets")
    out.append(Path.home() / ".restore-privacy" / "secrets")
    return out


def resolve_source(explicit: Path | None) -> Path:
    if explicit:
        if not (explicit / CLIENT_PRIV).is_file() or not (explicit / NODE_PUB).is_file():
            raise FileNotFoundError(
                f"incomplete secrets dir {explicit} (need {CLIENT_PRIV} + {NODE_PUB})"
            )
        return explicit
    for d in candidate_sources():
        if (d / CLIENT_PRIV).is_file() and (d / NODE_PUB).is_file():
            return d
    searched = ", ".join(str(d) for d in candidate_sources())
    raise FileNotFoundError(
        f"No admission secrets found (need {CLIENT_PRIV} and {NODE_PUB}). "
        f"Checked: {searched}"
    )


def inject(app: Path, source: Path, ios: bool) -> Path:
    if not app.is_dir():
        raise FileNotFoundError(f"app not found: {app}")
    if ios:
        dest = app / "secrets"
    else:
        dest = app / "Contents" / "Resources" / "secrets"
    dest.mkdir(parents=True, exist_ok=True)
    for name in (CLIENT_PRIV, NODE_PUB):
        src = source / name
        dst = dest / name
        shutil.copy2(src, dst)
        print(f"injected {name} -> {dst} ({dst.stat().st_size} bytes)")
    # Ensure we never leave node private key in the bundle
    forbidden = dest / FORBIDDEN
    if forbidden.is_file():
        forbidden.unlink()
        print(f"removed accidental {FORBIDDEN}")
    # Also remove from source-adjacent if someone copied whole secrets tree
    for leftover in dest.glob("*.priv"):
        if leftover.name != CLIENT_PRIV:
            leftover.unlink()
            print(f"removed non-client priv: {leftover.name}")
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=None)
    ap.add_argument("--ios", action="store_true", help="iOS Runner.app layout")
    ap.add_argument(
        "--optional",
        action="store_true",
        help="exit 0 if secrets missing (skip inject)",
    )
    args = ap.parse_args(argv)
    try:
        src = resolve_source(args.source)
    except FileNotFoundError as e:
        if args.optional:
            print(f"skip inject (optional): {e}")
            return 0
        print(e, file=sys.stderr)
        return 1
    inject(args.app.resolve(), src, ios=args.ios)
    return 0


if __name__ == "__main__":
    sys.exit(main())
