#!/usr/bin/env python3
"""Windows client installer for Restore Privacy.

Deploys the bundled client (runtime + wintun + deps) into the user profile
and launches it. Designed to run as a PyInstaller onefile that embeds the
prebuilt onedir client payload under payload/.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

APP_NAME = "RestorePrivacy"
VERSION = "0.0.5"
# Install under LocalAppData so no elevation is required for deploy.
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / APP_NAME
START_MENU = (
    Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / APP_NAME
)
DESKTOP = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"


def _payload_root() -> Path:
    """Locate embedded client payload (PyInstaller _MEIPASS or sibling)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        cand = base / "payload"
        if cand.is_dir():
            return cand
        # onedir payload may be nested as RestorePrivacy-VERSION
        for child in base.iterdir():
            if child.is_dir() and (child / f"{APP_NAME}-{VERSION}.exe").is_file():
                return child
            if child.is_dir() and (child / f"{APP_NAME}.exe").is_file():
                return child
        return base
    # Dev / non-frozen: look for dist onedir next to repo
    here = Path(__file__).resolve().parent
    repo = here.parents[1]
    for name in (f"{APP_NAME}-{VERSION}", APP_NAME):
        d = repo / "dist" / name
        if d.is_dir():
            return d
    raise FileNotFoundError(
        "Client payload not found. Build with scripts/build_release_0.0.5.py first."
    )


def _find_client_exe(root: Path) -> Path:
    for name in (f"{APP_NAME}-{VERSION}.exe", f"{APP_NAME}.exe", "RestorePrivacy.exe"):
        p = root / name
        if p.is_file():
            return p
    # Search one level deep
    for p in root.rglob("*.exe"):
        if "uninstall" in p.name.lower():
            continue
        if APP_NAME.lower() in p.name.lower() or "restore" in p.name.lower():
            return p
    raise FileNotFoundError(f"No client .exe under {root}")


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("*.priv", "*.pyc", "__pycache__"),
    )


def _write_version(install_dir: Path) -> None:
    (install_dir / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    (install_dir / "INSTALL.txt").write_text(
        f"Restore Privacy Client {VERSION}\r\n"
        "Installed with bundled Python runtime and dependencies.\r\n"
        "Run RestorePrivacy as Administrator for full system VPN.\r\n"
        f"Install path: {install_dir}\r\n",
        encoding="utf-8",
    )


def _create_shortcut(target: Path, link_path: Path, workdir: Path) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    # PowerShell COM shortcut (no extra deps)
    ps = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut({str(link_path)!r}); '
        f'$s.TargetPath = {str(target)!r}; '
        f'$s.WorkingDirectory = {str(workdir)!r}; '
        f'$s.Description = "Restore Privacy VPN Client {VERSION}"; '
        f"$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def install(launch: bool = True) -> Path:
    """Deploy bundled client to INSTALL_DIR and optionally launch it."""
    payload = _payload_root()
    client_src_exe = _find_client_exe(payload)
    # If payload root is the onedir folder, copy whole tree
    payload_dir = client_src_exe.parent

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    _copy_tree(payload_dir, INSTALL_DIR)
    _write_version(INSTALL_DIR)

    installed_exe = INSTALL_DIR / client_src_exe.name
    if not installed_exe.is_file():
        # rename if needed
        candidates = list(INSTALL_DIR.glob("*.exe"))
        if not candidates:
            raise FileNotFoundError("Install copy failed — no .exe in install dir")
        installed_exe = candidates[0]

    # Start menu + desktop shortcuts
    try:
        _create_shortcut(
            installed_exe,
            START_MENU / f"{APP_NAME}.lnk",
            INSTALL_DIR,
        )
        _create_shortcut(
            installed_exe,
            DESKTOP / f"{APP_NAME}.lnk",
            INSTALL_DIR,
        )
    except Exception:
        # Shortcuts are nice-to-have; install still succeeds
        pass

    # Tiny uninstaller helper (batch)
    uninst = INSTALL_DIR / "Uninstall.bat"
    uninst.write_text(
        "@echo off\r\n"
        f"title Uninstall Restore Privacy {VERSION}\r\n"
        f'rmdir /s /q "%LOCALAPPDATA%\\Programs\\{APP_NAME}"\r\n'
        f'rmdir /s /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{APP_NAME}"\r\n'
        f'del /q "%USERPROFILE%\\Desktop\\{APP_NAME}.lnk" 2>nul\r\n'
        "echo Uninstalled.\r\n"
        "pause\r\n",
        encoding="utf-8",
    )

    if launch and installed_exe.is_file():
        subprocess.Popen(
            [str(installed_exe)],
            cwd=str(INSTALL_DIR),
            close_fds=True,
        )
    return installed_exe


def main() -> int:
    try:
        path = install(launch=True)
        # Brief console feedback if a console is attached
        print(f"Installed Restore Privacy {VERSION} to:\n  {INSTALL_DIR}")
        print(f"Launched: {path}")
        return 0
    except Exception as e:
        msg = f"Install failed: {e}\n{traceback.format_exc()}"
        print(msg, file=sys.stderr)
        try:
            # Message box when running windowed / double-clicked
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, msg[:1000], "Restore Privacy Installer", 0x10)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
