#!/usr/bin/env python3
"""Inject public node material into a macOS/iOS app bundle.

Copies **public** ElGamal keys only:
  - ``node_elgamal.pub`` (Iceland entry)
  - ``exit_node_elgamal.pub`` (Romania exit, multi-hop residual)

Never copies a shared ``client_ed25519.priv`` or ``node_elgamal.priv``.
Per-device Ed25519 keys are generated on first run by the client.

Source search (first hit wins for each pub):
  RPT_SECRETS_DIR env, <repo>/product/, <repo>/secrets/, ~/.restore-privacy/secrets/

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
EXIT_PUB = "exit_node_elgamal.pub"
PUBLIC_PUBS = (NODE_PUB, EXIT_PUB)
FORBIDDEN = "node_elgamal.priv"


def candidate_sources() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get("RPT_SECRETS_DIR", "").strip()
    if env:
        out.append(Path(env))
    # Tracked product keys first (entry + exit); then operator secrets/
    out.append(ROOT / "product")
    out.append(ROOT / "secrets")
    out.append(Path.home() / ".restore-privacy" / "secrets")
    return out


def resolve_pub(name: str, explicit: Path | None) -> Path | None:
    """Return path to a public key file, or None if not found."""
    if explicit and (explicit / name).is_file():
        return explicit / name
    for d in candidate_sources():
        p = d / name
        if p.is_file() and p.stat().st_size >= 32:
            return p
    return None


def resolve_source(explicit: Path | None) -> Path:
    """Directory that contains at least entry node_elgamal.pub (compat)."""
    entry = resolve_pub(NODE_PUB, explicit)
    if entry is None:
        searched = ", ".join(str(d) for d in candidate_sources())
        raise FileNotFoundError(
            f"No node public key found (need {NODE_PUB}). Checked: {searched}"
        )
    return entry.parent


def inject(app: Path, source: Path, ios: bool) -> Path:
    if not app.is_dir():
        raise FileNotFoundError(f"app not found: {app}")
    if ios:
        dest = app / "secrets"
    else:
        dest = app / "Contents" / "Resources" / "secrets"
    dest.mkdir(parents=True, exist_ok=True)
    # Entry + exit public keys (never private keys)
    for name in PUBLIC_PUBS:
        src = resolve_pub(name, source if source.is_dir() else source.parent)
        if src is None and name == NODE_PUB:
            # required
            src = source / NODE_PUB if (source / NODE_PUB).is_file() else None
        if src is None:
            if name == NODE_PUB:
                raise FileNotFoundError(f"missing required {NODE_PUB}")
            print(f"skip optional {name} (not found)")
            continue
        dst = dest / name
        shutil.copy2(src, dst)
        print(f"injected {name} -> {dst} ({dst.stat().st_size} bytes)")
    # Never leave private keys in the bundle
    for leftover in list(dest.glob("*.priv")):
        leftover.unlink()
        print(f"removed priv from package: {leftover.name}")
    forbidden = dest / FORBIDDEN
    if forbidden.is_file():
        forbidden.unlink()
        print(f"removed accidental {FORBIDDEN}")
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
