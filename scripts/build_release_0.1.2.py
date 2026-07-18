#!/usr/bin/env python3
"""Build / stage Restore Privacy client packages for release 0.1.2.

Apple packages include Packet Tunnel Team signing + App Group secrets seed.
Windows/Android are staged from 0.1.1 when not rebuilt on this host.

- Windows: reuses prior .exe installer when local Windows build is unavailable
- Android: reuses prior APK when flutter apk is not rebuilt here
- macOS: zips Flutter restore_privacy_client.app after Developer ID sign/notarize
- iOS: zips Flutter Runner.app for sideload / device install tooling

Product admission keys (client_ed25519.priv + node_elgamal.pub) are **bundled**
into Apple packages via scripts/inject_apple_secrets.py when present under
repo secrets/ or ~/.restore-privacy/secrets/ (same pattern as Android assets).
Never bundles node_elgamal.priv.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.2"
OUT = ROOT / "releases" / VERSION
WINDOWS_EXE_NAME = f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
ANDROID_APK_NAME = f"restore-privacy-client-{VERSION}-android.apk"
MACOS_ZIP_NAME = f"restore-privacy-client-{VERSION}-macos.zip"
IOS_ZIP_NAME = f"restore-privacy-client-{VERSION}-ios.zip"

# Built Flutter products (when present)
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

# Prior release used when Windows/Android cannot be rebuilt on this host
PRIOR_TAG = "0.1.1"
PRIOR_WINDOWS = f"restore-privacy-client-{PRIOR_TAG}-windows-x64-setup.exe"
PRIOR_ANDROID = f"restore-privacy-client-{PRIOR_TAG}-android.apk"
PRIOR_DOWNLOAD = (
    f"https://github.com/rgsneddon/restore-privacy/releases/download/{PRIOR_TAG}"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_version_files() -> None:
    (ROOT / "client" / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    pubspec = ROOT / "client_app" / "pubspec.yaml"
    text = pubspec.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        if line.startswith("version:"):
            lines.append(f"version: {VERSION}+1")
        else:
            lines.append(line)
    pubspec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    inst = ROOT / "client" / "windows" / "installer.py"
    if inst.is_file():
        t = inst.read_text(encoding="utf-8")
        t2 = t
        for old in ("0.1.1", "0.1.0", "0.0.9", "0.0.8"):
            t2 = t2.replace(f'VERSION = "{old}"', f'VERSION = "{VERSION}"')
            t2 = t2.replace(f"build_release_{old}.py", f"build_release_{VERSION}.py")
        if t2 != t:
            inst.write_text(t2, encoding="utf-8")


def _assert_no_priv(root: Path) -> None:
    """Never ship node private key. Client admission priv is allowed in product packages."""
    for p in root.rglob("*.priv"):
        if p.name == "node_elgamal.priv":
            raise RuntimeError(f"refusing to package node private key: {p}")
        if p.name != "client_ed25519.priv":
            raise RuntimeError(f"refusing to package unexpected secret file: {p}")


def sign_and_notarize_macos(app: Path, dest_zip: Path) -> None:
    """Developer ID sign + notarytool + staple via shipped scripts/sign_and_notarize_macos.py.

    This is what prevents Gatekeeper "Apple could not verify … free of malware"
    for the published macOS zip (must not ship ad-hoc CODE_SIGN_IDENTITY=- alone).
    """
    script = ROOT / "scripts" / "sign_and_notarize_macos.py"
    if not script.is_file():
        raise FileNotFoundError(f"missing {script}")
    cmd = [
        sys.executable,
        str(script),
        "--app",
        str(app),
        "--zip",
        str(dest_zip),
    ]
    # Allow RP_NOTARY_* / RP_CODESIGN_IDENTITY from environment
    subprocess.run(cmd, check=True)


def package_macos_zip() -> Path:
    if not MACOS_APP.is_dir():
        raise FileNotFoundError(
            f"Missing macOS app at {MACOS_APP}. Run: cd client_app && flutter build macos"
        )
    # Bundle product admission keys before signing/notarizing
    inject_product_secrets(MACOS_APP, ios=False)
    _assert_no_priv(MACOS_APP)
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / MACOS_ZIP_NAME
    # Distribution path: Developer ID + notarize + staple, then zip (not ad-hoc)
    sign_and_notarize_macos(MACOS_APP, dest)
    if not dest.is_file():
        raise RuntimeError(f"sign_and_notarize_macos did not produce {dest}")
    return dest


def sign_ios_app(app: Path) -> None:
    """Sign iOS Runner.app + nested frameworks/appex with Apple Distribution (or Development).

    Avoids a permanently ad-hoc-only iOS package when a team identity is in the keychain.
    Full device install still needs a matching provisioning profile for the team.
    """
    identity = os.environ.get(
        "RP_IOS_CODESIGN_IDENTITY",
        "Apple Distribution: Russell Sneddon (SFCBP95595)",
    )
    # Nested frameworks
    fw_dir = app / "Frameworks"
    if fw_dir.is_dir():
        for fw in sorted(fw_dir.glob("*.framework")):
            subprocess.run(
                ["codesign", "--force", "--timestamp", "--sign", identity, str(fw)],
                check=False,
            )
    # Packet Tunnel extension
    appex = app / "PlugIns" / "PacketTunnel.appex"
    if appex.is_dir():
        ent = ROOT / "client_app" / "ios" / "PacketTunnel" / "PacketTunnel.entitlements"
        cmd = ["codesign", "--force", "--timestamp", "--sign", identity]
        if ent.is_file():
            cmd.extend(["--entitlements", str(ent)])
        cmd.append(str(appex))
        r = subprocess.run(cmd, check=False)
        if r.returncode != 0:
            subprocess.run(
                ["codesign", "--force", "--timestamp", "--sign", identity, str(appex)],
                check=True,
            )
    # Host app
    subprocess.run(
        ["codesign", "--force", "--timestamp", "--sign", identity, str(app)],
        check=True,
    )


def inject_product_secrets(app: Path, *, ios: bool) -> None:
    """Bundle client_ed25519.priv + node_elgamal.pub into the app for seamless connect."""
    script = ROOT / "scripts" / "inject_apple_secrets.py"
    cmd = [sys.executable, str(script), "--app", str(app)]
    if ios:
        cmd.append("--ios")
    # Prefer non-optional so release fails closed if keys missing on packager machine
    subprocess.run(cmd, check=True)


def package_ios_zip() -> Path:
    if not IOS_APP.is_dir():
        raise FileNotFoundError(
            f"Missing iOS app at {IOS_APP}. Run: cd client_app && flutter build ios --no-codesign"
        )
    # Bundle product admission keys before signing/zipping
    inject_product_secrets(IOS_APP, ios=True)
    _assert_no_priv(IOS_APP)
    # Team-sign when identity is available (not ad-hoc-only distribution story)
    try:
        sign_ios_app(IOS_APP)
    except Exception as exc:  # noqa: BLE001 — packaging continues with best effort
        print(f"iOS codesign warning: {exc}", file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / IOS_ZIP_NAME
    if dest.exists():
        dest.unlink()
    # Zip signed Runner.app for sideload / device tooling
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in IOS_APP.rglob("*"):
            if path.is_file():
                arc = Path("Runner.app") / path.relative_to(IOS_APP)
                zf.write(path, arc.as_posix())
    return dest


def fetch_prior_asset(name: str, dest: Path) -> Path:
    """Download a prior release asset via gh (authenticated)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{PRIOR_DOWNLOAD}/{name}"
    # Prefer gh so private rate limits / auth work
    cmd = [
        "gh",
        "release",
        "download",
        PRIOR_TAG,
        "--repo",
        "rgsneddon/restore-privacy",
        "--pattern",
        name,
        "--dir",
        str(dest.parent),
        "--clobber",
    ]
    subprocess.run(cmd, check=True)
    src = dest.parent / name
    if src.resolve() != dest.resolve():
        if dest.exists():
            dest.unlink()
        src.rename(dest)
    if not dest.is_file():
        raise FileNotFoundError(f"failed to fetch {url} → {dest}")
    return dest


