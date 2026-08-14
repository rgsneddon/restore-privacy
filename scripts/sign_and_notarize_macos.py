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


DEVID_TUNNEL_SYSEX_NAME = (
    "com.restoreprivacy.restorePrivacyClient.PacketTunnel.systemextension"
)
HOST_SYSEX_USAGE = (
    "Restore Privacy needs a Network system extension to create the residual "
    "Packet Tunnel. Choose Allow if macOS asks."
)


def find_signables(app: Path) -> list[Path]:
    """Inside-out order: nested frameworks/dylibs/appex/sysex, then main executable, then .app."""
    items: list[Path] = []
    # Nested code first
    for pattern in (
        "Contents/Frameworks/**/*.framework",
        "Contents/Frameworks/**/*.dylib",
        "Contents/PlugIns/**/*.appex",
        "Contents/Library/SystemExtensions/**/*.systemextension",
        "Contents/MacOS/*",
    ):
        for p in sorted(app.glob(pattern)):
            if p.is_file() or p.suffix in {".framework", ".appex", ".systemextension"}:
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


def devid_ne_provisioning_dir() -> Path:
    """Shipped Developer ID Network Extension provisioning profiles (MAC_APP_DIRECT)."""
    return ROOT / "client_app/macos/Provisioning/DeveloperID"


def devid_ne_profiles_available() -> bool:
    """True when host + PacketTunnel Developer ID NE profiles are on disk."""
    d = devid_ne_provisioning_dir()
    host = d / "host.provisionprofile"
    tunnel = d / "PacketTunnel.provisionprofile"
    return host.is_file() and tunnel.is_file() and host.stat().st_size > 100


