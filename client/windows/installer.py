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
VERSION = "0.1.0"
# Install under LocalAppData so no elevation is required for deploy.
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / APP_NAME
USER_SECRETS = Path.home() / ".restore-privacy" / "secrets"
START_MENU = (
    Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / APP_NAME
)
DESKTOP = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
# Product admission keys only (never node_elgamal.priv)
CLIENT_PRIV = "client_ed25519.priv"
NODE_PUB = "node_elgamal.pub"


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
        "Client payload not found. Build with scripts/build_release_0.1.0.py first."
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
    # Allow product client_ed25519.priv in payload secrets/; never copy node_elgamal.priv
    def _ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for n in names:
            if n.endswith(".pyc") or n == "__pycache__":
                ignored.add(n)
            if n == "node_elgamal.priv":
                ignored.add(n)
        return ignored

    shutil.copytree(src, dst, ignore=_ignore)


def _find_payload_secrets(payload_dir: Path) -> Path | None:
    for cand in (
        payload_dir / "secrets",
        payload_dir.parent / "secrets",
    ):
        if (cand / CLIENT_PRIV).is_file() and (cand / NODE_PUB).is_file():
            return cand
    # Nested onedir
    for p in payload_dir.rglob(CLIENT_PRIV):
        parent = p.parent
        if (parent / NODE_PUB).is_file() and parent.name == "secrets":
            return parent
    return None


def _provision_secrets(payload_dir: Path, install_dir: Path) -> list[str]:
    """Install admission keys where the client resolver will find them."""
    written: list[str] = []
    src = _find_payload_secrets(payload_dir)
    # Also try shipping secrets next to installer meipass
    if src is None and getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        for cand in (base / "secrets", base / "payload" / "secrets"):
            if (cand / CLIENT_PRIV).is_file() and (cand / NODE_PUB).is_file():
                src = cand
                break
    if src is None:
        return written

    for dest in (install_dir / "secrets", USER_SECRETS):
        dest.mkdir(parents=True, exist_ok=True)
        for name in (CLIENT_PRIV, NODE_PUB):
            data = (src / name).read_bytes()
            # Never write node private key even if mis-named
            if name.endswith(".priv") and name != CLIENT_PRIV:
                continue
            target = dest / name
            target.write_bytes(data)
            written.append(str(target))
    return written


def _write_version(install_dir: Path) -> None:
    (install_dir / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    secrets_ok = (install_dir / "secrets" / CLIENT_PRIV).is_file()
    sec_line = (
        "Admission secrets installed: yes"
        if secrets_ok
        else f"Admission secrets missing — place {CLIENT_PRIV} and {NODE_PUB} in secrets\\"
    )
    (install_dir / "INSTALL.txt").write_text(
        f"Restore Privacy Client {VERSION}\r\n"
        "Installed with bundled Python runtime and dependencies.\r\n"
        "Full tunnel: double-click the shortcut (UAC prompt once) — no need to right-click Run as admin.\r\n"
        "The app also auto-requests elevation on launch if needed.\r\n"
        f"Install path: {install_dir}\r\n"
        f"{sec_line}\r\n",
        encoding="utf-8",
    )


def _create_shortcut(target: Path, link_path: Path, workdir: Path) -> None:
    """Create .lnk; mark Run as administrator so double-click triggers UAC once."""
    link_path.parent.mkdir(parents=True, exist_ok=True)
    # PowerShell COM shortcut + set "Run as administrator" bit (0x20 at offset 0x15)
    ps = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut({str(link_path)!r}); '
        f'$s.TargetPath = {str(target)!r}; '
        f'$s.WorkingDirectory = {str(workdir)!r}; '
        f'$s.Description = "Restore Privacy VPN Client {VERSION} (elevates for full tunnel)"; '
        f"$s.Save(); "
        f"$p = {str(link_path)!r}; "
        f"$b = [System.IO.File]::ReadAllBytes($p); "
        f"if ($b.Length -gt 0x15) {{ $b[0x15] = $b[0x15] -bor 0x20; "
        f"[System.IO.File]::WriteAllBytes($p, $b) }}"
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
    secrets_written = _provision_secrets(payload_dir, INSTALL_DIR)
    _write_version(INSTALL_DIR)

    installed_exe = INSTALL_DIR / client_src_exe.name
    if not installed_exe.is_file():
        # rename if needed
        candidates = list(INSTALL_DIR.glob("*.exe"))
        if not candidates:
            raise FileNotFoundError("Install copy failed — no .exe in install dir")
        installed_exe = candidates[0]

    if not secrets_written:
        # Still launch, but user will see a clear secrets error from the app
        print(
            "WARNING: admission secrets not found in installer payload. "
            f"Place {CLIENT_PRIV} and {NODE_PUB} under {INSTALL_DIR / 'secrets'}"
        )

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
        sec = INSTALL_DIR / "secrets"
        print(f"Secrets dir: {sec} present={sec.is_dir()}")
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
