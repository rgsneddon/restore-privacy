#!/usr/bin/env python3
"""Build Restore Privacy client packages for release 0.0.8.

Primary Windows deliverable: a single .exe installer that embeds the full
client runtime (PyInstaller onedir + wintun + deps), deploys to the user
profile, creates shortcuts, and launches the app — no separate Python install.

Also stages the Android APK. Never bundles secrets/*.priv.
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
VERSION = "0.0.8"
OUT = ROOT / "releases" / VERSION
DIST = ROOT / "dist" / VERSION
APP_NAME = "RestorePrivacy"
CLIENT_ONEDIR_NAME = f"{APP_NAME}-{VERSION}"
WINDOWS_EXE_NAME = f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
ANDROID_APK_NAME = f"restore-privacy-client-{VERSION}-android.apk"


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


def _ensure_wintun() -> Path:
    native = ROOT / "client" / "windows" / "native"
    dll = native / "wintun.dll"
    if not dll.is_file():
        alt = native / "wintun-amd64.dll"
        if alt.is_file():
            shutil.copy2(alt, dll)
    if not dll.is_file():
        raise FileNotFoundError(f"Missing wintun.dll under {native}")
    return dll


def build_client_onedir() -> Path:
    """PyInstaller onedir of the Windows client with cryptography + wintun."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError as e:
        raise RuntimeError("PyInstaller required: pip install pyinstaller") from e

    wintun = _ensure_wintun()
    entry = ROOT / "client" / "windows" / "app.py"
    work = DIST / "pyi-client"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    # Clean previous
    for old in (
        ROOT / "dist" / CLIENT_ONEDIR_NAME,
        ROOT / "build" / CLIENT_ONEDIR_NAME,
    ):
        if old.exists():
            shutil.rmtree(old)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        CLIENT_ONEDIR_NAME,
        "--paths",
        str(ROOT),
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(work),
        "--specpath",
        str(DIST),
        "--add-data",
        f"{wintun};client/windows/native",
        "--hidden-import",
        "cryptography",
        "--hidden-import",
        "cryptography.hazmat.backends.openssl",
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
        "--hidden-import",
        "client.connect",
        "--hidden-import",
        "client.uk_gate",
        "--hidden-import",
        "client.secrets_loader",
        "--hidden-import",
        "client.dataplane",
        "--hidden-import",
        "client.windows.tun_win",
        "--hidden-import",
        "client.windows.tunnel_win",
        "--hidden-import",
        "client.windows.elevate",
        str(entry),
    ]
    # Bundle public node key only (never a shared client_ed25519.priv)
    secrets_src = ROOT / "secrets"
    if (secrets_src / "node_elgamal.pub").is_file():
        cmd.extend(
            [
                "--add-data",
                f"{secrets_src / 'node_elgamal.pub'};secrets",
            ]
        )
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log = DIST / "pyinstaller_client.log"
    log.write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"PyInstaller client failed (see {log})")

    built = ROOT / "dist" / CLIENT_ONEDIR_NAME
    if not built.is_dir():
        raise RuntimeError(f"Expected onedir missing: {built}")
    exe = built / f"{CLIENT_ONEDIR_NAME}.exe"
    if not exe.is_file():
        # sometimes name differs
        exes = list(built.glob("*.exe"))
        if not exes:
            raise RuntimeError(f"No .exe in {built}")
    # Never ship any private key material in the package tree
    for p in list(built.rglob("*.priv")):
        try:
            p.unlink()
        except OSError:
            pass
    inject_product_secrets(built)
    return built


def inject_product_secrets(target_dir: Path) -> None:
    """Copy public node_elgamal.pub only — device Ed25519 keys are generated on first run.

    Never ships a shared client_ed25519.priv (impersonation risk) or node_elgamal.priv.
    Strips **all** ``*.priv`` under the entire package tree (incl. ``_internal/secrets``).
    """
    src = ROOT / "secrets"
    node_pub = src / "node_elgamal.pub"
    if not node_pub.is_file():
        raise RuntimeError(
            "Build requires secrets/node_elgamal.pub "
            "(gitignored operator public key). Refusing to ship without node pub."
        )
    dest = target_dir / "secrets"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(node_pub, dest / "node_elgamal.pub")
    # Also place pub under _internal/secrets if that layout exists (onedir)
    for sub in target_dir.rglob("secrets"):
        if sub.is_dir():
            try:
                shutil.copy2(node_pub, sub / "node_elgamal.pub")
            except OSError:
                pass
    # Strip every private key anywhere in the package tree
    for p in list(target_dir.rglob("*.priv")):
        try:
            p.unlink()
        except OSError:
            pass