def host_ne_for_residual_catalog() -> bool:
    """Whether free monopin DevID host includes residual Network Extension.

    Default **on** when ``client_app/macos/Provisioning/DeveloperID/*.provisionprofile``
    exist (MAC_APP_DIRECT profiles authorizing ``packet-tunnel-provider-systemextension``).
    Without those profiles, bare ``packet-tunnel-provider`` under DevID is AMFI-killed
    (exit 137) — then default **off** so the zip still opens.

    Override: ``RPT_MACOS_HOST_NE=0`` forces no host NE; ``=1`` forces residual NE
    (requires profiles + launch_probe).
    """
    raw = os.environ.get("RPT_MACOS_HOST_NE", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    # Auto: residual-capable free monopin when DevID NE profiles are present.
    return devid_ne_profiles_available()


def entitlements_for(path: Path) -> Path | None:
    """Optional entitlements file for host app / PacketTunnel."""
    name = path.name
    if (
        name.endswith(".appex")
        or name.endswith(".systemextension")
        or name == "PacketTunnel"
    ):
        if host_ne_for_residual_catalog():
            devid_tun = (
                ROOT / "client_app/macos/PacketTunnel/PacketTunnelDeveloperID.entitlements"
            )
            if devid_tun.is_file():
                print(
                    f"tunnel entitlements: {devid_tun.name} (DevID systemextension NE)",
                    flush=True,
                )
                return devid_tun
        ent = ROOT / "client_app/macos/PacketTunnel/PacketTunnel.entitlements"
        return ent if ent.is_file() else None
    if path.suffix == ".app" or name == "restore_privacy_client":
        if host_ne_for_residual_catalog():
            residual = (
                ROOT / "client_app/macos/Runner/DeveloperIDResidual.entitlements"
            )
            if residual.is_file():
                print(
                    f"host entitlements: residual NE ({residual.name}) "
                    f"DevID systemextension + embedded MAC_APP_DIRECT profile",
                    flush=True,
                )
                return residual
        for candidate in (
            ROOT / "client_app/macos/Runner/DeveloperID.entitlements",
            ROOT / "client_app/macos/Runner/Release.entitlements",
        ):
            if candidate.is_file():
                print(f"host entitlements: {candidate.name} (no host NE)", flush=True)
                return candidate
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
        if path.suffix in {".app", ".appex", ".systemextension"} or path.name in {
            "restore_privacy_client",
            "PacketTunnel",
        }:
            cmd.extend(["--entitlements", str(ent)])
    cmd.append(str(path))
    run(cmd)


def strip_development_profiles(app: Path) -> None:
    """Remove Xcode-managed *development* provisioning profiles only.

    Developer ID distribution must not embed a device-limited *Mac Team
    Provisioning Profile* (ProvisionedDevices). That mismatch causes launchd
    spawn failure (RBSRequestErrorDomain Code=5 / POSIX 163).

    **Keep** MAC_APP_DIRECT / Developer ID Network Extension profiles (no
    ProvisionedDevices, ProvisionsAllDevices) so residual host NE launches.
    """
    import plistlib
    import subprocess as _sp

    removed = 0
    kept = 0
    for prof in app.rglob("embedded.provisionprofile"):
        try:
            raw = _sp.check_output(
                ["security", "cms", "-D", "-i", str(prof)],
                stderr=_sp.DEVNULL,
            )
            data = plistlib.loads(raw)
            name = str(data.get("Name", ""))
            has_devices = bool(data.get("ProvisionedDevices"))
            is_team_dev = "Team Provisioning Profile" in name
            # Developer ID / direct distribution profiles: keep
            if data.get("ProvisionsAllDevices") and not has_devices and not is_team_dev:
                print(f"keeping distribution profile: {prof} ({name!r})", flush=True)
                kept += 1
                continue
            if has_devices or is_team_dev:
                print(f"removing development profile: {prof} ({name!r})", flush=True)
                prof.unlink()
                removed += 1
                continue
            # Unknown but not device-limited — keep (e.g. MAC_APP_DIRECT)
            print(f"keeping profile: {prof} ({name!r})", flush=True)
            kept += 1
        except Exception as exc:
            # Unreadable: remove for safety on DevID packaging
            print(f"removing unreadable profile {prof}: {exc}", flush=True)
            try:
                prof.unlink()
                removed += 1
            except OSError:
                pass
    print(
        f"stripped {removed} development profile(s); kept {kept} distribution profile(s)",
        flush=True,
    )


def embed_devid_ne_profiles(app: Path) -> None:
    """Embed MAC_APP_DIRECT NE profiles for free monopin residual registration."""
    if not host_ne_for_residual_catalog():
        return
    if not devid_ne_profiles_available():
        print(
            "WARNING: RPT residual host NE requested but "
            f"{devid_ne_provisioning_dir()} profiles missing",
            flush=True,
        )
        return
    d = devid_ne_provisioning_dir()
    host_src = d / "host.provisionprofile"
    tun_src = d / "PacketTunnel.provisionprofile"
    host_dst = app / "Contents" / "embedded.provisionprofile"
    shutil.copy2(host_src, host_dst)
    print(f"embedded host DevID NE profile → {host_dst}", flush=True)
    tun_bundles = [
        app / "Contents" / "Library" / "SystemExtensions" / DEVID_TUNNEL_SYSEX_NAME,
        app / "Contents" / "PlugIns" / "PacketTunnel.appex",
    ]
    for tun in tun_bundles:
        if not tun.is_dir():
            continue
        tun_dst = tun / "Contents" / "embedded.provisionprofile"
        tun_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tun_src, tun_dst)
        print(f"embedded PacketTunnel DevID NE profile → {tun_dst}", flush=True)
        break


