#!/usr/bin/env python3
"""Install a git pre-commit hook that assures current per-device packages.

Every local commit runs ``python scripts/assure_current_packages.py --check``
so the catalog pin, client/VERSION, and five platform installer names stay
aligned — buyers always pay for the **current** device package identity.

Usage (from repo root)::

  python scripts/install_commit_package_task.py
  python scripts/install_commit_package_task.py --force   # overwrite existing hook

Git does not ship hooks from the remote — run this once per clone.
"""

from __future__ import annotations

import argparse
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HOOK_MARKER = "assure_current_packages.py"
HOOK_BODY = """#!/bin/sh
# restore-privacy: assure current per-device paid packages on every commit
# Installed by: python scripts/install_commit_package_task.py
# Marker: assure_current_packages.py
set -e
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$ROOT" ]; then
  exit 0
fi
cd "$ROOT" || exit 1
# Prefer python3, fall back to python (Windows git-bash / py launcher)
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "pre-commit: python not found; cannot assure current packages" >&2
  exit 1
fi
exec "$PY" scripts/assure_current_packages.py --check
"""


def hooks_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or ROOT
    # Honour core.hooksPath if set to a relative path inside the repo
    try:
        import subprocess

        r = subprocess.run(
            ["git", "-C", str(root), "config", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0 and (r.stdout or "").strip():
            hp = Path((r.stdout or "").strip())
            if not hp.is_absolute():
                hp = root / hp
            return hp
    except (OSError, subprocess.SubprocessError):
        pass
    return root / ".git" / "hooks"


def install_pre_commit(
    *,
    repo_root: Path | None = None,
    force: bool = False,
) -> Path:
    """Write ``pre-commit`` hook that runs the package currency check. Returns path."""
    root = repo_root or ROOT
    hdir = hooks_dir(root)
    if not hdir.parent.is_dir() and hdir.name == "hooks":
        # .git missing (not a clone) — still allow writing for tests into a temp tree
        hdir.mkdir(parents=True, exist_ok=True)
    else:
        hdir.mkdir(parents=True, exist_ok=True)
    hook_path = hdir / "pre-commit"
    if hook_path.is_file() and not force:
        existing = hook_path.read_text(encoding="utf-8", errors="replace")
        if HOOK_MARKER in existing:
            # already our hook
            _chmod_exec(hook_path)
            return hook_path
        raise FileExistsError(
            f"{hook_path} already exists and is not the package-assure hook; "
            f"re-run with --force to replace"
        )
    hook_path.write_text(HOOK_BODY, encoding="utf-8", newline="\n")
    _chmod_exec(hook_path)
    return hook_path


def _chmod_exec(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        # Windows may not use Unix exec bits the same way; git still runs the hook
        pass


def hook_invokes_assure(hook_path: Path) -> bool:
    if not hook_path.is_file():
        return False
    text = hook_path.read_text(encoding="utf-8", errors="replace")
    return HOOK_MARKER in text and "--check" in text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Install pre-commit task: assure current per-device packages"
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing pre-commit hook",
    )
    ap.add_argument(
        "--print-only",
        action="store_true",
        help="Print hook body and target path without writing",
    )
    args = ap.parse_args(argv)
    target = hooks_dir() / "pre-commit"
    if args.print_only:
        print(f"target={target}")
        print(HOOK_BODY)
        return 0
    try:
        path = install_pre_commit(force=args.force)
    except FileExistsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"installed {path}")
    if hook_invokes_assure(path):
        print("hook invokes: python scripts/assure_current_packages.py --check")
    print("Every commit will fail if catalog / client VERSION / device packages drift.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
