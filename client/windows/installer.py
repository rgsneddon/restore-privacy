#!/usr/bin/env python3
"""Windows client installer for Restore Privacy.

Deploys the bundled client (runtime + wintun + deps) into the standard machine
program folder **Program Files\\Restore Privacy** (bundle: client exe +
Restore Internet failsafe). Designed to run as a PyInstaller onefile that
embeds the prebuilt onedir client payload under payload/.

Elevation: Program Files typically requires Administrator. Without rights the
installer falls soft to the per-user LocalAppData path (honest message) unless
``RPT_INSTALL_DIR`` / ``RPT_INSTALL_PER_USER`` forces a root.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from client.install_paths import (
    PRODUCT_FOLDER_DISPLAY,
    PRODUCT_FOLDER_LEGACY_ID,
    default_windows_install_dir,
    inventory_install_bundle,
    is_under_program_files,
    per_user_windows_install_dir,
)

APP_NAME = "RestorePrivacy"
# Baked by scripts/build_release_*.py write_version_files (monopin). Never use a
# stale historical pin as the only identity when client/VERSION is missing.
PRODUCT_VERSION_EMBEDDED = "1.2.0"


def _product_version_pin() -> str:
    """Resolve product monopin for installer UI and VERSION files.

    Order: env override → client/VERSION near source → frozen PyInstaller
    datas (``client/VERSION`` / ``VERSION`` under ``_MEIPASS`` and payload) →
    :data:`PRODUCT_VERSION_EMBEDDED` (current monopin, rewritten at release).
    """
    env = (os.environ.get("RPT_PRODUCT_VERSION") or "").strip().lstrip("vV")
    if env:
        return env

    candidates: list[Path] = []
    try:
        here = Path(__file__).resolve()
        # Dev: client/VERSION (installer lives in client/windows/)
        candidates.append(here.parents[1] / "VERSION")
        # Repo root client/VERSION when layout differs
        if len(here.parents) > 2:
            candidates.append(here.parents[2] / "client" / "VERSION")
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        try:
            mei = Path(sys._MEIPASS)  # type: ignore[attr-defined]
            candidates.extend(
                [
                    mei / "client" / "VERSION",
                    mei / "VERSION",
                    mei / "payload" / "VERSION",
                    mei / "payload" / "client" / "VERSION",
                    mei / "payload" / "_internal" / "client" / "VERSION",
                ]
            )
        except Exception:
            pass

    for pin in candidates:
        try:
            if not pin.is_file():
                continue
            line = pin.read_text(encoding="utf-8").strip().splitlines()[0].strip()
            v = line.lstrip("vV")
            if v:
                return v
        except (OSError, IndexError, TypeError, ValueError):
            continue
    return (PRODUCT_VERSION_EMBEDDED or "0.0.0").strip().lstrip("vV") or "0.0.0"


VERSION = _product_version_pin()


def _restore_internet_source_candidates(filename: str = "Restore Internet.bat") -> list[Path]:
    """Locate shipped failsafe sources (dev tree, frozen MEIPASS, payload)."""
    cands: list[Path] = []
    try:
        here = Path(__file__).resolve().parent
        cands.append(here / filename)
        # Alias without space
        if filename == "Restore Internet.bat":
            cands.append(here / "RestoreInternet.bat")
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        try:
            mei = Path(sys._MEIPASS)  # type: ignore[attr-defined]
            for base in (
                mei,
                mei / "client" / "windows",
                mei / "payload",
                mei / "payload" / "client" / "windows",
                mei / "_internal" / "client" / "windows",
            ):
                cands.append(base / filename)
                if filename == "Restore Internet.bat":
                    cands.append(base / "RestoreInternet.bat")
        except Exception:
            pass
    return cands


def load_full_restore_internet_bat_text() -> str:
    """Return the full Restore Internet failsafe body (never the rmdir-only stub).

    Prefers on-disk source next to this module / frozen datas. Falls back to an
    embedded full failsafe that restores routes, clears RPT-KS/RPT-FW, removes
    product trees and shortcuts.
    """
    for cand in _restore_internet_source_candidates("Restore Internet.bat"):
        try:
            if not cand.is_file():
                continue
            text = cand.read_text(encoding="utf-8", errors="replace")
            if is_full_restore_internet_failsafe(text):
                return text if text.endswith("\n") else text + "\n"
        except OSError:
            continue
    return FULL_RESTORE_INTERNET_BAT_EMBEDDED


def is_full_restore_internet_failsafe(text: str) -> bool:
    """True when *text* is the full residual restore + product removal failsafe."""
    if not text or len(text) < 200:
        return False
    low = text.lower()
    # Must restore dual /1 residual routes
    if "0.0.0.0" not in text or "128.0.0.0" not in text:
        return False
    # Must clear product firewall (KS and/or FW rules)
    if "rpt-ks" not in low and "rpt-fw" not in low:
        return False
    # Must remove product install tree (not only route deletes)
    if "restoreprivacy" not in low and "localappdata" not in low:
        return False
    # Reject historical three-line stub (route delete x3 + rmdir only, no KS)
    if "remove-netfirewallrule" not in low and "rpt-ks" not in low:
        return False
    return True


def ship_restore_internet_failsafe(install_dir: Path | str) -> Path:
    """Write full Restore Internet.bat (+ alias) under *install_dir*. Returns primary path."""
    root = Path(install_dir)
    root.mkdir(parents=True, exist_ok=True)
    body = load_full_restore_internet_bat_text()
    if not is_full_restore_internet_failsafe(body):
        body = FULL_RESTORE_INTERNET_BAT_EMBEDDED
    # Normalize CRLF for Windows cmd
    body = body.replace("\r\n", "\n").replace("\n", "\r\n")
    if not body.endswith("\r\n"):
        body += "\r\n"
    primary = root / "Restore Internet.bat"
    alias = root / "RestoreInternet.bat"
    primary.write_text(body, encoding="utf-8")
    alias.write_text(body, encoding="utf-8")
    return primary


# Embedded full failsafe — used when source .bat is not next to frozen installer.
# Keep in sync with client/windows/Restore Internet.bat (residual + KS + uninstall).
FULL_RESTORE_INTERNET_BAT_EMBEDDED = r"""@echo off
REM =============================================================================
REM Restore Internet — failsafe residual restore + complete product removal
REM =============================================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "QUIET=0"
set "NODE=82.221.101.241"
set "APPNAME=RestorePrivacy"
set "DISPLAY=Privacy Restored"
if /I "%~1"=="/quiet" set "QUIET=1"
if /I "%~2"=="/quiet" set "QUIET=1"
if not "%~1"=="" if /I not "%~1"=="/quiet" set "NODE=%~1"

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator for Restore Internet (network + uninstall)...
  powershell -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '/quiet' -Verb RunAs -Wait"
  exit /b %ERRORLEVEL%
)