def remap_packettunnel_appex_to_systemextension(app: Path) -> Path | None:
    """TN3134: Developer ID packet tunnel must be a system extension.

    Flutter still builds PacketTunnel as PlugIns/PacketTunnel.appex so the
    residual-team copy can keep the Team ``packet-tunnel-provider`` appex.
    Catalog DevID seals ``packet-tunnel-provider-systemextension`` — NESM
    rejects that token on an appex (Plugin internal error, startTunnel never
    runs). Move the bundle to Contents/Library/SystemExtensions.
    """
    if not host_ne_for_residual_catalog():
        return None
    dest_dir = app / "Contents" / "Library" / "SystemExtensions"
    dest = dest_dir / DEVID_TUNNEL_SYSEX_NAME
    appex = app / "Contents" / "PlugIns" / "PacketTunnel.appex"
    xcode_sysex = dest_dir / "PacketTunnel.systemextension"
    if dest.is_dir() and not appex.is_dir():
        print(f"PacketTunnel already a system extension: {dest}", flush=True)
        _ensure_systemextension_info_plist(dest)
        _ensure_host_system_extension_usage(app)
        return dest
    if xcode_sysex.is_dir() and xcode_sysex.resolve() != dest.resolve():
        dest_dir.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(xcode_sysex), str(dest))
        _ensure_systemextension_info_plist(dest)
        _ensure_host_system_extension_usage(app)
        print(f"renamed Xcode PacketTunnel.systemextension → {dest}", flush=True)
        return dest
    if not appex.is_dir():
        print(
            "WARNING: PacketTunnel.appex missing; cannot remap to system extension",
            flush=True,
        )
        return dest if dest.is_dir() else None
    dest_dir.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(appex), str(dest))
    plugins = app / "Contents" / "PlugIns"
    if plugins.is_dir() and not any(plugins.iterdir()):
        plugins.rmdir()
    _ensure_systemextension_info_plist(dest)
    _ensure_host_system_extension_usage(app)
    print(f"remapped PacketTunnel.appex → {dest}", flush=True)
    return dest


def _ensure_systemextension_info_plist(sysex: Path) -> None:
    import plistlib

    info = sysex / "Contents" / "Info.plist"
    if not info.is_file():
        return
    with info.open("rb") as fh:
        data = plistlib.load(fh)
    data["CFBundlePackageType"] = "SYSX"
    data["NSSystemExtensionUsageDescription"] = HOST_SYSEX_USAGE
    # XPCService makes sysextd classify this as an XPC service, not a Network
    # system extension ("extension category returned error"). Entry is
    # NEProvider.startSystemExtensionMode in PacketTunnel/main.m.
    data.pop("XPCService", None)
    # startSystemExtensionMode + NEProviderClasses; NSExtension makes NESM
    # treat this as an appex and startTunnel never reaches the Swift provider.
    data.pop("NSExtension", None)
    ne = data.get("NetworkExtension")
    if not isinstance(ne, dict):
        ne = {}
        data["NetworkExtension"] = ne
    # 1.2.4 activated without NEMachServiceName. An application-identifier
    # Mach name (not app-group prefixed) makes the NE category validator
    # return "extension category returned error".
    if isinstance(ne, dict):
        ne.pop("NEMachServiceName", None)
    providers = ne.get("NEProviderClasses")
    if not isinstance(providers, dict):
        providers = {}
        ne["NEProviderClasses"] = providers
    providers.setdefault(
        "com.apple.networkextension.packet-tunnel",
        "PacketTunnel.PacketTunnelProvider",
    )
    with info.open("wb") as fh:
        plistlib.dump(data, fh, sort_keys=False)


def _ensure_host_system_extension_usage(app: Path) -> None:
    import plistlib

    info = app / "Contents" / "Info.plist"
    if not info.is_file():
        return
    with info.open("rb") as fh:
        data = plistlib.load(fh)
    if data.get("NSSystemExtensionUsageDescription"):
        return
    data["NSSystemExtensionUsageDescription"] = HOST_SYSEX_USAGE
    with info.open("wb") as fh:
        plistlib.dump(data, fh, sort_keys=False)
    print(f"added NSSystemExtensionUsageDescription → {info}", flush=True)


def sign_app(app: Path, identity: str) -> None:
    if not app.is_dir():
        raise FileNotFoundError(f"app not found: {app}")
    strip_development_profiles(app)
    remap_packettunnel_appex_to_systemextension(app)
    embed_devid_ne_profiles(app)
    # Sign deepest nested first
    nested: list[Path] = []
    for root, dirs, files in os.walk(app / "Contents"):
        for d in dirs:
            p = Path(root) / d
            if p.suffix in {".framework", ".appex", ".systemextension"}:
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
    # Explicitly sign each .framework, leftover .appex, and .systemextension
    for p in sorted(app.glob("Contents/Frameworks/*.framework"), reverse=True):
        sign_path(p, identity)
    for p in sorted(app.glob("Contents/PlugIns/*.appex"), reverse=True):
        sign_path(p, identity)
    for p in sorted(
        app.glob("Contents/Library/SystemExtensions/*.systemextension"), reverse=True
    ):
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


