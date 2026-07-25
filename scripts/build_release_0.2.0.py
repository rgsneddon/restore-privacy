#!/usr/bin/env python3
"""Build / stage Restore Privacy client packages for release 0.2.0.

Apple packages include Packet Tunnel Team signing + App Group secrets seed.
Windows/Android are staged from 0.1.2 when not rebuilt on this host.

- Windows: reuses prior .exe installer when local Windows build is unavailable
- Android: reuses prior APK when flutter apk is not rebuilt here
- macOS: zips Flutter restore_privacy_client.app after Developer ID sign/notarize
- iOS: zips Flutter Runner.app for sideload / device install tooling

Public node key (node_elgamal.pub) may be bundled via scripts/inject_apple_secrets.py.
Per-device Ed25519 client keys are generated on first run — never a shared
client_ed25519.priv. Never bundles node_elgamal.priv.
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
VERSION = "0.2.0"
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
PRIOR_TAG = "0.1.8"
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
        for old in ("0.1.9", "0.1.8", "0.1.7", "0.1.6", "0.1.5", "0.1.4", "0.1.3", "0.1.2", "0.1.1", "0.1.0", "0.0.9"):
            t2 = t2.replace(f'VERSION = "{old}"', f'VERSION = "{VERSION}"')
            t2 = t2.replace(f"build_release_{old}.py", f"build_release_{VERSION}.py")
        if t2 != t:
            inst.write_text(t2, encoding="utf-8")


def _assert_no_priv(root: Path) -> None:
    """Never ship any .priv in public packages (per-device keys are generated at runtime)."""
    for p in root.rglob("*.priv"):
        raise RuntimeError(f"refusing to package private key material: {p}")


def sign_and_notarize_macos(app: Path, dest_zip: Path) -> None:
    """Developer ID sign + notarytool + staple via shipped scripts/sign_and_notarize_macos.py.

    This is what prevents Gatekeeper "Apple could not verify Ã¢â‚¬Â¦ free of malware"
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
    """Bundle node_elgamal.pub only; device Ed25519 keys are generated on first run."""
    script = ROOT / "scripts" / "inject_apple_secrets.py"
    cmd = [sys.executable, str(script), "--app", str(app)]
    if ios:
        cmd.append("--ios")
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
    except Exception as exc:  # noqa: BLE001 Ã¢â‚¬â€ packaging continues with best effort
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
    """Download a prior public GitHub release asset (urllib, then gh)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{PRIOR_DOWNLOAD}/{name}"
    try:
        import urllib.request

        print(f"fetch {url}")
        urllib.request.urlretrieve(url, dest)
        if dest.is_file() and dest.stat().st_size > 1_000_000:
            return dest
    except Exception as exc:  # noqa: BLE001
        print(f"urllib fetch failed ({exc}); trying ghâ€¦", file=sys.stderr)
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
        raise FileNotFoundError(f"failed to fetch {url} -> {dest}")
    return dest


def rebuild_windows_setup() -> Path:
    """Rebuild Windows setup.exe via the proven PyInstaller recipe (0.0.8 module)."""
    import importlib.util

    path = ROOT / "scripts" / "build_release_0.0.8.py"
    spec = importlib.util.spec_from_file_location("rpt_build_win", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.VERSION = VERSION
    m.OUT = OUT
    m.DIST = ROOT / "dist" / VERSION
    m.CLIENT_ONEDIR_NAME = f"RestorePrivacy-{VERSION}"
    m.WINDOWS_EXE_NAME = WINDOWS_EXE_NAME
    m.ANDROID_APK_NAME = ANDROID_APK_NAME
    m.APP_NAME = "RestorePrivacy"
    onedir = m.build_client_onedir()
    setup = m.build_windows_installer_exe(onedir)
    if not setup.is_file():
        raise RuntimeError(f"Windows setup missing: {setup}")
    return setup


def stage_windows_exe() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / WINDOWS_EXE_NAME
    # Prefer a fresh PyInstaller rebuild (includes current teardown code)
    try:
        built = rebuild_windows_setup()
        if built.resolve() != dest.resolve():
            shutil.copy2(built, dest)
        print(f"windows rebuilt: {dest}")
        return dest
    except Exception as exc:  # noqa: BLE001
        print(f"Windows rebuild failed ({exc}); staging priorâ€¦", file=sys.stderr)
    local_candidates = [
        ROOT / "releases" / PRIOR_TAG / PRIOR_WINDOWS,
        ROOT / "dist" / VERSION / WINDOWS_EXE_NAME,
        ROOT / "dist" / f"RestorePrivacy-Setup-{VERSION}.exe",
        ROOT / "releases" / "0.0.8" / "restore-privacy-client-0.0.8-windows-x64-setup.exe",
    ]
    for c in local_candidates:
        if c.is_file() and c.stat().st_size > 1_000_000:
            shutil.copy2(c, dest)
            return dest
    fetch_prior_asset(PRIOR_WINDOWS, dest)
    return dest


def stage_android_apk() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / ANDROID_APK_NAME
    flutter = shutil.which("flutter")
    app = ROOT / "client_app"
    if flutter and (app / "pubspec.yaml").is_file():
        try:
            r = subprocess.run(
                [flutter, "build", "apk", "--release"],
                cwd=app,
                capture_output=True,
                text=True,
                timeout=900,
            )
            apk = app / "build" / "app" / "outputs" / "flutter-apk" / "app-release.apk"
            if r.returncode == 0 and apk.is_file() and apk.stat().st_size > 1_000_000:
                shutil.copy2(apk, dest)
                return dest
        except Exception as exc:  # noqa: BLE001
            print(f"flutter apk failed: {exc}", file=sys.stderr)
    local_candidates = [
        ROOT / "releases" / PRIOR_TAG / PRIOR_ANDROID,
        ROOT
        / "client_app"
        / "build"
        / "app"
        / "outputs"
        / "flutter-apk"
        / "app-release.apk",
        ROOT / "releases" / "0.0.8" / "restore-privacy-client-0.0.8-android.apk",
    ]
    for c in local_candidates:
        if c.is_file() and c.stat().st_size > 1_000_000:
            shutil.copy2(c, dest)
            return dest
    fetch_prior_asset(PRIOR_ANDROID, dest)
    return dest


def stage_macos_zip() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / MACOS_ZIP_NAME
    try:
        return package_macos_zip()
    except Exception as exc:  # noqa: BLE001
        print(f"macos local package skipped ({exc}); staging priorâ€¦", file=sys.stderr)
    prior = f"restore-privacy-client-{PRIOR_TAG}-macos.zip"
    fetch_prior_asset(prior, dest)
    return dest


def stage_ios_zip() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / IOS_ZIP_NAME
    try:
        return package_ios_zip()
    except Exception as exc:  # noqa: BLE001
        print(f"ios local package skipped ({exc}); staging priorâ€¦", file=sys.stderr)
    prior = f"restore-privacy-client-{PRIOR_TAG}-ios.zip"
    fetch_prior_asset(prior, dest)
    return dest


def main() -> int:
    write_version_files()
    OUT.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}

    print(f"=== Restore Privacy release {VERSION} ===")
    win = stage_windows_exe()
    artifacts[WINDOWS_EXE_NAME] = sha256_file(win)
    print(f"windows: {win} ({win.stat().st_size} bytes)")

    apk = stage_android_apk()
    artifacts[ANDROID_APK_NAME] = sha256_file(apk)
    print(f"android: {apk} ({apk.stat().st_size} bytes)")

    mac = stage_macos_zip()
    artifacts[MACOS_ZIP_NAME] = sha256_file(mac)
    print(f"macos:   {mac} ({mac.stat().st_size} bytes)")

    ios = stage_ios_zip()
    artifacts[IOS_ZIP_NAME] = sha256_file(ios)
    print(f"ios:     {ios} ({ios.stat().st_size} bytes)")

    # Bake-in Linux installer (manylinux cryptography wheels offline)
    LINUX_TGZ_NAME = f"restore-privacy-client-{VERSION}-linux-x64.tar.gz"
    try:
        import importlib.util

        pl_path = ROOT / "scripts" / "package_linux.py"
        spec = importlib.util.spec_from_file_location("package_linux", pl_path)
        pl = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(pl)
        rc = pl.main()
        linux_path = OUT / LINUX_TGZ_NAME
        if rc == 0 and linux_path.is_file():
            artifacts[LINUX_TGZ_NAME] = sha256_file(linux_path)
            print(f"linux:   {linux_path} ({linux_path.stat().st_size} bytes)")
        else:
            print("WARNING: package_linux failed or missing output", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"linux package skipped ({exc})", file=sys.stderr)

    # Final no-secrets check on release dir
    _assert_no_priv(OUT)

    required = [
        WINDOWS_EXE_NAME,
        ANDROID_APK_NAME,
        MACOS_ZIP_NAME,
        IOS_ZIP_NAME,
        LINUX_TGZ_NAME,
    ]
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
            "0.2.0: Linux installer package with baked-in cryptography wheels; "
            "Ubuntu 20.04+ family support; tray logo; clean UI. "
            "0.1.7: tray logo+status, mojibake-free UI, same-version install speed."
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