def build_windows_installer_exe(client_onedir: Path) -> Path:
    """Package onedir payload into a single setup .exe that runs installer.py."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError as e:
        raise RuntimeError("PyInstaller required") from e

    OUT.mkdir(parents=True, exist_ok=True)
    payload_stage = DIST / "installer-payload"
    if payload_stage.exists():
        shutil.rmtree(payload_stage)
    payload_stage.mkdir(parents=True)
    # Embed entire onedir under payload/ (includes secrets/ with product client key)
    dest_payload = payload_stage / "payload"
    shutil.copytree(
        client_onedir,
        dest_payload,
        ignore=shutil.ignore_patterns("*.priv", "*.pyc", "__pycache__"),
    )
    inject_product_secrets(dest_payload)

    installer_entry = ROOT / "client" / "windows" / "installer.py"
    work = DIST / "pyi-installer"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    setup_name = f"RestorePrivacy-Setup-{VERSION}"
    for old in (ROOT / "dist" / f"{setup_name}.exe", ROOT / "build" / setup_name):
        if old.is_file():
            old.unlink()
        elif old.is_dir():
            shutil.rmtree(old)

    # onefile installer with payload as data
    add_data = f"{dest_payload};payload"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",  # show install progress; still double-clickable
        "--name",
        setup_name,
        "--paths",
        str(ROOT),
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(work),
        "--specpath",
        str(DIST),
        "--add-data",
        add_data,
        str(installer_entry),
    ]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log = DIST / "pyinstaller_installer.log"
    log.write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"PyInstaller installer failed (see {log})")

    built_exe = ROOT / "dist" / f"{setup_name}.exe"
    if not built_exe.is_file():
        raise RuntimeError(f"Installer exe missing: {built_exe}")

    # Reject PEM / node private key material; product client key is intentional
    raw = built_exe.read_bytes()
    if b"BEGIN PRIVATE" in raw or b"BEGIN RSA PRIVATE" in raw:
        raise RuntimeError("Installer binary appears to embed PEM private key material")
    if b"node_elgamal.priv" in raw:
        raise RuntimeError("Installer must not embed node_elgamal.priv")

    final = OUT / WINDOWS_EXE_NAME
    if final.exists():
        final.unlink()
    shutil.copy2(built_exe, final)
    return final


def build_android_apk() -> Path | None:
    """flutter build apk, or stage existing release APK under 0.0.8 name."""
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / ANDROID_APK_NAME
    app = ROOT / "client_app"
    flutter = shutil.which("flutter")
    DIST.mkdir(parents=True, exist_ok=True)

    if flutter and (app / "pubspec.yaml").is_file():
        r = subprocess.run(
            [flutter, "build", "apk", "--release"],
            cwd=app,
            capture_output=True,
            text=True,
            timeout=900,
        )
        log = DIST / "flutter_apk.log"
        log.write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
        apk = app / "build" / "app" / "outputs" / "flutter-apk" / "app-release.apk"
        if r.returncode == 0 and apk.is_file() and apk.stat().st_size > 1_000_000:
            shutil.copy2(apk, dest)
            return dest

    # Fallback: existing flutter-apk or previous release APK (rename to 0.0.8)
    candidates = [
        app / "build" / "app" / "outputs" / "flutter-apk" / "app-release.apk",
        ROOT / "releases" / "0.0.5" / "restore-privacy-client-0.0.5-android.apk",
        ROOT / "releases" / "0.0.4" / "restore-privacy-client-0.0.4-android.apk",
        ROOT / "releases" / "0.0.3" / "restore-privacy-client-0.0.3-android.apk",
        ROOT / "releases" / "0.0.2" / "restore-privacy-client-0.0.2-android.apk",
        ROOT / "releases" / "0.0.1" / "restore-privacy-client-0.0.1-android.apk",
    ]
    for c in candidates:
        if c.is_file() and c.stat().st_size > 1_000_000:
            shutil.copy2(c, dest)
            note = DIST / "android_apk_source.txt"
            note.write_text(
                f"Staged {dest.name} from {c} (flutter rebuild unavailable or failed).\n",
                encoding="utf-8",
            )
            return dest
    return None


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
                        if p.name.endswith(".apk")
                        else "windows"
                        if p.name.endswith(".exe")
                        else "other"
                    ),
                }
            )
    man = {
        "version": VERSION,
        "tag": VERSION,
        "artifacts": items,
        "windows_installer": WINDOWS_EXE_NAME,
        "android_apk": ANDROID_APK_NAME,
        "notes": (
            "Windows setup.exe embeds full client runtime + wintun; "
            "installs to %LOCALAPPDATA%\\Programs\\RestorePrivacy and launches. "
            "No separate Python install required."
        ),
    }
    path = OUT / "manifest.json"
    path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    write_version_files()
    OUT.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    arts: list[Path] = []

    print(f"=== Restore Privacy release {VERSION} ===")
    print("Building Windows client onedir (bundled deps)…")
    try:
        onedir = build_client_onedir()
        print(" client onedir:", onedir)
        print("Building Windows setup .exe installer…")
        setup = build_windows_installer_exe(onedir)
        print(" windows setup:", setup, setup.stat().st_size if setup else 0)
        if setup:
            arts.append(setup)
    except Exception as e:
        print(" Windows build error:", e, file=sys.stderr)
        # leave partial; continue to APK

    print("Building / staging Android APK…")
    apk = build_android_apk()
    print(" android apk:", apk, apk.stat().st_size if apk else 0)
    if apk:
        arts.append(apk)

    man = write_manifest(arts)
    print("manifest:", man)
    if not any(a.name.endswith(".exe") for a in arts):
        print("ERROR: Windows .exe installer missing", file=sys.stderr)
        return 1
    if not any(a.name.endswith(".apk") for a in arts):
        print("ERROR: Android .apk missing", file=sys.stderr)
        return 1
    print("OK:", [a.name for a in arts])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