title Restore Internet — Restore Privacy failsafe
echo.
echo === Restore Internet ===
echo Restoring normal internet, then removing Restore Privacy from this PC...
echo.

echo [1/4] Removing residual dual /1 routes and server pin...
route delete 0.0.0.0 mask 128.0.0.0 >nul 2>&1
route delete 128.0.0.0 mask 128.0.0.0 >nul 2>&1
route delete 0.0.0.0 mask 128.0.0.0 0.0.0.0 >nul 2>&1
route delete 128.0.0.0 mask 128.0.0.0 0.0.0.0 >nul 2>&1
route delete %NODE% mask 255.255.255.255 >nul 2>&1

echo [2/4] Clearing RPT kill-switch / profile Block and re-enabling IPv6...
powershell -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Continue';" ^
  "Get-NetFirewallRule -EA SilentlyContinue | Where-Object { $_.DisplayName -like 'RPT-KS-*' -or $_.DisplayName -like 'RPT-FW-*' } | Remove-NetFirewallRule -EA SilentlyContinue;" ^
  "$sp=Join-Path $env:ProgramData 'RestorePrivacy\ks-outbound-state.json';" ^
  "if (Test-Path $sp) { try { $p=Get-Content $sp -Raw|ConvertFrom-Json; foreach($n in @('Domain','Private','Public')){ $v=$p.$n; if(-not $v){$v='Allow'}; Set-NetFirewallProfile -Name $n -DefaultOutboundAction $v -EA SilentlyContinue }; Remove-Item $sp -Force -EA SilentlyContinue } catch { foreach($n in @('Domain','Private','Public')){ Set-NetFirewallProfile -Name $n -DefaultOutboundAction Allow -EA SilentlyContinue } } } else { foreach($n in @('Domain','Private','Public')){ Set-NetFirewallProfile -Name $n -DefaultOutboundAction Allow -EA SilentlyContinue } };" ^
  "Get-NetAdapter -EA SilentlyContinue | ForEach-Object { Enable-NetAdapterBinding -Name $_.Name -ComponentID ms_tcpip6 -Confirm:$false -EA SilentlyContinue };" ^
  "netsh interface teredo set state default | Out-Null;" ^
  "Write-Output RPT_RESTORE_INTERNET_NET_OK"

echo [3/4] Stopping product process...
taskkill /F /IM RestorePrivacy.exe >nul 2>&1
taskkill /F /IM "Restore Privacy.exe" >nul 2>&1
timeout /t 1 /nobreak >nul 2>&1

echo [4/4] Removing product tree, shortcuts, secrets...
set "PORTABLE=%~dp0"
if "%PORTABLE:~-1%"=="\" set "PORTABLE=%PORTABLE:~0,-1%"
set "INSTALL=%LOCALAPPDATA%\Programs\%APPNAME%"

if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\%APPNAME%" (
  rmdir /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\%APPNAME%" 2>nul
)
del /q "%USERPROFILE%\Desktop\%DISPLAY%.lnk" 2>nul
del /q "%USERPROFILE%\Desktop\Privacy, Restored.lnk" 2>nul
del /q "%USERPROFILE%\Desktop\%APPNAME%.lnk" 2>nul
del /q "%USERPROFILE%\Desktop\Restore Internet.lnk" 2>nul
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\%DISPLAY%.lnk" 2>nul
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Restore Internet.lnk" 2>nul

if exist "%USERPROFILE%\.restore-privacy" (
  rmdir /s /q "%USERPROFILE%\.restore-privacy" 2>nul
)
if exist "%ProgramData%\RestorePrivacy" (
  rmdir /s /q "%ProgramData%\RestorePrivacy" 2>nul
)
if exist "%LOCALAPPDATA%\RestorePrivacy" (
  rmdir /s /q "%LOCALAPPDATA%\RestorePrivacy" 2>nul
)