def stage_windows_exe() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / WINDOWS_EXE_NAME
    # Prefer local build if present
    local_candidates = [
        ROOT / "releases" / PRIOR_TAG / PRIOR_WINDOWS,
        ROOT / "dist" / VERSION / WINDOWS_EXE_NAME,
    ]
    for c in local_candidates:
        if c.is_file():
            shutil.copy2(c, dest)
            return dest
    fetch_prior_asset(PRIOR_WINDOWS, dest)
    return dest


def stage_android_apk() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / ANDROID_APK_NAME
    local_candidates = [
        ROOT / "releases" / PRIOR_TAG / PRIOR_ANDROID,
        ROOT
        / "client_app"
        / "build"
        / "app"
        / "outputs"
        / "flutter-apk"
        / "app-release.apk",
    ]
    for c in local_candidates:
        if c.is_file():
            shutil.copy2(c, dest)
            return dest
    fetch_prior_asset(PRIOR_ANDROID, dest)
    return dest


def main() -> int:
    write_version_files()
    OUT.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}

    win = stage_windows_exe()
    artifacts[WINDOWS_EXE_NAME] = sha256_file(win)
    print(f"windows: {win} ({win.stat().st_size} bytes)")

    apk = stage_android_apk()
    artifacts[ANDROID_APK_NAME] = sha256_file(apk)
    print(f"android: {apk} ({apk.stat().st_size} bytes)")

    mac = package_macos_zip()
    artifacts[MACOS_ZIP_NAME] = sha256_file(mac)
    print(f"macos:   {mac} ({mac.stat().st_size} bytes)")

    ios = package_ios_zip()
    artifacts[IOS_ZIP_NAME] = sha256_file(ios)
    print(f"ios:     {ios} ({ios.stat().st_size} bytes)")

    # Final no-secrets check on release dir
    _assert_no_priv(OUT)

    manifest = {
        "version": VERSION,
        "tag": VERSION,
        "assets": [
            {"filename": name, "sha256": dig, "bytes": (OUT / name).stat().st_size}
            for name, dig in artifacts.items()
        ],
    }
    man_path = OUT / "SHA256SUMS.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"manifest: {man_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
