#!/usr/bin/env python3
"""Build Restore Privacy client packages for release 0.0.1.

Produces real Windows zip (+ optional onedir exe) and Android APK when tools allow.
Never bundles secrets/*.priv into public packages.
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
VERSION = "0.0.1"
OUT = ROOT / "releases" / VERSION
DIST = ROOT / "dist" / VERSION


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


def build_windows() -> Path | None:
    """Package Windows client as zip with launcher, wintun, and public config."""
    OUT.mkdir(parents=True, exist_ok=True)
    staging = DIST / "windows-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    # App tree (no secrets)
    for rel in (
        "client",
        "node",
        "requirements.txt",
        "README.md",
    ):
        src = ROOT / rel
        dst = staging / rel
        if src.is_dir():
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    "secrets",
                    "*.priv",
                    ".pytest_cache",
                ),
            )
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # Ensure wintun is present
    wintun = ROOT / "client" / "windows" / "native" / "wintun.dll"
    if wintun.is_file():
        (staging / "client" / "windows" / "native").mkdir(parents=True, exist_ok=True)
        shutil.copy2(wintun, staging / "client" / "windows" / "native" / "wintun.dll")

    # Public config template (no private keys)
    cfg = staging / "config"
    cfg.mkdir(exist_ok=True)
    (cfg / "endpoint.json").write_text(
        json.dumps(
            {
                "version": VERSION,
                "host": "104.156.224.47",
                "port": 44044,
                "protocol": "RPT2",
                "note": "Place authorized client secrets in secrets/ (not shipped publicly).",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (cfg / "README_SECRETS.txt").write_text(
        "Do not distribute private keys in public installers.\n"
        "Operators copy client_ed25519.priv + node_elgamal.pub into secrets/ after install.\n",
        encoding="utf-8",
    )

    # Launchers
    (staging / "RestorePrivacy.bat").write_text(
        "@echo off\r\n"
        f"title Restore Privacy {VERSION}\r\n"
        "cd /d \"%~dp0\"\r\n"
        "where py >nul 2>&1 && (\r\n"
        "  py -3 -m client.windows\r\n"
        "  exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        "where python >nul 2>&1 && (\r\n"
        "  python -m client.windows\r\n"
        "  exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        "echo Python 3 is required. Install from https://www.python.org/downloads/\r\n"
        "pause\r\n"
        "exit /b 1\r\n",
        encoding="utf-8",
    )
    (staging / "INSTALL.txt").write_text(
        f"Restore Privacy Client {VERSION} — Windows\r\n"
        "=========================================\r\n"
        "1. Install Python 3.11+ and: pip install -r requirements.txt cryptography\r\n"
        "2. (Optional) copy operator secrets into secrets\\ (gitignored paths).\r\n"
        "3. Right-click RestorePrivacy.bat → Run as administrator for full VPN.\r\n"
        "4. The app auto-connects on launch.\r\n",
        encoding="utf-8",
    )
    (staging / "VERSION").write_text(VERSION + "\n", encoding="utf-8")

    zip_path = OUT / f"restore-privacy-client-{VERSION}-windows-x64.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in staging.rglob("*"):
            if path.is_file():
                # Never ship private keys
                if path.suffix == ".priv" or path.name.endswith(".priv"):
                    continue
                if "secrets" in path.parts and path.suffix in {".priv", ".key", ".pem"}:
                    continue
                zf.write(path, path.relative_to(staging).as_posix())
    return zip_path if zip_path.is_file() and zip_path.stat().st_size > 1000 else None


def build_windows_pyinstaller() -> Path | None:
    """Optional standalone onedir via PyInstaller (best-effort)."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        return None
    work = DIST / "pyi"
    work.mkdir(parents=True, exist_ok=True)
    entry = ROOT / "client" / "windows" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        f"RestorePrivacy-{VERSION}",
        "--paths",
        str(ROOT),
        "--add-data",
        f"{ROOT / 'client' / 'windows' / 'native' / 'wintun.dll'};client/windows/native",
        "--hidden-import",
        "cryptography",
        "--hidden-import",
        "node.handshake",
        "--hidden-import",
        "node.protocol",
        "--hidden-import",
        "node.elgamal",
        "--hidden-import",
        "node.pedersen",
        "--hidden-import",
        "node.crypto_session",
        str(entry),
    ]
    # Windows add-data uses ;
    env = os.environ.copy()
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log = DIST / "pyinstaller.log"
    log.write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
    if r.returncode != 0:
        return None
    built = ROOT / "dist" / f"RestorePrivacy-{VERSION}"
    if not built.is_dir():
        # pyinstaller may put under dist/
        candidates = list((ROOT / "dist").glob(f"RestorePrivacy-{VERSION}*"))
        if not candidates:
            return None
        built = candidates[0]
    zip_path = OUT / f"restore-privacy-client-{VERSION}-windows-standalone-x64.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if built.is_dir():
            for path in built.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(built.parent).as_posix())
        else:
            zf.write(built, built.name)
    return zip_path if zip_path.is_file() and zip_path.stat().st_size > 1000 else None


def build_android_apk() -> Path | None:
    """flutter build apk — real APK artifact."""
    app = ROOT / "client_app"
    if not (app / "pubspec.yaml").is_file():
        return None
    flutter = shutil.which("flutter")
    if not flutter:
        return None
    r = subprocess.run(
        [flutter, "build", "apk", "--release"],
        cwd=app,
        capture_output=True,
        text=True,
        timeout=600,
    )
    log = DIST / "flutter_apk.log"
    DIST.mkdir(parents=True, exist_ok=True)
    log.write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
    apk = app / "build" / "app" / "outputs" / "flutter-apk" / "app-release.apk"
    if r.returncode != 0 or not apk.is_file():
        return None
    dest = OUT / f"restore-privacy-client-{VERSION}-android.apk"
    shutil.copy2(apk, dest)
    return dest


def write_manifest(artifacts: list[Path]) -> Path:
    items = []
    for p in artifacts:
        if p and p.is_file():
            items.append(
                {
                    "name": p.name,
                    "size": p.stat().st_size,
                    "sha256": sha256_file(p),
                    "platform": (
                        "android"
                        if "android" in p.name
                        else "windows"
                        if "windows" in p.name
                        else "other"
                    ),
                }
            )
    man = {
        "version": VERSION,
        "tag": VERSION,
        "artifacts": items,
        "notes": "iOS/macOS installers: build on Mac (see client_app/ios and macos BUILD_ON_MAC.md).",
    }
    path = OUT / "manifest.json"
    path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    write_version_files()
    OUT.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    arts: list[Path] = []
    print("Building Windows zip…")
    w = build_windows()
    print(" windows zip:", w)
    if w:
        arts.append(w)
    print("Building Windows standalone (optional)…")
    s = build_windows_pyinstaller()
    print(" windows standalone:", s)
    if s:
        arts.append(s)
    print("Building Android APK…")
    a = build_android_apk()
    print(" android apk:", a)
    if a:
        arts.append(a)
    man = write_manifest(arts)
    print("manifest:", man)
    if len(arts) < 1:
        print("ERROR: no artifacts", file=sys.stderr)
        return 1
    # Require windows + android if possible; at least one real package
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
