#!/usr/bin/env python3
"""Fail-closed gates for Apple monopin ships (Team residual NE + catalog seal).

Product residual monopin path (do not conflate with openable DevID):
  (A) **Catalog residual monopin zip** — Team residual NE re-sign of a **copy**
      of the Flutter-built app (host + appex with NE profiles, host
      packet-tunnel-provider). This is the monopin basename shipped to Helsinki
      so residual Connect / VPN config registration works and launch stays alive.
  (B) **Optional openable DevID zip** — Developer ID + notarize with host NE
      **omitted** (AMFI kills DevID+host-NE without a matching DevID NE profile).
      Not the residual monopin; opt-in via RPT_MACOS_ALSO_DEVID=1.

Never ship DevID + host packet-tunnel-provider without a DevID NE profile
(AMFI SIGKILL 137 → Settings/VPN unreachable).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MACOS_APP = (
    ROOT
    / "client_app"
    / "build"
    / "macos"
    / "Build"
    / "Products"
    / "Release"
    / "restore_privacy_client.app"
)
RESIDUAL_TEAM_SCRIPT = ROOT / "scripts" / "sign_macos_residual_team.py"
NOTARIZE_SCRIPT = ROOT / "scripts" / "sign_and_notarize_macos.py"
HOST_PAID_SCRIPT = ROOT / "scripts" / "host_paid_assets_vps.py"


def residual_team_skip_allowed() -> bool:
    """Explicit opt-out only (operator CI without Mac Team profiles)."""
    return os.environ.get("RPT_SKIP_RESIDUAL_TEAM", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def residual_team_app_path(app: Path | None = None) -> Path:
    """Sibling residual-Team copy: restore_privacy_client.residual-team.app."""
    a = (app or DEFAULT_MACOS_APP).resolve()
    # .app is a directory; parent / stem.residual-team.app
    name = a.name  # restore_privacy_client.app
    if name.endswith(".app"):
        base = name[: -len(".app")]
    else:
        base = name
    return a.parent / f"{base}.residual-team.app"


def copy_app_for_residual_team(app: Path | None = None) -> Path:
    """Clone the Flutter Release app for Team residual NE re-sign (does not touch public zip input)."""
    src = (app or DEFAULT_MACOS_APP).resolve()
    if not src.is_dir():
        raise FileNotFoundError(
            f"macOS app missing at {src} — run: cd client_app && flutter build macos --release"
        )
    dest = residual_team_app_path(src)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, symlinks=True)
    return dest


def run_residual_team_resign(
    app: Path | None = None,
    *,
    require: bool | None = None,
) -> dict:
    """Run Team residual NE re-sign on a **copy** of *app*.

    Returns a result dict: ok, path, skipped, error.
    When *require* is True (default unless RPT_SKIP_RESIDUAL_TEAM), missing
    profiles/identity raise RuntimeError (fail-closed).
    """
    if require is None:
        require = not residual_team_skip_allowed()
    if residual_team_skip_allowed() and require is not False:
        # Explicit skip: only when env opt-out
        return {
            "ok": True,
            "skipped": True,
            "path": None,
            "error": None,
            "reason": "RPT_SKIP_RESIDUAL_TEAM set — residual Team NE re-sign skipped",
        }
    if not RESIDUAL_TEAM_SCRIPT.is_file():
        msg = f"missing residual Team re-sign script: {RESIDUAL_TEAM_SCRIPT}"
        if require:
            raise RuntimeError(msg)
        return {"ok": False, "skipped": True, "path": None, "error": msg}

    dest = copy_app_for_residual_team(app)
    cmd = [sys.executable, str(RESIDUAL_TEAM_SCRIPT), "--app", str(dest)]
    print(f"[apple-ship] Team residual NE re-sign: {' '.join(cmd)}", flush=True)
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        err = out.strip() or f"sign_macos_residual_team exit {p.returncode}"
        if require:
            raise RuntimeError(
                "Team residual NE re-sign failed (required for residual Connect on this Mac). "
                f"{err}\n"
                "Fix: open client_app/macos in Xcode with Automatic Signing (Team SFCBP95595) "
                "to download Mac Team Provisioning Profiles with Network Extension, then re-run. "
                "Opt-out only for non-residual CI: RPT_SKIP_RESIDUAL_TEAM=1"
            )
        return {"ok": False, "skipped": False, "path": str(dest), "error": err}
    print(out, flush=True)
    return {
        "ok": True,
        "skipped": False,
        "path": str(dest),
        "error": None,
        "stdout_tail": out[-800:],
    }


def assert_ship_scripts_present() -> list[str]:
    """Structural: ship scripts exist (unit-testable without running codesign)."""
    missing: list[str] = []
    for p in (RESIDUAL_TEAM_SCRIPT, NOTARIZE_SCRIPT, HOST_PAID_SCRIPT):
        if not p.is_file():
            missing.append(str(p.relative_to(ROOT)))
    return missing


def ship_path_invokes_residual_team(build_release_src: str) -> bool:
    """True when a build_release_*.py body wires residual Team re-sign."""
    return (
        "run_residual_team_resign" in build_release_src
        or "sign_macos_residual_team" in build_release_src
        or "apple_ship_gates" in build_release_src
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--residual-team-only",
        action="store_true",
        help="Copy Flutter Release app and Team residual NE re-sign (fail-closed)",
    )
    ap.add_argument("--app", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.residual_team_only:
        try:
            r = run_residual_team_resign(args.app, require=True)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print(f"OK residual_team path={r.get('path')} skipped={r.get('skipped')}")
        return 0
    miss = assert_ship_scripts_present()
    if miss:
        print("ERROR missing scripts:", ", ".join(miss), file=sys.stderr)
        return 1
    print("OK apple ship scripts present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
