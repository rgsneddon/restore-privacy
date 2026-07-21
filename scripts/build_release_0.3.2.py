#!/usr/bin/env python3
"""Build / stage Restore Privacy client packages for release 0.3.2.

**0.3.2** fixes Apple public packages (macOS Developer ID + notarized; iOS
Team-signed sideload). Windows / Android / Linux are carry-forward renames
from the prior catalog pin (**0.3.1**) unless rebuilt on this host.

- macOS: Flutter restore_privacy_client.app → inject pub-only → DevID sign/notarize → zip
- iOS: Flutter Runner.app → inject pub-only → Distribution team-sign → zip
- Windows / Android / Linux: prefer local 0.3.0 assets renamed to 0.3.2 filenames

Never bundles node_elgamal.priv or shared client_ed25519.priv.
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
VERSION = "0.3.2"
OUT = ROOT / "releases" / VERSION
WINDOWS_EXE_NAME = f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
ANDROID_APK_NAME = f"restore-privacy-client-{VERSION}-android.apk"
MACOS_ZIP_NAME = f"restore-privacy-client-{VERSION}-macos.zip"
IOS_ZIP_NAME = f"restore-privacy-client-{VERSION}-ios.zip"
LINUX_TGZ_NAME = f"restore-privacy-client-{VERSION}-linux-x64.tar.gz"

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

# Carry-forward non-Apple platforms from last full catalog pin
PRIOR_TAG = "0.3.1"
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
        for old in (
            "0.3.0",
            "0.2.9",
            "0.2.8",
            "0.2.7",
            "0.2.6",
            "0.2.5",
            "0.2.4",
            "0.2.3",
            "0.2.2",
            "0.2.1",
            "0.2.0",
            "0.1.9",
            "0.1.8",
            "0.1.7",
            "0.1.6",
            "0.1.5",
            "0.1.4",
            "0.1.3",
            "0.1.2",
            "0.1.1",
            "0.1.0",
            "0.0.9",
        ):
            t2 = t2.replace(f'VERSION = "{old}"', f'VERSION = "{VERSION}"')
            t2 = t2.replace(f"build_release_{old}.py", f"build_release_{VERSION}.py")
        if t2 != t:
            inst.write_text(t2, encoding="utf-8")


def _assert_no_priv(root: Path) -> None:
    for p in root.rglob("*.priv"):
        raise RuntimeError(f"refusing to package private key material: {p}")


def inject_product_secrets(app: Path, *, ios: bool) -> None:
    script = ROOT / "scripts" / "inject_apple_secrets.py"
    cmd = [sys.executable, str(script), "--app", str(app)]
    if ios:
        cmd.append("--ios")
    subprocess.run(cmd, check=True)


def sign_and_notarize_macos(app: Path, dest_zip: Path) -> None:
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
    subprocess.run(cmd, check=True)


def package_macos_zip() -> Path:
    if not MACOS_APP.is_dir():
        raise FileNotFoundError(
            f"Missing macOS app at {MACOS_APP}. Run: cd client_app && flutter build macos"
        )
    inject_product_secrets(MACOS_APP, ios=False)
    _assert_no_priv(MACOS_APP)
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / MACOS_ZIP_NAME
    sign_and_notarize_macos(MACOS_APP, dest)
    if not dest.is_file():
        raise RuntimeError(f"sign_and_notarize_macos did not produce {dest}")
    return dest


def sign_ios_app(app: Path) -> None:
    identity = os.environ.get(
        "RP_IOS_CODESIGN_IDENTITY",
        "Apple Distribution: Russell Sneddon (SFCBP95595)",
    )
    fw_dir = app / "Frameworks"
    if fw_dir.is_dir():
        for fw in sorted(fw_dir.glob("*.framework")):
            subprocess.run(
                ["codesign", "--force", "--timestamp", "--sign", identity, str(fw)],
                check=False,
            )
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
    subprocess.run(
        ["codesign", "--force", "--timestamp", "--sign", identity, str(app)],
        check=True,
    )


def package_ios_zip() -> Path:
    if not IOS_APP.is_dir():
        raise FileNotFoundError(
            f"Missing iOS app at {IOS_APP}. Run: cd client_app && flutter build ios --no-codesign"
        )
    inject_product_secrets(IOS_APP, ios=True)
    _assert_no_priv(IOS_APP)
    try:
        sign_ios_app(IOS_APP)
    except Exception as exc:  # noqa: BLE001
        print(f"iOS codesign warning: {exc}", file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / IOS_ZIP_NAME
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in IOS_APP.rglob("*"):
            if path.is_file():
                arc = Path("Runner.app") / path.relative_to(IOS_APP)
                zf.write(path, arc.as_posix())
    return dest


def _stage_from_prior(prior_name: str, dest: Path) -> Path:
    """Copy prior release asset and rename to current VERSION filename."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    local = ROOT / "releases" / PRIOR_TAG / prior_name
    if local.is_file() and local.stat().st_size > 1_000_000:
        shutil.copy2(local, dest)
        print(f"staged from local {PRIOR_TAG}: {local.name} → {dest.name}")
        return dest
    # download prior then rename
    import urllib.request

    url = f"{PRIOR_DOWNLOAD}/{prior_name}"
    tmp = dest.parent / prior_name
    print(f"fetch {url}")
    urllib.request.urlretrieve(url, tmp)
    if tmp.resolve() != dest.resolve():
        if dest.exists():
            dest.unlink()
        tmp.rename(dest)
    if not dest.is_file() or dest.stat().st_size < 1_000_000:
        raise FileNotFoundError(f"failed to stage {prior_name} → {dest}")
    return dest