def launch_probe_alive(app: Path, *, settle_s: float = 2.5) -> dict:
    """Prove the sealed app launches and stays alive (not AMFI SIGKILL 137).

    Host packet-tunnel-provider under DevID without a matching NE profile is
    known to die immediately with exit 137 — spctl can still say Accepted.
    """
    import time

    main_bin = app / "Contents" / "MacOS" / "restore_privacy_client"
    if not main_bin.is_file():
        return {"ok": False, "error": f"missing main binary {main_bin}", "rc": None}
    # Launch detached; do not use open(1) alone — capture process exit.
    proc = subprocess.Popen(
        [str(main_bin)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    time.sleep(settle_s)
    rc = proc.poll()
    if rc is None:
        # Still running — healthy launch for residual UI path.
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return {"ok": True, "rc": None, "alive": True, "error": None}
    # Process already exited — AMFI often reports 137.
    return {
        "ok": False,
        "rc": rc,
        "alive": False,
        "error": f"app exited immediately rc={rc} (137=AMFI SIGKILL often host NE)",
    }


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
    # Bundle product admission keys into Resources/secrets before signing
    # (seamless connect; mirrors Android assets inject). Never node_elgamal.priv.
    inject = ROOT / "scripts" / "inject_apple_secrets.py"
    if inject.is_file():
        print(f"Injecting product secrets into {app}…", flush=True)
        # Prefer real inject; fall back to optional so sign still works for CI without keys
        r = subprocess.run(
            [sys.executable, str(inject), "--app", str(app)],
            check=False,
        )
        if r.returncode != 0:
            print(
                "WARNING: product secrets not injected — connect will fail until keys are present.",
                flush=True,
            )
            run([sys.executable, str(inject), "--app", str(app), "--optional"], check=False)
    print(f"Signing {app} with {identity}", flush=True)
    sign_app(app, identity)

    cs = run_capture(["codesign", "-dv", "--verbose=2", str(app)])
    print(cs)
    if "Signature=adhoc" in cs or "Signature=adhoc" in cs.replace(" ", ""):
        print("ERROR: still ad-hoc after sign", file=sys.stderr)
        return 2
    # Fail closed: catalog distribution must be Developer ID, not Apple Development
    # (Development-signed apps trigger Gatekeeper "Apple could not verify… / Not Opened").
    if "Developer ID Application" not in cs:
        print(
            "ERROR: signature is not Developer ID Application after sign. "
            f"Got codesign -dv:\n{cs}\n"
            "Set RP_CODESIGN_IDENTITY to a Developer ID Application identity "
            "(not Apple Development / Apple Distribution).",
            file=sys.stderr,
        )
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
    if not args.skip_notarize and "accepted" not in sp.lower() and "source=Notarized Developer ID" not in sp:
        # spctl may still print "accepted\nsource=Notarized Developer ID" on success
        if "source=Notarized Developer ID" not in sp and "Notarized Developer ID" not in sp:
            print(
                "WARNING: spctl did not report Notarized Developer ID — "
                "Gatekeeper may still block downloads.",
                file=sys.stderr,
            )

    # Fail closed: spctl "accepted" is not enough — host NE without matching
    # DevID NE profile yields AMFI SIGKILL (rc=137) and Settings/VPN never open.
    probe = launch_probe_alive(app)
    print(f"launch_probe={probe}", flush=True)
    if not probe.get("ok"):
        print(
            f"ERROR: sealed app failed launch probe: {probe.get('error')}\n"
            "Free monopin must launch. With residual host NE, require matching "
            "MAC_APP_DIRECT profiles under client_app/macos/Provisioning/DeveloperID/ "
            "and DeveloperIDResidual systemextension entitlements. "
            "Fallback: RPT_MACOS_HOST_NE=0 (openable, no System VPN registration).",
            file=sys.stderr,
        )
        return 4

    if args.zip:
        package_zip(app, args.zip.resolve())
        print(f"Wrote {args.zip}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
