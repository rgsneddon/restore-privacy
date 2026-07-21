#!/usr/bin/env python3
"""Sign restore_privacy_client.app for residual Packet Tunnel on this Mac.

Developer ID distribution (public zip) omits host Network Extension so AMFI does
not SIGKILL the host. Residual public IP **requires** host + appex NE
entitlements authorized by a Mac Team Provisioning Profile.

This script:
  - Embeds Mac Team profiles for host and PacketTunnel.appex
  - Signs host with TeamResidual.entitlements (packet-tunnel-provider + Flutter CS)
  - Signs appex with PacketTunnel.entitlements
  - Uses Apple Development identity (device-limited residual path)

Usage:
  python3 scripts/sign_macos_residual_team.py \\
      --app path/to/restore_privacy_client.app

Then open the app and Connect; approve VPN configuration if macOS prompts.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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
HOST_BUNDLE = "com.restoreprivacy.restorePrivacyClient"
APPEX_BUNDLE = "com.restoreprivacy.restorePrivacyClient.PacketTunnel"
DEFAULT_IDENTITY = "Apple Development: Russell Sneddon (U37S5938B4)"
TEAM_RESIDUAL_ENT = ROOT / "client_app/macos/Runner/TeamResidual.entitlements"
APPEX_ENT = ROOT / "client_app/macos/PacketTunnel/PacketTunnel.entitlements"
PROFILE_DIR = (
    Path.home() / "Library/Developer/Xcode/UserData/Provisioning Profiles"
)


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def find_profile(bundle_id: str) -> Path | None:
    import plistlib

    if not PROFILE_DIR.is_dir():
        return None
    for p in PROFILE_DIR.glob("*.provisionprofile"):
        try:
            raw = subprocess.check_output(
                ["security", "cms", "-D", "-i", str(p)], stderr=subprocess.DEVNULL
            )
            data = plistlib.loads(raw)
            ents = data.get("Entitlements") or {}
            app_id = str(ents.get("com.apple.application-identifier", ""))
            if app_id.endswith(bundle_id) or app_id == f"SFCBP95595.{bundle_id}":
                # Prefer profiles that include networkextension
                ne = ents.get("com.apple.developer.networking.networkextension")
                if ne:
                    return p
        except Exception:
            continue
    return None


def embed_profile(bundle: Path, profile: Path) -> None:
    dest = bundle / "Contents" / "embedded.provisionprofile"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(profile, dest)
    print(f"embedded {profile.name} → {dest}", flush=True)


def sign_path(path: Path, identity: str, entitlements: Path | None) -> None:
    # Hardened Runtime is required for Flutter JIT CS entitlement; profile
    # authorizes host NE. Do not claim disable-library-validation or
    # allow-unsigned-executable-memory alongside NE (AMFI SIGKILL).
    cmd = [
        "codesign",
        "--force",
        "--timestamp",
        "--options",
        "runtime",
        "--sign",
        identity,
    ]
    if entitlements is not None and entitlements.is_file():
        cmd.extend(["--entitlements", str(entitlements)])
    cmd.append(str(path))
    run(cmd)


def sign_app(app: Path, identity: str) -> None:
    if not app.is_dir():
        raise FileNotFoundError(app)
    host_prof = find_profile(HOST_BUNDLE)
    appex_prof = find_profile(APPEX_BUNDLE)
    if host_prof is None or appex_prof is None:
        raise RuntimeError(
            "Missing Mac Team Provisioning Profiles with Network Extension for "
            f"{HOST_BUNDLE} and/or {APPEX_BUNDLE}. Open the macos Xcode project once "
            "with Automatic Signing (Team SFCBP95595) to download them."
        )
    if not TEAM_RESIDUAL_ENT.is_file():
        raise FileNotFoundError(TEAM_RESIDUAL_ENT)

    # Frameworks first
    for fw in sorted(app.glob("Contents/Frameworks/*.framework")):
        sign_path(fw, identity, None)

    # Appex with NE + profile
    for appex in sorted(app.glob("Contents/PlugIns/*.appex")):
        embed_profile(appex, appex_prof)
        main = appex / "Contents" / "MacOS" / "PacketTunnel"
        if main.is_file():
            sign_path(main, identity, APPEX_ENT if APPEX_ENT.is_file() else None)
        sign_path(appex, identity, APPEX_ENT if APPEX_ENT.is_file() else None)

    # Host with NE + profile
    embed_profile(app, host_prof)
    main_bin = app / "Contents" / "MacOS" / "restore_privacy_client"
    if main_bin.is_file():
        sign_path(main_bin, identity, TEAM_RESIDUAL_ENT)
    sign_path(app, identity, TEAM_RESIDUAL_ENT)

    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)])
    print("--- host entitlements ---", flush=True)
    subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(app)], check=False
    )
    print("--- appex entitlements ---", flush=True)
    for appex in app.glob("Contents/PlugIns/*.appex"):
        subprocess.run(
            ["codesign", "-d", "--entitlements", ":-", str(appex)], check=False
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app", type=Path, default=DEFAULT_APP)
    ap.add_argument(
        "--identity",
        default=os.environ.get("RP_TEAM_CODESIGN_IDENTITY", DEFAULT_IDENTITY),
    )
    args = ap.parse_args(argv)
    app = args.app.resolve()
    print(f"Team residual sign {app} with {args.identity}", flush=True)
    try:
        sign_app(app, args.identity)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(
        "OK — open the app, Connect, and approve VPN if prompted. "
        "Residual public IP only changes when Packet Tunnel status is connected.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