def stage_windows_exe() -> Path:
    dest = OUT / WINDOWS_EXE_NAME
    return _stage_from_prior(
        f"restore-privacy-client-{PRIOR_TAG}-windows-x64-setup.exe", dest
    )


def stage_android_apk() -> Path:
    dest = OUT / ANDROID_APK_NAME
    return _stage_from_prior(
        f"restore-privacy-client-{PRIOR_TAG}-android.apk", dest
    )


def stage_linux_tgz() -> Path:
    dest = OUT / LINUX_TGZ_NAME
    return _stage_from_prior(
        f"restore-privacy-client-{PRIOR_TAG}-linux-x64.tar.gz", dest
    )


def stage_macos_zip() -> Path:
    return package_macos_zip()


def stage_ios_zip() -> Path:
    return package_ios_zip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apple-only",
        action="store_true",
        help="Only package macOS + iOS (still write version pins; skip non-Apple carry-forward)",
    )
    ap.add_argument(
        "--with-carry-forward",
        action="store_true",
        help="Also stage Windows/Android/Linux from 0.3.0 under 0.3.2 names (default if not apple-only)",
    )
    args = ap.parse_args(argv)

    write_version_files()
    OUT.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}

    print(f"=== Restore Privacy release {VERSION} ===")

    # Apple packages are required for this release
    mac = stage_macos_zip()
    artifacts[MACOS_ZIP_NAME] = sha256_file(mac)
    print(f"macos:   {mac} ({mac.stat().st_size} bytes)")

    ios = stage_ios_zip()
    artifacts[IOS_ZIP_NAME] = sha256_file(ios)
    print(f"ios:     {ios} ({ios.stat().st_size} bytes)")

    do_carry = args.with_carry_forward or not args.apple_only
    if do_carry:
        win = stage_windows_exe()
        artifacts[WINDOWS_EXE_NAME] = sha256_file(win)
        print(f"windows: {win} ({win.stat().st_size} bytes) [carry-forward]")

        apk = stage_android_apk()
        artifacts[ANDROID_APK_NAME] = sha256_file(apk)
        print(f"android: {apk} ({apk.stat().st_size} bytes) [carry-forward]")

        linux = stage_linux_tgz()
        artifacts[LINUX_TGZ_NAME] = sha256_file(linux)
        print(f"linux:   {linux} ({linux.stat().st_size} bytes) [carry-forward]")

    _assert_no_priv(OUT)

    required = [MACOS_ZIP_NAME, IOS_ZIP_NAME]
    if do_carry:
        required.extend([WINDOWS_EXE_NAME, ANDROID_APK_NAME, LINUX_TGZ_NAME])
    missing = [n for n in required if not (OUT / n).is_file()]
    if missing:
        print(f"ERROR: missing assets: {missing}", file=sys.stderr)
        return 1

    manifest = {
        "version": VERSION,
        "tag": VERSION,
        "assets": [
            {"filename": name, "sha256": dig, "bytes": (OUT / name).stat().st_size}
            for name, dig in artifacts.items()
        ],
        "notes": (
            "0.3.2: catalog rebuild after Apple IPv6 kill-switch removal; connect pins production node Developer ID package seal + iOS Team-signed sideload; "
            "public host without NE, Packet Tunnel appex with packet-tunnel-provider; "
            "non-Apple platforms carry-forward from 0.3.1 under new catalog filenames when not rebuilt."
        ),
    }
    man_path = OUT / "SHA256SUMS.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"manifest: {man_path}")
    print("OK:", list(artifacts.keys()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