if exist "%INSTALL%\RestorePrivacy.exe" (
  rmdir /s /q "%INSTALL%" 2>nul
)
if exist "%INSTALL%" (
  rmdir /s /q "%INSTALL%" 2>nul
)

if exist "%~dp0RestorePrivacy.exe" (
  echo Portable package detected — scheduling full tree removal...
  start "" /min powershell -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 2; if (Test-Path -LiteralPath '%PORTABLE%') { Remove-Item -LiteralPath '%PORTABLE%' -Recurse -Force -ErrorAction SilentlyContinue }"
)

if exist "%~dp0RestorePrivacy.exe" del /f /q "%~dp0RestorePrivacy.exe" 2>nul
if exist "%~dp0run.bat" del /f /q "%~dp0run.bat" 2>nul
if exist "%~dp0AllowFirewall.bat" del /f /q "%~dp0AllowFirewall.bat" 2>nul
if exist "%~dp0_internal" rmdir /s /q "%~dp0_internal" 2>nul
if exist "%~dp0client" rmdir /s /q "%~dp0client" 2>nul
if exist "%~dp0product" rmdir /s /q "%~dp0product" 2>nul
if exist "%~dp0secrets" rmdir /s /q "%~dp0secrets" 2>nul

echo.
echo Restore Internet complete.
if "%QUIET%"=="1" exit /b 0
pause
exit /b 0
"""


# User-facing shortcut name (Start Menu + Desktop). Tray hover text is rpT0.
SHORTCUT_DISPLAY_NAME = "Privacy, Restored"
# Default: Program Files\Restore Privacy (see client.install_paths).
INSTALL_DIR = default_windows_install_dir()
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
        "Client payload not found. Build with scripts/build_release_"
        f"{PRODUCT_VERSION_EMBEDDED}.py (or build_windows_multihop) first."
    )


def _find_client_exe(root: Path) -> Path:
    for name in (f"{APP_NAME}-{VERSION}.exe", f"{APP_NAME}.exe", "RestorePrivacy.exe"):
        p = root / name
        if p.is_file():
            return p
    # Shallow only (onedir layout)  -  never full-tree rglob (slow on large payloads)
    try:
        for child in root.iterdir():
            if not child.is_dir():
                continue
            for name in (f"{APP_NAME}-{VERSION}.exe", f"{APP_NAME}.exe", "RestorePrivacy.exe"):
                p = child / name
                if p.is_file():
                    return p
            for p in child.glob("*.exe"):
                if "uninstall" in p.name.lower():
                    continue
                if APP_NAME.lower() in p.name.lower() or "restore" in p.name.lower():
                    return p
    except OSError:
        pass
    raise FileNotFoundError(f"No client .exe under {root}")


def _rmtree_best_effort(path: Path) -> None:
    """Remove directory tree; on Windows, retry/chmod locked files when possible."""
    if not path.exists():
        return

    def _onerror(func, p, _exc_info) -> None:  # type: ignore[no-untyped-def]
        try:
            os.chmod(p, 0o700)
            func(p)
        except Exception:
            pass

    try:
        shutil.rmtree(path, onerror=_onerror)
    except TypeError:
        # Python 3.12+ prefers onexc
        def _onexc(_func, p, _exc) -> None:  # type: ignore[no-untyped-def]
            try:
                os.chmod(p, 0o700)
                _func(p)
            except Exception:
                pass

        shutil.rmtree(path, onexc=_onexc)
    if path.exists():
        # Fallback: rename locked tree aside so copy can proceed
        bak = path.with_name(path.name + ".old")
        try:
            if bak.exists():
                shutil.rmtree(bak, ignore_errors=True)
            path.rename(bak)
        except OSError as exc:
            raise RuntimeError(
                f"Could not replace existing install at {path}. "
                f"Close Restore Privacy / rpT0 if it is running, then try again. ({exc})"
            ) from exc


def _copy_tree(src: Path, dst: Path) -> None:
    """Copy product tree quickly (robocopy multi-thread on Windows when available)."""
    _rmtree_best_effort(dst)
    # Never copy any .priv (shared client_ed25519.priv or node_elgamal.priv)
    def _ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for n in names:
            if n.endswith(".pyc") or n == "__pycache__":
                ignored.add(n)
            if n.endswith(".priv"):
                ignored.add(n)
        return ignored

    if sys.platform == "win32":
        try:
            # /MT multi-thread copy is much faster than shutil for large onedir payloads
            dst.mkdir(parents=True, exist_ok=True)
            cmd = [
                "robocopy",
                str(src),
                str(dst),
                "/E",
                "/NFL",
                "/NDL",
                "/NJH",
                "/NJS",
                "/NC",
                "/NS",
                "/NP",
                "/R:1",
                "/W:1",
                "/MT:8",
                "/XF",
                "*.priv",
                "*.pyc",
                "/XD",
                "__pycache__",
            ]
            # DEVNULL + CREATE_NO_WINDOW: no console flash on install robocopy
            _cf = 0
            if sys.platform == "win32":
                _cf = 0x08000000  # CREATE_NO_WINDOW
            r = subprocess.run(
                cmd,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=300,
                creationflags=_cf,
            )
            # robocopy: 0-7 = success with optional extras; ≥8 = failure
            if r.returncode < 8 and dst.is_dir() and any(dst.iterdir()):
                return
        except Exception:
            # Any robocopy issue → shutil fallback
            pass

    try:
        # If robocopy left a partial tree, clear before shutil
        if dst.exists():
            _rmtree_best_effort(dst)
        shutil.copytree(src, dst, ignore=_ignore)
    except OSError as exc:
        raise RuntimeError(
            f"Could not copy product files to {dst}. "
            f"Close any running Restore Privacy app and retry. ({exc})"
        ) from exc


def resolve_install_dir(
    *,
    prefer_program_files: bool = True,
    env: dict[str, str] | None = None,
) -> Path:
    """Choose install destination: Program Files by default, LocalAppData if unwritable.

    Pure path pick when *env* is injected; on a live Windows box, probes write
    access to Program Files\\Restore Privacy and falls soft to per-user.
    """
    e = env if env is not None else os.environ
    if (e.get("RPT_INSTALL_DIR") or "").strip():
        return default_windows_install_dir(e)
    if (e.get("RPT_INSTALL_PER_USER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return per_user_windows_install_dir(e)
    if not prefer_program_files:
        return per_user_windows_install_dir(e)
    primary = default_windows_install_dir(e)
    # Probe: can we create the product folder?
    try:
        primary.mkdir(parents=True, exist_ok=True)
        probe = primary / ".rpt_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return primary
    except OSError:
        fallback = per_user_windows_install_dir(e)
        return fallback


def read_installed_version(install_dir: Path | None = None) -> str | None:
    """Return VERSION string already present under the install directory, if any."""
    root = install_dir if install_dir is not None else INSTALL_DIR
    for rel in (
        Path("VERSION"),
        Path("client") / "VERSION",
        Path("_internal") / "client" / "VERSION",
    ):
        p = root / rel
        if p.is_file():
            try:
                v = p.read_text(encoding="utf-8").strip()
                if v:
                    return v
            except OSError:
                continue
    return None


def should_skip_bulk_tree_copy(
    payload_dir: Path,
    install_dir: Path | None = None,
    *,
    version: str | None = None,
) -> bool:
    """True when install dir already has this product version and a client exe.

    Same-version reinstall skips the multi-tens-of-MB tree copy (secrets and
    shortcuts are still refreshed by ``install()``).
    """
    root = install_dir if install_dir is not None else INSTALL_DIR
    want = (version if version is not None else VERSION).strip()
    if not root.is_dir():
        return False
    have = read_installed_version(root)
    if not have or have.strip() != want:
        return False
    try:
        _find_client_exe(root)
    except FileNotFoundError:
        return False
    # Payload must still look like a real product tree
    try:
        _find_client_exe(payload_dir)
    except FileNotFoundError:
        return False
    return True


def strip_all_private_keys(root: Path) -> list[str]:
    """Remove known *.priv slip-ins (shared client + node). Avoids full-tree rglob."""
    removed: list[str] = []
    if not root.is_dir():
        return removed
    # Known layouts only  -  full rglob on a frozen onedir is multi-second on HDDs
    candidates = (
        root / "secrets",
        root / "_internal" / "secrets",
        root / "client" / "secrets",
        root / "payload" / "secrets",
    )
    for folder in candidates:
        if not folder.is_dir():
            continue
        try:
            for p in folder.glob("*.priv"):
                try:
                    p.unlink()
                    removed.append(str(p))
                except OSError:
                    pass
        except OSError:
            pass
    return removed


def _find_payload_secrets(payload_dir: Path) -> Path | None:
    """Find packaged secrets that include at least node_elgamal.pub (public)."""
    for cand in (
        payload_dir / "secrets",
        payload_dir.parent / "secrets",
        payload_dir / "_internal" / "secrets",
        payload_dir / "client" / "secrets",
    ):
        if (cand / NODE_PUB).is_file():
            return cand
    # One shallow level only (no full-tree rglob)
    try:
        for child in payload_dir.iterdir():
            if not child.is_dir():
                continue
            for cand in (child / "secrets", child / "_internal" / "secrets"):
                if (cand / NODE_PUB).is_file():
                    return cand
    except OSError:
        pass
    return None


def _provision_secrets(payload_dir: Path, install_dir: Path) -> list[str]:
    """Install public node key only - device Ed25519 is generated on first run.

    Never copies a shared client_ed25519.priv into every install (impersonation risk).
    Never copies node_elgamal.priv. Strips any .priv that slipped into the install tree
    (e.g. under ``_internal/secrets`` from older packages).
    """
    written: list[str] = []
    src = _find_payload_secrets(payload_dir)
    if src is None and getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        for cand in (base / "secrets", base / "payload" / "secrets"):
            if (cand / NODE_PUB).is_file():
                src = cand
                break

    for dest in (install_dir / "secrets", USER_SECRETS):
        dest.mkdir(parents=True, exist_ok=True)
        if src is not None:
            sp = src / NODE_PUB
            if sp.is_file():
                target = dest / NODE_PUB
                target.write_bytes(sp.read_bytes())
                written.append(str(target))

    # Strip package-resident shared priv under install (incl. _internal) AND user secrets.
    # USER_SECRETS may still hold the pre-0.1.3 universal client_ed25519.priv after upgrade.
    strip_all_private_keys(install_dir)
    strip_all_private_keys(USER_SECRETS)
    return written


def _write_version(install_dir: Path) -> None:
    (install_dir / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    secrets_ok = (install_dir / "secrets" / NODE_PUB).is_file()
    sec_line = (
        "Node public key installed: yes (device Ed25519 key is generated on first run)"
        if secrets_ok
        else f"Node public key missing - place {NODE_PUB} in secrets\\ (device key auto-generated)"
    )
    (install_dir / "INSTALL.txt").write_text(
        f"Restore Privacy Client {VERSION}\r\n"
        "Installed with bundled Python runtime and dependencies.\r\n"
        "Open the app as a normal user (no Run as administrator on the shortcut).\r\n"
        "Connect asks for Administrator once for residual routes (Wintun), or install\r\n"
        "the residual helper once (elevated) so day-to-day Connect needs no UAC.\r\n"
        f"Install path: {install_dir}\r\n"
        f"{sec_line}\r\n",
        encoding="utf-8",
    )


def resolve_shortcut_icon(install_dir: Path, target: Path) -> Path:
    """Logo ICO for Start Menu / Desktop shortcuts (product brand)."""
    candidates = [
        install_dir / "app_icon.ico",
        install_dir / "client" / "windows" / "native" / "app_icon.ico",
        install_dir / "_internal" / "client" / "windows" / "native" / "app_icon.ico",
        install_dir / "_internal" / "app_icon.ico",
        target,  # exe may embed icon from PyInstaller --icon
    ]
    for p in candidates:
        if p.is_file() and p.suffix.lower() == ".ico":
            return p
    return target


def _ps_escape_double(s: str) -> str:
    """Escape for PowerShell double-quoted string."""
    return s.replace("`", "``").replace('"', '`"').replace("$", "`$")


def _create_shortcuts_batch(
    items: list[tuple[Path, Path, Path, Path | None, str | None, bool]],
) -> None:
    """Create many .lnk files in one PowerShell process (avoids multi-second cold starts).

    Each item: (target, link_path, workdir, icon_or_None, description_or_None, run_as_admin).
    """
    if not items:
        return
    for _t, link_path, _w, _i, _d, _r in items:
        try:
            link_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    parts = ["$ws = New-Object -ComObject WScript.Shell"]
    for target, link_path, workdir, icon, description, run_as_admin in items:
        icon_path = icon or resolve_shortcut_icon(workdir, target)
        desc = description or (
            f"{SHORTCUT_DISPLAY_NAME} VPN Client {VERSION} "
            "(open normally; Connect requests residual privilege)"
        )
        desc_ps = _ps_escape_double(desc)
        parts.append(
            f"$s = $ws.CreateShortcut({str(link_path)!r}); "
            f"$s.TargetPath = {str(target)!r}; "
            f"$s.WorkingDirectory = {str(workdir)!r}; "
            f'$s.Description = "{desc_ps}"; '
            f"$s.IconLocation = {str(icon_path)!r} + ',0'; "
            f"$s.Save()"
        )
        if run_as_admin:
            parts.append(
                f"$p = {str(link_path)!r}; "
                f"$b = [System.IO.File]::ReadAllBytes($p); "
                f"if ($b.Length -gt 0x15) {{ $b[0x15] = $b[0x15] -bor 0x20; "
                f"[System.IO.File]::WriteAllBytes($p, $b) }}"
            )
    ps = "; ".join(parts)
    # Hidden PowerShell host — no console flash while creating .lnk shortcuts
    _cf = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    _si = None
    if sys.platform == "win32":
        _si = subprocess.STARTUPINFO()
        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0  # SW_HIDE
    subprocess.run(
        [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-Command",
            ps,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=45,
        stdin=subprocess.DEVNULL,
        creationflags=_cf,
        startupinfo=_si,
    )


def _create_shortcut(
    target: Path,
    link_path: Path,
    workdir: Path,
    *,
    icon: Path | None = None,
    description: str | None = None,
    run_as_admin: bool = False,
) -> None:
    """Create one .lnk with brand logo icon (thin wrapper around batch helper)."""
    _create_shortcuts_batch(
        [(target, link_path, workdir, icon, description, run_as_admin)]
    )


def install_step_count() -> int:
    """Number of user-visible install steps (for progress bar)."""
    return 6


def format_install_failure_status(error_message: str) -> str:
    """User-facing status line after a failed install (no exception objects)."""
    msg = (error_message or "").strip() or "Unknown error"
    return f"Installation failed:\n{msg}"


def format_install_success_status(install_dir: Path, launched_name: str) -> str:
    """User-facing status after a successful install."""
    return (
        f"Installation complete.\n"
        f"Installed to:\n{install_dir}\n"
        f"Launched: {launched_name}"
    )


def installer_success_autoclose_ms() -> int:
    """How long to show success text before auto-closing the setup window."""
    return 900


def should_autoclose_installer_on_success() -> bool:
    """Product policy: success closes the installer; failure stays open."""
    return True


def install(
    launch: bool = True,
    *,
    progress_cb: Callable[[int, int, str], None] | None = None,
    install_dir: Path | None = None,
) -> Path:
    """Deploy bundled client to Program Files\\Restore Privacy (or fallback).

    Bundle: main client executable + Restore Internet failsafe in the same tree.
    ``progress_cb(step_index, total, status_text)`` is invoked for GUI progress.
    """
    global INSTALL_DIR
    target = install_dir if install_dir is not None else resolve_install_dir()
    INSTALL_DIR = target
    if is_under_program_files(target):
        loc_note = f"Program Files product folder ({PRODUCT_FOLDER_DISPLAY})"
    else:
        loc_note = (
            f"per-user folder (Program Files not writable without elevation; "
            f"{PRODUCT_FOLDER_LEGACY_ID})"
        )

    def _progress(step: int, status: str) -> None:
        total = install_step_count()
        if progress_cb is not None:
            try:
                progress_cb(step, total, status)
            except Exception:
                pass
        # Windowed setup: avoid console chatter (no attached console on --noconsole)
        if sys.stdout is not None and hasattr(sys.stdout, "isatty"):
            try:
                if sys.stdout.isatty():
                    print(f"[{step}/{total}] {status}")
            except Exception:
                pass

    _progress(1, "Locating product files...")
    payload = _payload_root()
    client_src_exe = _find_client_exe(payload)
    # If payload root is the onedir folder, copy whole tree
    payload_dir = client_src_exe.parent

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    skip_copy = should_skip_bulk_tree_copy(payload_dir, INSTALL_DIR, version=VERSION)
    if skip_copy:
        _progress(2, f"Already at v{VERSION} - skipping bulk file copy...")
    else:
        _progress(2, f"Copying files to {INSTALL_DIR} ({loc_note})...")
        _copy_tree(payload_dir, INSTALL_DIR)
    # Belt-and-suspenders: never leave shared .priv from old payloads
    strip_all_private_keys(INSTALL_DIR)

    _progress(3, "Installing admission secrets...")
    secrets_written = _provision_secrets(payload_dir, INSTALL_DIR)

    # Auto-provision Connect entitlement (fast path only  -  no full Downloads walk).
    try:
        from client.payment_entitlement import (
            default_entitlement_path,
            provision_entitlement_from_installer_dirs,
        )

        search = [
            Path.cwd(),
            payload_dir,
            Path(sys.argv[0]).resolve().parent if sys.argv else Path.cwd(),
        ]
        # Single known thank-you filename only (avoid scanning whole Downloads tree)
        try:
            dl = Path.home() / "Downloads" / "payment_entitlement.json"
            if dl.is_file():
                search.append(dl.parent)
        except Exception:
            pass
        ent = provision_entitlement_from_installer_dirs(
            *search, dest_path=default_entitlement_path()
        )
        if ent and ent.session_id:
            pass  # silent  -  GUI progress already shows secrets/version steps
    except Exception:
        pass

    _progress(4, "Writing version and install info...")
    _write_version(INSTALL_DIR)
    # Also place VERSION next to package data for frozen version readers
    try:
        for sub in (
            INSTALL_DIR / "client" / "VERSION",
            INSTALL_DIR / "_internal" / "client" / "VERSION",
        ):
            sub.parent.mkdir(parents=True, exist_ok=True)
            sub.write_text(VERSION + "\n", encoding="utf-8")
    except Exception:
        pass

    installed_exe = INSTALL_DIR / client_src_exe.name
    if not installed_exe.is_file():
        # rename if needed
        candidates = list(INSTALL_DIR.glob("*.exe"))
        if not candidates:
            raise FileNotFoundError("Install copy failed - no .exe in install dir")
        installed_exe = candidates[0]

    if not secrets_written:
        # Still launch; app surfaces secrets error. Avoid console I/O on windowed builds.
        try:
            if sys.stdout is not None and sys.stdout.isatty():
                print(
                    "WARNING: admission secrets not found in installer payload. "
                    f"Place {CLIENT_PRIV} and {NODE_PUB} under {INSTALL_DIR / 'secrets'}"
                )
        except Exception:
            pass

    # Brand logo ICO next to installed exe (known paths only  -  no full-tree rglob)
    try:
        dest_ico = INSTALL_DIR / "app_icon.ico"
        if not dest_ico.is_file():
            for cand in (
                Path(__file__).resolve().parent / "native" / "app_icon.ico",
                payload_dir / "app_icon.ico",
                payload_dir / "native" / "app_icon.ico",
                INSTALL_DIR / "native" / "app_icon.ico",
                INSTALL_DIR / "_internal" / "client" / "windows" / "native" / "app_icon.ico",
            ):
                if cand.is_file():
                    shutil.copy2(cand, dest_ico)
                    break
    except Exception:
        pass

    icon = resolve_shortcut_icon(INSTALL_DIR, installed_exe)

    # Restore Internet failsafe (network restore + full uninstall) + FW allow helper.
    # ALWAYS ship the full failsafe (routes + RPT-KS/RPT-FW cleanup + tree remove).
    # Never write the historical three-line rmdir-only stub.
    restore_bat = INSTALL_DIR / "Restore Internet.bat"
    restore_alias = INSTALL_DIR / "RestoreInternet.bat"
    allow_bat = INSTALL_DIR / "AllowFirewall.bat"
    try:
        ship_restore_internet_failsafe(INSTALL_DIR)
        # AllowFirewall is optional helper (best-effort copy)
        here = Path(__file__).resolve().parent
        for cand in _restore_internet_source_candidates("AllowFirewall.bat"):
            if cand.is_file():
                shutil.copy2(cand, allow_bat)
                break
        if not restore_bat.is_file() and restore_alias.is_file():
            shutil.copy2(restore_alias, restore_bat)
    except Exception:
        # Last resort: still try to write full body (never stub)
        try:
            ship_restore_internet_failsafe(INSTALL_DIR)
        except Exception:
            pass
    # Assert client + Restore Internet co-bundle (honest install inventory)
    inv = inventory_install_bundle(INSTALL_DIR, platform="win32")
    if not inv.restore_internet_entry and restore_bat.is_file():
        inv = inventory_install_bundle(INSTALL_DIR, platform="win32")
    if not inv.complete:
        try:
            if sys.stdout is not None and sys.stdout.isatty():
                print(
                    "WARNING: install bundle incomplete  -  need client .exe and "
                    f"Restore Internet under {INSTALL_DIR} "
                    f"(client={inv.client_entry!r} restore={inv.restore_internet_entry!r})"
                )
        except Exception:
            pass

    # Skip heavy firewall probe during setup (AllowFirewall.bat / Connect UAC covers it).
    # netsh under install was a common multi-second hang before progress advanced.

    # Launch wrapper: allow FW, run app, residual restore on exit (Quit path)
    launch_bat = INSTALL_DIR / "LaunchPrivacyRestored.bat"
    try:
        launch_bat.write_text(
            "@echo off\r\n"
            "setlocal\r\n"
            "cd /d \"%~dp0\"\r\n"
            "if exist \"%~dp0AllowFirewall.bat\" call \"%~dp0AllowFirewall.bat\" /quiet\r\n"
            f'start /wait "" "%~dp0{installed_exe.name}"\r\n',
            encoding="utf-8",
        )
    except Exception:
        launch_bat = installed_exe

    _progress(5, "Creating Start Menu and Desktop shortcuts...")
    # One PowerShell process for all .lnk files (six separate spawns were multi-second)
    try:
        shortcut_target = launch_bat if launch_bat.is_file() else installed_exe
        batch: list[tuple[Path, Path, Path, Path | None, str | None, bool]] = [
            (
                shortcut_target,
                START_MENU / f"{SHORTCUT_DISPLAY_NAME}.lnk",
                INSTALL_DIR,
                icon,
                None,
                False,
            ),
            (
                shortcut_target,
                DESKTOP / f"{SHORTCUT_DISPLAY_NAME}.lnk",
                INSTALL_DIR,
                icon,
                None,
                False,
            ),
            # Legacy name for upgrades that look for old Start Menu entry
            (
                shortcut_target,
                START_MENU / f"{APP_NAME}.lnk",
                INSTALL_DIR,
                icon,
                None,
                False,
            ),
        ]
        if restore_bat.is_file():
            _ri_desc = (
                "WARNING: erases ALL Restore Privacy; contact "
                "rus@restoreprivacy.online for a new download link"
            )
            batch.append(
                (
                    restore_bat,
                    START_MENU / "Restore Internet.lnk",
                    INSTALL_DIR,
                    icon,
                    _ri_desc,
                    False,
                )
            )
            batch.append(
                (
                    restore_bat,
                    DESKTOP / "Restore Internet.lnk",
                    INSTALL_DIR,
                    icon,
                    _ri_desc,
                    False,
                )
            )
        if allow_bat.is_file():
            batch.append(
                (
                    allow_bat,
                    START_MENU / "Allow Firewall for rpT0.lnk",
                    INSTALL_DIR,
                    icon,
                    None,
                    False,
                )
            )
        _create_shortcuts_batch(batch)
    except Exception:
        # Shortcuts are nice-to-have; install still succeeds
        pass

    # Uninstall.bat aliases the full Restore Internet failsafe
    uninst = INSTALL_DIR / "Uninstall.bat"
    uninst.write_text(
        "@echo off\r\n"
        f"title Uninstall {SHORTCUT_DISPLAY_NAME} {VERSION}\r\n"
        "if exist \"%~dp0Restore Internet.bat\" (\r\n"
        "  call \"%~dp0Restore Internet.bat\" %*\r\n"
        "  exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        "if exist \"%~dp0RestoreInternet.bat\" (\r\n"
        "  call \"%~dp0RestoreInternet.bat\" %*\r\n"
        "  exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        "echo Restore Internet failsafe missing.\r\n"
        "pause\r\n"
        "exit /b 1\r\n",
        encoding="utf-8",
    )

    _progress(6, "Finishing install...")
    if launch and installed_exe.is_file():
        # Detach GUI client: no console flash, installer can exit cleanly
        creation = 0
        if sys.platform == "win32":
            creation = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            creation |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            creation |= 0x08000000  # CREATE_NO_WINDOW
        try:
            subprocess.Popen(
                [str(installed_exe)],
                cwd=str(INSTALL_DIR),
                close_fds=True,
                creationflags=creation,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except TypeError:
            subprocess.Popen(
                [str(installed_exe)],
                cwd=str(INSTALL_DIR),
                close_fds=True,
            )
    return installed_exe


def _close_pyi_splash(status: str | None = None) -> None:
    """Close PyInstaller bootloader splash once Tk (or console fallback) is ready."""
    try:
        import pyi_splash  # type: ignore[import-not-found]

        if status:
            try:
                pyi_splash.update_text(status)
            except Exception:
                pass
        pyi_splash.close()
    except Exception:
        pass


def run_installer_progress_ui(*, launch: bool = True) -> int:
    """Standard installer window: title, status line, determinate progress bar."""
    import threading
    import tkinter as tk
    from tkinter import ttk

    # Drop any leftover console host (dev launches / legacy --console builds)
    try:
        from client.windows.launch_gui import free_console_if_attached

        free_console_if_attached()
    except Exception:
        try:
            import ctypes

            ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass

    _close_pyi_splash("Starting setup…")

    root = tk.Tk()
    root.title(f"{SHORTCUT_DISPLAY_NAME} Setup v{VERSION}")
    root.geometry("480x220")
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    # Icon when available
    try:
        ico = Path(__file__).resolve().parent / "native" / "app_icon.ico"
        if ico.is_file():
            root.iconbitmap(default=str(ico))
    except Exception:
        pass

    outer = tk.Frame(root, padx=18, pady=16)
    outer.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        outer,
        text=f"{SHORTCUT_DISPLAY_NAME}",
        font=("Segoe UI", 14, "bold"),
        anchor="w",
    ).pack(fill=tk.X)
    tk.Label(
        outer,
        text=f"Installer - version {VERSION}",
        font=("Segoe UI", 9),
        fg="#444444",
        anchor="w",
    ).pack(fill=tk.X, pady=(0, 12))

    status_var = tk.StringVar(value="Preparing install...")
    status_lbl = tk.Label(
        outer,
        textvariable=status_var,
        font=("Segoe UI", 10),
        anchor="w",
        wraplength=440,
        justify=tk.LEFT,
    )
    status_lbl.pack(fill=tk.X, pady=(0, 8))

    bar = ttk.Progressbar(outer, mode="determinate", maximum=install_step_count())
    bar.pack(fill=tk.X, pady=(0, 12))
    bar["value"] = 0

    detail_var = tk.StringVar(value=f"Install location:\n{INSTALL_DIR}")
    tk.Label(
        outer,
        textvariable=detail_var,
        font=("Segoe UI", 8),
        fg="#666666",
        anchor="w",
        justify=tk.LEFT,
        wraplength=440,
    ).pack(fill=tk.X)

    btn_row = tk.Frame(outer)
    btn_row.pack(fill=tk.X, side=tk.BOTTOM, pady=(12, 0))
    close_btn = tk.Button(
        btn_row,
        text="Close",
        state=tk.DISABLED,
        width=10,
        command=root.destroy,
    )
    close_btn.pack(side=tk.RIGHT)

    result: dict = {"path": None, "error": None, "traceback": None, "code": 1}

    def on_progress(step: int, total: int, status: str) -> None:
        def ui() -> None:
            status_var.set(status)
            bar["maximum"] = max(1, total)
            bar["value"] = min(step, total)
            root.update_idletasks()

        root.after(0, ui)

    def work() -> None:
        try:
            path = install(launch=launch, progress_cb=on_progress)
            result["path"] = path
            result["code"] = 0
            # Capture path name before deferred callback (closure-safe)
            path_name = path.name if path is not None else "yes"

            success_status = format_install_success_status(INSTALL_DIR, path_name)
            autoclose_ms = installer_success_autoclose_ms()
            do_autoclose = should_autoclose_installer_on_success()

            def done_ok() -> None:
                status_var.set(success_status)
                bar["value"] = bar["maximum"]
                close_btn.configure(state=tk.NORMAL)
                close_btn.focus_set()
                # Do not leave the setup window open after a successful install.
                if do_autoclose:
                    root.after(autoclose_ms, root.destroy)

            root.after(0, done_ok)
        except Exception as exc:
            # Bind strings before nested callback - Python clears `except as` names
            # after the block, so deferred root.after cannot read `exc` later.
            err_msg = str(exc) or exc.__class__.__name__
            err_tb = traceback.format_exc()
            result["error"] = err_msg
            result["traceback"] = err_tb
            result["code"] = 1
            fail_status = format_install_failure_status(err_msg)
            fail_detail = (err_tb or "")[:500]

            def done_err() -> None:
                # Stay open with real error - user dismisses via Close (no auto-destroy).
                status_var.set(fail_status)
                detail_var.set(fail_detail)
                close_btn.configure(state=tk.NORMAL)
                close_btn.focus_set()

            root.after(0, done_err)

    threading.Thread(target=work, daemon=True).start()
    root.mainloop()
    return int(result["code"])


def main() -> int:
    """GUI progress installer by default; console fallback if Tk unavailable."""
    # Prefer standard progress window (double-click / frozen setup)
    if sys.platform == "win32":
        try:
            # Splash (if any) stays up until Tk window builds inside run_installer_progress_ui
            return run_installer_progress_ui(launch=True)
        except Exception as gui_exc:
            _close_pyi_splash()
            try:
                print(
                    f"Installer GUI unavailable ({gui_exc}); using console path.",
                    file=sys.stderr,
                )
            except Exception:
                pass

    try:
        path = install(launch=True)
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

            ctypes.windll.user32.MessageBoxW(
                0, msg[:1000], f"{SHORTCUT_DISPLAY_NAME} Installer", 0x10
            )
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

